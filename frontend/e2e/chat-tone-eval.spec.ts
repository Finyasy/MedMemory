import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './fixtures';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
const E2E_EMAIL = process.env.E2E_EMAIL || 'demo@medmemory.ai';
const E2E_PASSWORD = process.env.E2E_PASSWORD || 'demo-password';
const PROMPT_PROFILE = (
  process.env.E2E_PROMPT_PROFILE
  || process.env.LLM_PROMPT_PROFILE
  || 'baseline_current'
).trim();
const ENFORCE_HARD_FAIL = (process.env.E2E_EVAL_ENFORCE_HARD_FAIL || 'false').toLowerCase() === 'true';

const ROBOTIC_PHRASES = [
  'as an ai',
  'based on the provided context',
  'here is the summary',
  'i understand',
  'please consult your healthcare provider',
  'for informational purposes only',
];

const TEMPLATE_STARTERS = [
  'From your records',
  'The document does not record this information.',
  'I do not know from the available records.',
  'Not in documents.',
];

type FixtureRecord = {
  key: string;
  title: string;
  content: string;
  record_type: string;
};

type ScenarioExpectation = {
  requires_sources: boolean;
  expects_numeric_grounding: boolean;
  refusal_expected: boolean;
  expected_keywords: string[];
  max_words?: number;
};

type EvalScenario = {
  id: string;
  description: string;
  turns: string[];
  expectation: ScenarioExpectation;
};

type ScenarioFixture = {
  default_refusal_phrases: string[];
  scenarios: EvalScenario[];
};

type RecordFixture = {
  records: FixtureRecord[];
};

type PatientSummary = {
  id: number;
  full_name: string;
};

type CreatedRecord = {
  id: number;
  patient_id: number;
  title: string;
};

type MemoryChunkSummary = {
  id: number;
  content: string;
  chunk_type?: string | null;
};

type TurnRunResult = {
  prompt: string;
  response_text: string;
  source_chips: string[];
  badges: string[];
  mode_metadata: {
    endpoint: 'ask' | 'stream' | 'unknown';
    structured: boolean;
    coaching_mode: boolean;
    clinician_mode: boolean;
    http_status: number;
  };
  duration_ms: number;
  word_count: number;
};

type ScenarioRunResult = {
  id: string;
  description: string;
  expectation: ScenarioExpectation;
  turns: TurnRunResult[];
};

type ScoreBundle = ReturnType<typeof scoreRuns>;

type ScoreArtifact = {
  variant: string;
  timestamp: string;
  scoring: ScoreBundle;
  hard_fail: boolean;
  baseline_comparison?: {
    baseline_variant: string;
    baseline_timestamp: string;
    grounding_regression: boolean;
    naturalness_uplift: number;
  } | null;
  selection_rule?: string;
};

const dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtureBaseDir = path.resolve(dirname, '../../docs/fixtures/medgemma_chat_eval');
const artifactDir = path.resolve(dirname, '../../artifacts/medgemma-chat-eval');
const winnerTieBreakPriority: Record<string, number> = {
  warm_concise_v1: 0,
  warm_concise_v2: 1,
  clinician_terse_humanized: 2,
};

const clampScore = (value: number): number => Math.max(0, Math.min(100, Math.round(value)));

const normalize = (text: string): string =>
  text.toLowerCase().replace(/\s+/g, ' ').trim();

const normalizeSourceType = (recordType: string): string => {
  const normalized = recordType.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
  return normalized.slice(0, 48) || 'eval_fixture';
};

const splitSentences = (text: string): string[] =>
  text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

const countWords = (text: string): number =>
  text
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;

const hasNumericToken = (text: string): boolean =>
  /\b\d+(?:\.\d+)?(?:\/\d+)?\b/.test(text);

const hasCitationEvidence = (turn: TurnRunResult): boolean =>
  turn.source_chips.length > 0 || turn.response_text.includes('(source:');

const containsRefusal = (text: string, refusalPhrases: string[]): boolean => {
  const normalizedText = normalize(text);
  return refusalPhrases.some((phrase) => normalizedText.includes(normalize(phrase)));
};

const countRoboticPhrases = (text: string): number => {
  const lowered = text.toLowerCase();
  return ROBOTIC_PHRASES.reduce((count, phrase) => (
    count + (lowered.includes(phrase) ? 1 : 0)
  ), 0);
};

const getFirstSentence = (text: string): string => splitSentences(text)[0] || '';

