# MedPics-Inspired Product Recommendations for MedMemory
Date: February 17, 2026
Source: Visual review of images in `/Users/bryan.bosire/anaconda_projects/MedMemory/MedPics`

## Goal
Translate the strongest ideas from MedPics into implementation-ready recommendations for MedMemory, while preserving your existing hallucination-safety and evidence-grounding direction.

## Key Product Patterns Observed
1. Unified data surface: records from multiple providers shown in one place with connection status.
2. Fast health state summary: in-range vs out-of-range counts at top-level.
3. Highlights-first dashboard: top few metrics and plain-language summary before deep detail.
4. Metric detail pages: value, normal range position, trend chart, and plain-language explanation.
5. Contextual AI chat: answers are tied to user-specific metrics (not generic education text).
6. Actionable insight cards: what changed, why it matters, what to do next.
7. Continuous monitoring: users track a short watchlist and get notified on important changes.

## Recommendations (Prioritized)

### P0: Ship first (high impact, low-to-medium complexity)

#### 1) Build a "Connections Hub" with sync status
Requirements:
- Must let users connect healthcare/lab sources from a searchable list.
- Must show status per source: `Connected`, `Last updated`, `Sync in progress`, `Error`.
- Must support manual re-sync per source.
- Must maintain sync audit trail for user trust.

Implementation notes:
- Backend: add provider connection model + sync job status endpoint.
- Frontend: a modal/sheet with source list and status pills (connected/not connected).
- Add background incremental sync scheduler (delta fetch where possible).

Acceptance:
- User can connect/disconnect a source without backend restarts.
- Dashboard reflects latest sync timestamp within one refresh cycle.

#### 2) Add a "Health Highlights" strip on dashboard
Requirements:
- Must show counts: `Out of range`, `In range`.
- Must show top 3-5 flagged metrics with latest value, unit, date, and direction.
- Must be computed from explicit record values only (no inferred values).

Implementation notes:
- Add daily materialized summary table for latest metric states.
- Rank highlights by severity + recency + trend delta.
- Keep this deterministic (no LLM needed for initial highlight list).

Acceptance:
- Counts match underlying records for sampled users.
- Highlight list updates after new ingestion completes.

#### 3) Add metric detail pages (value + range + trend + explanation)
Requirements:
- Must show current value against reference range.
- Must show trend over time with clear date axis.
- Must include a short plain-language "About this metric" section.
- Must include direct source references for displayed values.

Implementation notes:
- Build `MetricDetail` API: latest value, ranges, historical points, source IDs.
- Use existing RAG evidence model for explanation text; enforce citation mode for numeric claims.
- Reuse chart component across LDL/HbA1c/BP/etc.

Acceptance:
- Every displayed number can be traced to a document/record ID.
- Explanation refuses when evidence is missing.

#### 4) Add "Watchlist + Alerts" for selected metrics
Requirements:
- Must let users star metrics to monitor.
- Must notify on threshold crossing, sharp trend changes, or newly abnormal values.
- Must link each alert to underlying evidence (record/date/source).

Implementation notes:
- Add watchlist rules table (`metric`, `threshold`, `direction`, `channel`).
- Trigger alerts post-ingestion and post-recompute.
- Start with in-app notifications; add email/webhook later.

Acceptance:
- Alerts fire once per qualifying event (no duplicates).
- Alert details include metric, old/new value, and source reference.

### P1: Next wave (high impact, medium complexity)

#### 5) Improve AI responses with "context cards"
Requirements:
- Must return response sections: `What changed`, `Why it matters`, `Suggested next discussion points`.
- Must include citation markers for each numeric statement.
- Must clearly separate record-grounded output from general medical background.

Implementation notes:
- Add a structured response schema for "metric coaching" mode.
- Route questions like "How is my LDL?" directly to metric-aware templates.
- Keep strict refusal policy when source evidence is missing.

Acceptance:
- No uncited numeric claims in these responses.
- UX shows source chips/links under each section.

#### 6) Add "family-history and risk context" overlay
Requirements:
- Should allow users to input family-history risk factors.
- Should prioritize dashboard highlights using both measured values and risk profile.
- Must label this as risk-context prioritization, not diagnosis.

Implementation notes:
- Add user profile fields for family history and long-term risk concerns.
- Compute a transparent "watch priority" score.

Acceptance:
- Highlight ordering changes when risk profile changes.
- UI explains why a metric is prioritized.

### P2: Strategic differentiators (higher complexity)

#### 7) Provider-normalized timeline
Requirements:
- Should normalize units/reference ranges across providers.
- Should merge same metric names from different labs into one timeline.
- Must preserve original raw value and source metadata.

Acceptance:
- Users can see one timeline per metric across providers.
- Raw and normalized values are both available.

#### 8) Source quality and confidence indicators
Requirements:
- Should score extraction quality and data freshness per source.
- Must degrade gracefully (show low confidence) when OCR quality is weak.

Acceptance:
- Low-confidence values are visibly marked and excluded from automatic insights by default.

## UX and Visual Direction to Borrow
1. Compact top summary with counts (in-range/out-of-range).
2. Card-based highlights with small trend glyphs.
3. One-tap transition from highlight card to full metric detail.
4. Clean provider connection list with immediate status affordances.
5. Conversational entry point directly from metrics (quick prompts like "How's my LDL?").

## Guardrails to Preserve (critical)
1. Keep fail-closed behavior for missing evidence.
2. Keep deterministic decoding defaults for factual flows.
3. Require citations for numeric claims in clinician mode and high-stakes user flows.
4. Never generate recommendation text without explicit value/date/source backing.

## Suggested Delivery Plan (6 weeks)
1. Week 1-2: Connections Hub + ingestion/sync status APIs.
2. Week 2-3: Highlights summary computation + dashboard cards.
3. Week 3-4: Metric detail API + UI pages + source traceability.
4. Week 4-5: Watchlist/alerts + notification center.
5. Week 5-6: Context-card AI responses + risk-priority overlay.

## Success Metrics
1. Time-to-first-insight after login.
2. Percentage of AI numeric statements with valid source references.
3. Reduction in "no evidence" user retries for common metric queries.
4. Weekly active users opening metric detail pages.
5. Alert engagement rate (open + follow-up action).
