export type SupportedPatientLanguage = 'en' | 'sw';

const BASE_LANGUAGE: SupportedPatientLanguage = 'en';

type PatientStrings = {
  introPrompt: string;
  placeholder: string;
  disabledPlaceholder: string;
  disclaimer: string;
  languageLabel: string;
  autoSpeakLabel: string;
  autoSpeakHint: string;
  playReplyLabel: string;
  stopReplyLabel: string;
  startVoiceLabel: string;
  stopVoiceLabel: string;
  sendingVoiceLabel: string;
  transcriptTitle: string;
  transcriptHint: string;
  transcriptSendLabel: string;
  transcriptDiscardLabel: string;
  transcriptConfidenceLabel: string;
  transcriptLowConfidenceLabel: string;
  noSpeechSupport: string;
  sourcesLabel: string;
  emptyTitle: string;
  emptyBody: string;
  recentLabsLabel: string;
  medicationsLabel: string;
  abnormalValuesLabel: string;
  trendsEyebrow: string;
  trendsTitle: string;
  trendsSetupTitle: string;
  askQuestionLabel: string;
  dailyStepsTitle: string;
  latestStepsLabel: string;
  averageStepsLabel: string;
  totalStepsLabel: string;
  stepsUnit: string;
  stepsPerDayUnit: string;
};

const ENGLISH_STRINGS: PatientStrings = {
  introPrompt:
    'Ask about a specific report, lab value, medication, or date. I will only use what is in the record.',
  placeholder: 'Message MedMemory...',
  disabledPlaceholder: 'Select a patient to start chatting...',
  disclaimer: 'MedMemory can make mistakes. Verify important medical information.',
  languageLabel: 'Language',
  autoSpeakLabel: 'Auto-read replies',
  autoSpeakHint: 'Play responses aloud when available',
  playReplyLabel: 'Play reply aloud',
  stopReplyLabel: 'Stop audio',
  startVoiceLabel: 'Record voice question',
  stopVoiceLabel: 'Stop recording',
  sendingVoiceLabel: 'Transcribing voice note…',
  transcriptTitle: 'Review transcript',
  transcriptHint: 'Confirm the transcript before sending it to MedMemory.',
  transcriptSendLabel: 'Send transcript',
  transcriptDiscardLabel: 'Discard',
  transcriptConfidenceLabel: 'Transcription confidence',
  transcriptLowConfidenceLabel: 'Low confidence. Review carefully before sending.',
  noSpeechSupport: 'Speech playback is not available in this browser.',
  sourcesLabel: 'Sources',
  emptyTitle: 'How can I help you today?',
  emptyBody:
    'Ask questions about patient records, upload medical documents, or get insights from lab results.',
  recentLabsLabel: 'Recent lab results',
  medicationsLabel: 'Current medications',
  abnormalValuesLabel: 'Abnormal values',
  trendsEyebrow: 'Trends',
  trendsTitle: 'A1C over time',
  trendsSetupTitle: 'Trends setup',
  askQuestionLabel: 'Ask a question',
  dailyStepsTitle: 'Daily steps',
  latestStepsLabel: 'Latest steps',
  averageStepsLabel: '14-day average',
  totalStepsLabel: 'Total steps',
  stepsUnit: 'steps',
  stepsPerDayUnit: 'steps/day',
};

const SWAHILI_STRINGS: PatientStrings = {
  introPrompt:
    'Uliza kuhusu ripoti maalum, thamani ya maabara, dawa, au tarehe. Nitatumia tu kilicho kwenye rekodi.',
  placeholder: 'Andika ujumbe kwa MedMemory...',
  disabledPlaceholder: 'Chagua mgonjwa ili uanze gumzo...',
  disclaimer: 'MedMemory inaweza kukosea. Thibitisha taarifa muhimu za matibabu.',
  languageLabel: 'Lugha',
  autoSpeakLabel: 'Soma majibu kwa sauti',
  autoSpeakHint: 'Cheza majibu kwa sauti pale inapowezekana',
  playReplyLabel: 'Cheza jibu kwa sauti',
  stopReplyLabel: 'Simamisha sauti',
  startVoiceLabel: 'Rekodi swali la sauti',
  stopVoiceLabel: 'Acha kurekodi',
  sendingVoiceLabel: 'Inabadilisha sauti kuwa maandishi…',
  transcriptTitle: 'Kagua maandishi',
  transcriptHint: 'Thibitisha maandishi kabla ya kuyatuma kwa MedMemory.',
  transcriptSendLabel: 'Tuma maandishi',
  transcriptDiscardLabel: 'Tupa',
  transcriptConfidenceLabel: 'Uhakika wa maandishi',
  transcriptLowConfidenceLabel: 'Uhakika ni mdogo. Kagua kwa makini kabla ya kutuma.',
  noSpeechSupport: 'Kucheza sauti hakupatikani kwenye kivinjari hiki.',
  sourcesLabel: 'Vyanzo',
  emptyTitle: 'Ninawezaje kukusaidia leo?',
  emptyBody:
    'Uliza maswali kuhusu rekodi za mgonjwa, pakia nyaraka za matibabu, au pata mwongozo kutoka kwa matokeo ya maabara.',
  recentLabsLabel: 'Matokeo ya maabara ya karibuni',
  medicationsLabel: 'Dawa za sasa',
  abnormalValuesLabel: 'Thamani zisizo za kawaida',
  trendsEyebrow: 'Mienendo',
  trendsTitle: 'A1C kwa muda',
  trendsSetupTitle: 'Mpangilio wa mienendo',
  askQuestionLabel: 'Uliza swali',
  dailyStepsTitle: 'Hatua za kila siku',
  latestStepsLabel: 'Hatua za hivi karibuni',
  averageStepsLabel: 'Wastani wa siku 14',
  totalStepsLabel: 'Jumla ya hatua',
  stepsUnit: 'hatua',
  stepsPerDayUnit: 'hatua/siku',
};