const isFirstSentenceUseful = (text: string): boolean => {
  const sentence = normalize(getFirstSentence(text));
  if (!sentence || sentence.length < 12) return false;
  if (sentence.startsWith('here is') || sentence.startsWith('i understand')) return false;
  return true;
};

const loadFixtureJson = async <T>(filename: string): Promise<T> => {
  const filePath = path.resolve(fixtureBaseDir, filename);
  const raw = await fs.readFile(filePath, 'utf-8');
  return JSON.parse(raw) as T;
};

const apiLogin = async (request: APIRequestContext): Promise<string> => {
  const response = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { email: E2E_EMAIL, password: E2E_PASSWORD },
  });
  expect(response.ok(), `API login failed (${response.status()})`).toBeTruthy();
  const body = (await response.json()) as { access_token?: string };
  expect(body.access_token, 'Missing access token from API login').toBeTruthy();
  return body.access_token as string;
};

const listPatients = async (
  request: APIRequestContext,
  token: string,
): Promise<PatientSummary[]> => {
  const response = await request.get(`${API_BASE}/api/v1/patients/?limit=200`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok(), `List patients failed (${response.status()})`).toBeTruthy();
  return (await response.json()) as PatientSummary[];
};

const findPatientIdByName = (patients: PatientSummary[], fullName: string): number | null => {
  const normalizedTarget = normalize(fullName);
  const exact = patients.find((patient) => normalize(patient.full_name) === normalizedTarget);
  if (exact) return exact.id;
  const loose = patients.find((patient) => normalize(patient.full_name).includes(normalizedTarget));
  return loose?.id ?? null;
};

