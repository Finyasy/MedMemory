import type { MedicalRecord } from '../types';

const MAX_RECORD_CHARS = 900;
const MAX_BULLETS = 4;

const normalizeText = (text: string) => text.replace(/\s+/g, ' ').trim();

const toSentence = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return '';
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
};

const pickEvidenceBullets = (content: string) => {
  const clipped =
    content.length > MAX_RECORD_CHARS ? `${content.slice(0, MAX_RECORD_CHARS).trimEnd()}…` : content;
  const sentences = clipped
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  const numeric = sentences.filter((sentence) => /\d/.test(sentence));
  const narrative = sentences.filter((sentence) => !/\d/.test(sentence));

  const merged = [...numeric, ...narrative];
  const seen = new Set<string>();
  const picked: string[] = [];
  for (const sentence of merged) {
    const normalized = sentence.toLowerCase();
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    const terminal = toSentence(sentence);
    if (terminal) picked.push(terminal);
    if (picked.length >= MAX_BULLETS) break;
  }

  if (picked.length) return picked;
  const fallback = toSentence(clipped);
  return fallback ? [fallback] : [];
};

export const buildDeterministicRecordSummary = (
  record: Pick<MedicalRecord, 'title' | 'record_type' | 'created_at' | 'content'>,
  formatDate: (date: string) => string,
) => {
  const title = record.title?.trim() || 'Latest record';
  const normalizedContent = normalizeText(record.content || '');

  if (!normalizedContent) {
    return `I could not find readable note text in "${title}". Add a fuller note, then try again.`;
  }

  const metadata: string[] = [];
  if (record.record_type?.trim()) {
    metadata.push(record.record_type.trim().replace(/_/g, ' '));
  }
  if (record.created_at) {
    metadata.push(formatDate(record.created_at));
  }

  const heading = metadata.length ? `${title} (${metadata.join(' · ')})` : title;
  const bullets = pickEvidenceBullets(normalizedContent);
  const bulletText = bullets.map((line) => `- ${line}`).join('\n');
  return `Record summary from explicit note text: ${heading}\n${bulletText}\n\nOnly statements present in the note are included above.`;
};

