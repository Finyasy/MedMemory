import { describe, expect, it } from 'vitest';
import { buildDeterministicRecordSummary } from '../recordSummary';

const formatDate = () => 'Feb 18, 2026, 01:13 PM';

describe('buildDeterministicRecordSummary', () => {
  it('returns extractive bullets with numeric evidence', () => {
    const summary = buildDeterministicRecordSummary(
      {
        title: 'Pediatric annual checkup',
        record_type: 'general',
        created_at: '2026-02-18T13:13:00Z',
        content:
          'Blood pressure 106/68 mmHg, heart rate 74 bpm, height 144 cm, weight 38 kg. No acute concerns documented.',
      },
      formatDate,
    );

    expect(summary).toContain('Record summary from explicit note text');
    expect(summary).toContain('- Blood pressure 106/68 mmHg, heart rate 74 bpm, height 144 cm, weight 38 kg.');
    expect(summary).toContain('- No acute concerns documented.');
    expect(summary).toContain('Only statements present in the note are included above.');
  });

  it('returns a clear message when note text is missing', () => {
    const summary = buildDeterministicRecordSummary(
      {
        title: 'Untitled',
        record_type: 'general',
        created_at: '2026-02-18T13:13:00Z',
        content: '   ',
      },
      formatDate,
    );

    expect(summary).toContain('I could not find readable note text');
  });
});