const cleanupEvalRecords = async (
  request: APIRequestContext,
  token: string,
  patientId: number,
  titlePrefix: string,
): Promise<void> => {
  const listResponse = await request.get(
    `${API_BASE}/api/v1/records/?patient_id=${patientId}&limit=1000`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(listResponse.ok(), `List records failed (${listResponse.status()})`).toBeTruthy();
  const records = (await listResponse.json()) as Array<{ id: number; title: string }>;
  const matchingIds = records
    .filter((record) => (record.title || '').startsWith(titlePrefix))
    .map((record) => record.id);

  for (const recordId of matchingIds) {
    const deleteResponse = await request.delete(`${API_BASE}/api/v1/records/${recordId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(
      deleteResponse.status() === 204 || deleteResponse.status() === 200 || deleteResponse.status() === 404,
      `Delete record ${recordId} failed (${deleteResponse.status()})`,
    ).toBeTruthy();
  }
};

const seedEvalRecords = async (
  request: APIRequestContext,
  token: string,
  patientId: number,
  fixtureRecords: FixtureRecord[],
  titlePrefix: string,
): Promise<CreatedRecord[]> => {
  const created: CreatedRecord[] = [];
  for (const fixtureRecord of fixtureRecords) {
    const createResponse = await request.post(
      `${API_BASE}/api/v1/records/?patient_id=${patientId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        data: {
          title: `${titlePrefix}${fixtureRecord.title}`,
          content: fixtureRecord.content,
          record_type: fixtureRecord.record_type,
        },
      },
    );
    expect(
      createResponse.ok(),
      `Create record failed for ${fixtureRecord.key} (${createResponse.status()})`,
    ).toBeTruthy();
    created.push((await createResponse.json()) as CreatedRecord);
  }
  return created;
};

const listPatientMemoryChunks = async (
  request: APIRequestContext,
  token: string,
  patientId: number,
): Promise<MemoryChunkSummary[]> => {
  const allChunks: MemoryChunkSummary[] = [];
  const pageSize = 1000;
  let skip = 0;

  while (true) {
    const response = await request.get(
      `${API_BASE}/api/v1/memory/chunks?patient_id=${patientId}&indexed_only=false&limit=${pageSize}&skip=${skip}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(response.ok(), `List memory chunks failed (${response.status()})`).toBeTruthy();
    const rows = (await response.json()) as MemoryChunkSummary[];
    allChunks.push(...rows);
    if (rows.length < pageSize) break;
    skip += pageSize;
  }

  return allChunks;
};

const cleanupEvalMemoryChunks = async (
  request: APIRequestContext,
  token: string,
  patientId: number,
): Promise<void> => {
  const chunks = await listPatientMemoryChunks(request, token, patientId);
  const evalChunkIds = chunks
    .filter((chunk) =>
      chunk.chunk_type === 'eval_fixture'
      || (chunk.content || '').includes('[EVAL')
      || (chunk.content || '').includes('EVAL_FIXTURE'))
    .map((chunk) => chunk.id);

  for (const chunkId of evalChunkIds) {
    const deleteResponse = await request.delete(`${API_BASE}/api/v1/memory/chunks/${chunkId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(
      deleteResponse.status() === 204 || deleteResponse.status() === 200 || deleteResponse.status() === 404,
      `Delete memory chunk ${chunkId} failed (${deleteResponse.status()})`,
    ).toBeTruthy();
  }
};

const seedEvalMemoryChunks = async (
  request: APIRequestContext,
  token: string,
  patientId: number,
  fixtureRecords: FixtureRecord[],
): Promise<number> => {
  let totalChunks = 0;

  for (const fixtureRecord of fixtureRecords) {
    const content = `${fixtureRecord.title}\n${fixtureRecord.content}`;
    const response = await request.post(`${API_BASE}/api/v1/memory/index/text`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: {
        patient_id: patientId,
        content,
        source_type: normalizeSourceType(fixtureRecord.record_type),
        chunk_type: 'eval_fixture',
        importance_score: 0.8,
      },
    });
    expect(
      response.ok(),
      `Index memory text failed for ${fixtureRecord.key} (${response.status()})`,
    ).toBeTruthy();
    const body = (await response.json()) as { total_chunks?: number };
    totalChunks += body.total_chunks ?? 0;
  }

  return totalChunks;
};

const askViaChatInterface = async (page: Page, prompt: string): Promise<TurnRunResult> => {
  const assistantMessages = page.locator('.message.message-assistant');
  const assistantCountBefore = await assistantMessages.count();
  const input = page.getByTestId('chat-input');
  const sendButton = page.getByTestId('chat-send');

  const responsePromise = page.waitForResponse(
    (response) => {
      const url = response.url();
      return (
        response.request().method() === 'POST'
        && (url.includes('/api/v1/chat/ask') || url.includes('/api/v1/chat/stream'))
      );
    },
    { timeout: 90_000 },
  );

  const start = Date.now();
  await input.fill(prompt);
  await sendButton.click();

  const apiResponse = await responsePromise;
  await expect(assistantMessages).toHaveCount(assistantCountBefore + 1, { timeout: 90_000 });

  const newAssistantMessage = assistantMessages.nth(assistantCountBefore);
  const newAssistantText = newAssistantMessage.locator('.message-text');
  await expect
    .poll(async () => (await newAssistantText.innerText()).trim().length, { timeout: 90_000 })
    .toBeGreaterThan(0);

  await expect(input).toBeEnabled({ timeout: 90_000 });
  await page.waitForTimeout(250);

  const responseText = (await newAssistantText.innerText()).trim();
  const sourceChips = await newAssistantMessage.locator('.message-source-chip').allInnerTexts();
  const badges = await newAssistantMessage.locator('.message-badge').allInnerTexts();
  const url = new URL(apiResponse.url());
  const endpoint = url.pathname.endsWith('/ask')
    ? 'ask'
    : (url.pathname.endsWith('/stream') ? 'stream' : 'unknown');

  return {
    prompt,
    response_text: responseText,
    source_chips: sourceChips,
    badges,
    mode_metadata: {
      endpoint,
      structured: url.searchParams.get('structured') === 'true',
      coaching_mode: url.searchParams.get('coaching_mode') === 'true',
      clinician_mode: url.searchParams.get('clinician_mode') === 'true',
      http_status: apiResponse.status(),
    },
    duration_ms: Date.now() - start,
    word_count: countWords(responseText),
  };
};

const scoreRuns = (
  runs: ScenarioRunResult[],
  refusalPhrases: string[],
) => {
  let unsupportedNumericClaims = 0;
  let uncitedClinicianNumericClaims = 0;
  let refusalPolicyViolations = 0;
  let overLimitResponses = 0;
  let usefulFirstSentenceCount = 0;
  let clarityIssues = 0;
  let keywordMisses = 0;
  let templateStarterCount = 0;
  let roboticPhraseCount = 0;

  const allTurnResponses = runs.flatMap((scenario) => scenario.turns.map((turn) => turn.response_text));
  const allSentences = allTurnResponses.flatMap((text) => splitSentences(text));
  const uniqueSentenceCount = new Set(allSentences.map(normalize)).size;
  const duplicateSentenceCount = Math.max(0, allSentences.length - uniqueSentenceCount);
  const sentenceVariability = allSentences.length > 0 ? uniqueSentenceCount / allSentences.length : 1;

  for (const scenario of runs) {
    const finalTurn = scenario.turns[scenario.turns.length - 1];
    const refusal = containsRefusal(finalTurn.response_text, refusalPhrases);
    const hasNumeric = hasNumericToken(finalTurn.response_text);
    const hasEvidence = hasCitationEvidence(finalTurn);

    if (scenario.expectation.refusal_expected && !refusal) refusalPolicyViolations += 1;
    if (!scenario.expectation.refusal_expected && refusal) refusalPolicyViolations += 1;

    if (scenario.expectation.expects_numeric_grounding && hasNumeric && !hasEvidence) {
      unsupportedNumericClaims += 1;
    }
    if (finalTurn.mode_metadata.clinician_mode && hasNumeric && !hasEvidence) {
      uncitedClinicianNumericClaims += 1;
    }

    if (scenario.expectation.max_words && finalTurn.word_count > scenario.expectation.max_words) {
      overLimitResponses += 1;
    }
    if (isFirstSentenceUseful(finalTurn.response_text)) usefulFirstSentenceCount += 1;
    if (/\[[^\]]+\]/.test(finalTurn.response_text) || finalTurn.response_text.includes('****')) {
      clarityIssues += 1;
    }
    if (scenario.expectation.expected_keywords.length > 0) {
      const lowered = finalTurn.response_text.toLowerCase();
      const hasExpectedKeyword = scenario.expectation.expected_keywords.some((keyword) =>
        lowered.includes(keyword.toLowerCase()));
      if (!hasExpectedKeyword) {
        clarityIssues += 1;
        keywordMisses += 1;
      }
    }
    if (TEMPLATE_STARTERS.some((starter) => finalTurn.response_text.startsWith(starter))) {
      templateStarterCount += 1;
    }
    roboticPhraseCount += countRoboticPhrases(finalTurn.response_text);
  }

  const scenarioCount = Math.max(runs.length, 1);
  const groundingScore = clampScore(
    100
    - unsupportedNumericClaims * 35
    - uncitedClinicianNumericClaims * 20
    - refusalPolicyViolations * 30,
  );

  const naturalnessScore = clampScore(
    100
    - roboticPhraseCount * 12
    - duplicateSentenceCount * 8
    - templateStarterCount * 6
    - Math.max(0, 0.65 - sentenceVariability) * 70,
  );

  const concisePassRate = (scenarioCount - overLimitResponses) / scenarioCount;
  const firstSentenceUsefulnessRate = usefulFirstSentenceCount / scenarioCount;
  const uxScore = clampScore(
    45
    + concisePassRate * 30
    + firstSentenceUsefulnessRate * 25
    - clarityIssues * 8,
  );

  return {
    grounding: {
      score: groundingScore,
      unsupported_numeric_claims: unsupportedNumericClaims,
      uncited_clinician_numeric_claims: uncitedClinicianNumericClaims,
      refusal_policy_violations: refusalPolicyViolations,
    },
    naturalness: {
      score: naturalnessScore,
      robotic_phrase_count: roboticPhraseCount,
      duplicate_sentence_count: duplicateSentenceCount,
      sentence_variability: Number(sentenceVariability.toFixed(4)),
      template_starter_count: templateStarterCount,
    },
    ux: {
      score: uxScore,
      over_limit_responses: overLimitResponses,
      concise_pass_rate: Number(concisePassRate.toFixed(4)),
      first_sentence_usefulness_rate: Number(firstSentenceUsefulnessRate.toFixed(4)),
      clarity_issues: clarityIssues,
      keyword_misses: keywordMisses,
    },
  };
};

const readScoreArtifacts = async (): Promise<ScoreArtifact[]> => {
  try {
    const entries = await fs.readdir(artifactDir);
    const parsed = await Promise.all(
      entries
        .filter((entry) => entry.endsWith('-score.json'))
        .map(async (entry) => {
          const raw = await fs.readFile(path.resolve(artifactDir, entry), 'utf-8');
          return JSON.parse(raw) as ScoreArtifact;
        }),
    );
    return parsed.filter((artifact) => artifact?.variant && artifact?.scoring);
  } catch {
    return [];
  }
};

const latestArtifactsByVariant = (artifacts: ScoreArtifact[]): Map<string, ScoreArtifact> => {
  const latest = new Map<string, ScoreArtifact>();
  for (const artifact of artifacts) {
    const current = latest.get(artifact.variant);
    if (!current || new Date(artifact.timestamp) > new Date(current.timestamp)) {
      latest.set(artifact.variant, artifact);
    }
  }
  return latest;
};

test.describe.configure({ mode: 'serial' });

test('chat tone evaluation harness writes variant artifacts', async ({ page, request }) => {
  test.setTimeout(8 * 60_000);

  const scenarioFixture = await loadFixtureJson<ScenarioFixture>('scenarios.json');
  const recordFixture = await loadFixtureJson<RecordFixture>('public_record_samples.json');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const evalTitlePrefix = `[EVAL:${timestamp}] `;
  const runResults: ScenarioRunResult[] = [];

  await fs.mkdir(artifactDir, { recursive: true });

  let token = '';
  let selectedPatientId = -1;

  try {
    await login(page, E2E_EMAIL, E2E_PASSWORD);
    await page.getByRole('tab', { name: /dashboard/i }).click();
    const dashboardHeader = page.locator('.dashboard-header h1');
    await expect(dashboardHeader).toBeVisible({ timeout: 30_000 });
    await expect(dashboardHeader).not.toHaveText('Your health dashboard', { timeout: 30_000 });
    const selectedPatientName = (await dashboardHeader.textContent()) || '';

    token = await apiLogin(request);
    const patients = await listPatients(request, token);
    expect(patients.length > 0, 'No patient found for eval run').toBeTruthy();

    selectedPatientId = findPatientIdByName(patients, selectedPatientName) ?? patients[0].id;
    await cleanupEvalMemoryChunks(request, token, selectedPatientId);
    await cleanupEvalRecords(request, token, selectedPatientId, '[EVAL:');
    const seededRecords = await seedEvalRecords(
      request,
      token,
      selectedPatientId,
      recordFixture.records,
      evalTitlePrefix,
    );
    expect(seededRecords.length).toBe(recordFixture.records.length);
    const seededCheckResponse = await request.get(
      `${API_BASE}/api/v1/records/?patient_id=${selectedPatientId}&limit=1000`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(seededCheckResponse.ok(), `Seeded records check failed (${seededCheckResponse.status()})`).toBeTruthy();
    const seededRows = (await seededCheckResponse.json()) as Array<{ title: string }>;
    const seededVisibleInApi = seededRows.filter((row) => (row.title || '').startsWith(evalTitlePrefix));
    expect(seededVisibleInApi.length).toBeGreaterThanOrEqual(recordFixture.records.length);
    const indexedChunkCount = await seedEvalMemoryChunks(
      request,
      token,
      selectedPatientId,
      recordFixture.records,
    );
    expect(indexedChunkCount).toBeGreaterThan(0);
    const memoryChunks = await listPatientMemoryChunks(request, token, selectedPatientId);
    const evalMemoryChunks = memoryChunks.filter((chunk) => chunk.chunk_type === 'eval_fixture');
    expect(evalMemoryChunks.length).toBeGreaterThan(0);

    await page.getByRole('tab', { name: 'Chat' }).click();

    for (const scenario of scenarioFixture.scenarios) {
      const turns: TurnRunResult[] = [];
      for (const prompt of scenario.turns) {
        turns.push(await askViaChatInterface(page, prompt));
      }
      runResults.push({
        id: scenario.id,
        description: scenario.description,
        expectation: scenario.expectation,
        turns,
      });
    }

    const scores = scoreRuns(runResults, scenarioFixture.default_refusal_phrases);
    const allPriorScores = await readScoreArtifacts();
    const baselineArtifact = allPriorScores
      .filter((artifact) => artifact.variant === 'baseline_current')
      .sort((a, b) => (new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()))
      .pop();

    let baselineComparison: ScoreArtifact['baseline_comparison'] = null;
    let baselineGroundingRegression = false;
    if (PROMPT_PROFILE !== 'baseline_current' && baselineArtifact) {
      baselineGroundingRegression = (
        scores.grounding.score < baselineArtifact.scoring.grounding.score
        || scores.grounding.unsupported_numeric_claims
          > baselineArtifact.scoring.grounding.unsupported_numeric_claims
        || scores.grounding.refusal_policy_violations
          > baselineArtifact.scoring.grounding.refusal_policy_violations
      );
      baselineComparison = {
        baseline_variant: baselineArtifact.variant,
        baseline_timestamp: baselineArtifact.timestamp,
        grounding_regression: baselineGroundingRegression,
        naturalness_uplift: Number(
          (scores.naturalness.score - baselineArtifact.scoring.naturalness.score).toFixed(2),
        ),
      };
    }

    const hardFail = (
      scores.grounding.unsupported_numeric_claims > 0
      || scores.grounding.refusal_policy_violations > 0
      || baselineGroundingRegression
    );

    const artifactBase = `${PROMPT_PROFILE}-${timestamp}`;
    const transcriptPath = path.resolve(artifactDir, `${artifactBase}.json`);
    const scorePath = path.resolve(artifactDir, `${artifactBase}-score.json`);

    const transcriptPayload = {
      variant: PROMPT_PROFILE,
      timestamp: new Date().toISOString(),
      patient_id: selectedPatientId,
      scenario_count: runResults.length,
      scenarios: runResults,
    };

    const scorePayload = {
      variant: PROMPT_PROFILE,
      timestamp: new Date().toISOString(),
      scoring: scores,
      hard_fail: hardFail,
      baseline_comparison: baselineComparison,
      selection_rule: 'best naturalness uplift with zero grounding regression',
    };

    await fs.writeFile(transcriptPath, JSON.stringify(transcriptPayload, null, 2), 'utf-8');
    await fs.writeFile(scorePath, JSON.stringify(scorePayload, null, 2), 'utf-8');

    const refreshedScores = await readScoreArtifacts();
    const latestByVariant = latestArtifactsByVariant(refreshedScores);
    const baselineLatest = latestByVariant.get('baseline_current');
    const candidateSummaries = Array.from(latestByVariant.values()).map((artifact) => {
      const groundingRegression = (
        artifact.variant !== 'baseline_current'
        && Boolean(baselineLatest)
        && (
          artifact.scoring.grounding.score < (baselineLatest?.scoring.grounding.score ?? 0)
          || artifact.scoring.grounding.unsupported_numeric_claims
            > (baselineLatest?.scoring.grounding.unsupported_numeric_claims ?? 0)
          || artifact.scoring.grounding.refusal_policy_violations
            > (baselineLatest?.scoring.grounding.refusal_policy_violations ?? 0)
        )
      );
      return {
        variant: artifact.variant,
        timestamp: artifact.timestamp,
        hard_fail: artifact.hard_fail,
        grounding_regression: groundingRegression,
        grounding_score: artifact.scoring.grounding.score,
        naturalness_score: artifact.scoring.naturalness.score,
        ux_score: artifact.scoring.ux.score,
        naturalness_uplift_vs_baseline: baselineLatest
          ? Number((artifact.scoring.naturalness.score - baselineLatest.scoring.naturalness.score).toFixed(2))
          : null,
      };
    });
    const winner = candidateSummaries
      .filter((candidate) => candidate.variant !== 'baseline_current')
      .filter((candidate) => !candidate.hard_fail && !candidate.grounding_regression)
      .sort((a, b) => {
        const upliftA = a.naturalness_uplift_vs_baseline ?? Number.NEGATIVE_INFINITY;
        const upliftB = b.naturalness_uplift_vs_baseline ?? Number.NEGATIVE_INFINITY;
        if (upliftA !== upliftB) return upliftB - upliftA;
        if (a.ux_score !== b.ux_score) return b.ux_score - a.ux_score;
        const priorityA = winnerTieBreakPriority[a.variant] ?? Number.MAX_SAFE_INTEGER;
        const priorityB = winnerTieBreakPriority[b.variant] ?? Number.MAX_SAFE_INTEGER;
        return priorityA - priorityB;
      })[0] ?? null;
    const summaryPayload = {
      generated_at: new Date().toISOString(),
      baseline_variant: baselineLatest?.variant ?? null,
      baseline_timestamp: baselineLatest?.timestamp ?? null,
      winner_variant: winner?.variant ?? null,
      winner_reason: winner
        ? 'best naturalness uplift with zero grounding regression'
        : 'insufficient complete variant data',
      variants: candidateSummaries,
    };
    await fs.writeFile(
      path.resolve(artifactDir, 'latest-summary.json'),
      JSON.stringify(summaryPayload, null, 2),
      'utf-8',
    );

    if (ENFORCE_HARD_FAIL) {
      expect(
        hardFail,
        `Hard fail: grounding regression detected. See ${scorePath}`,
      ).toBeFalsy();
    }
  } finally {
    if (token && selectedPatientId > 0) {
      await cleanupEvalMemoryChunks(request, token, selectedPatientId);
      await cleanupEvalRecords(request, token, selectedPatientId, '[EVAL:');
    }
  }
});