type PatientLanguageConfig = {
  label: string;
  speechLocale: string;
  dateLocale: string;
  strings: Partial<PatientStrings>;
};

export const PATIENT_LANGUAGE_CONFIG: Record<SupportedPatientLanguage, PatientLanguageConfig> = {
  en: {
    label: 'English',
    speechLocale: 'en-US',
    dateLocale: 'en-US',
    strings: {},
  },
  sw: {
    label: 'Swahili',
    speechLocale: 'sw-KE',
    dateLocale: 'sw-KE',
    strings: SWAHILI_STRINGS,
  },
};

export const LANGUAGE_OPTIONS: Array<{ value: SupportedPatientLanguage; label: string }> = (
  Object.entries(PATIENT_LANGUAGE_CONFIG) as Array<[SupportedPatientLanguage, PatientLanguageConfig]>
).map(([value, config]) => ({
  value,
  label: config.label,
}));

const METRIC_LABELS: Record<string, Partial<Record<SupportedPatientLanguage, string>>> = {
  steps: { sw: 'Hatua' },
  step_count: { sw: 'Hatua' },
  'daily steps': { sw: 'Hatua za kila siku' },
  heart_rate: { sw: 'Mapigo ya moyo' },
  'heart rate': { sw: 'Mapigo ya moyo' },
  sleep: { sw: 'Usingizi' },
  sleep_hours: { sw: 'Masaa ya usingizi' },
  'sleep hours': { sw: 'Masaa ya usingizi' },
};

export const normalizePatientLanguage = (
  value?: string | null,
): SupportedPatientLanguage => {
  if (!value) return BASE_LANGUAGE;
  const normalized = value.trim().toLowerCase().replace('_', '-');
  const aliasMap: Record<string, SupportedPatientLanguage> = {
    en: 'en',
    eng: 'en',
    english: 'en',
    'en-us': 'en',
    sw: 'sw',
    swa: 'sw',
    swahili: 'sw',
    kiswahili: 'sw',
    'sw-ke': 'sw',
  };
  return aliasMap[normalized] ?? BASE_LANGUAGE;
};

export const getPatientStrings = (
  language: SupportedPatientLanguage,
): PatientStrings => ({
  ...ENGLISH_STRINGS,
  ...PATIENT_LANGUAGE_CONFIG[language].strings,
});

export const getSpeechLocaleForLanguage = (
  language: SupportedPatientLanguage,
): string => PATIENT_LANGUAGE_CONFIG[language].speechLocale;

export const getDateLocaleForLanguage = (
  language: SupportedPatientLanguage,
): string => PATIENT_LANGUAGE_CONFIG[language].dateLocale;

export const translateMetricName = (
  metricName: string,
  language: SupportedPatientLanguage,
): string => {
  if (language === 'en') return metricName;
  const normalized = metricName.trim().toLowerCase();
  return METRIC_LABELS[normalized]?.[language] ?? metricName;
};

export const buildMetricQuestion = (
  metricName: string,
  language: SupportedPatientLanguage,
): string => {
  const translatedMetric = translateMetricName(metricName, language);
  if (language === 'sw') {
    return `Fupisha ${translatedMetric} ukitumia rekodi za mgonjwa pekee. Jumuisha thamani ya hivi karibuni, kiwango cha marejeo, na kama iko ndani au nje ya kiwango. Kama ushahidi haupo, sema hujui.`;
  }
  return `Summarize ${translatedMetric} using only patient records. Include latest value, reference range, and whether it is in or out of range. If evidence is missing, say you do not know.`;
};
