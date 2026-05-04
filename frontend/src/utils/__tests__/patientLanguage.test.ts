import { describe, expect, it } from 'vitest';

import {
  LANGUAGE_OPTIONS,
  normalizePatientLanguage,
  PATIENT_LANGUAGE_CONFIG,
} from '../patientLanguage';

describe('patientLanguage', () => {
  it('only exposes English and Swahili as patient-facing languages', () => {
    expect(LANGUAGE_OPTIONS.map((option) => option.value)).toEqual(['en', 'sw']);
    expect(Object.keys(PATIENT_LANGUAGE_CONFIG)).toEqual(['en', 'sw']);
  });

  it('falls back unsupported stored language preferences to English', () => {
    expect(normalizePatientLanguage('sw')).toBe('sw');
    expect(normalizePatientLanguage('kik')).toBe('en');
    expect(normalizePatientLanguage('luo')).toBe('en');
  });
});
