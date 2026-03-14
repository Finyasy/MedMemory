import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api';
import type { ClinicianAgentCitation, ClinicianAgentRun, ClinicianAgentRunSummary } from '../../types';

type TemplateKey = 'chart_review' | 'trend_review' | 'med_reconciliation' | 'data_quality';
type CopilotViewKey = 'latest' | 'history' | 'trace';

type ClinicianCopilotPanelProps = {
  patientId: number;
  patientName: string;
  onError: (title: string, error: unknown) => void;
  onNavigate: (actionTarget: string) => void;
  pushToast: (tone: 'success' | 'error' | 'info', message: string) => void;
};

const TEMPLATE_OPTIONS: Array<{
  key: TemplateKey;
  label: string;
  description: string;
  prompt: string;
}> = [
  {
    key: 'chart_review',
    label: 'Chart review',
    description: 'Summarize the current chart, surface missing evidence, and prepare a note outline.',
    prompt: 'Review this chart and surface the most important evidence for a clinician handoff.',
  },
  {
    key: 'trend_review',
    label: 'Trend review',
    description: 'Check comparable lab trends and call out meaningful directional changes.',
    prompt: 'Review the available lab trends and summarize the clinically relevant changes.',
  },
  {
    key: 'med_reconciliation',
    label: 'Med reconciliation',
    description: 'Summarize active medications, recent changes, and supporting record context.',
    prompt: 'Review active medications, recent changes, and supporting evidence for reconciliation.',
  },
  {
    key: 'data_quality',
    label: 'Data quality',
    description: 'Inspect provider sync health and determine whether missing data may reflect sync issues.',
    prompt: 'Review provider sync health and identify any data quality issues that could affect interpretation.',
  },
];

const formatDate = (value?: string | null) => {
  if (!value) return 'Just now';
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

export default function ClinicianCopilotPanel({
  patientId,
  patientName,
  onError,
  onNavigate,
  pushToast,
}: ClinicianCopilotPanelProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateKey>('chart_review');
  const [prompt, setPrompt] = useState(TEMPLATE_OPTIONS[0].prompt);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [history, setHistory] = useState<ClinicianAgentRunSummary[]>([]);
  const [activeRun, setActiveRun] = useState<ClinicianAgentRun | null>(null);
  const [activeView, setActiveView] = useState<CopilotViewKey>('latest');

  const selectedTemplateConfig = useMemo(
    () => TEMPLATE_OPTIONS.find((item) => item.key === selectedTemplate) ?? TEMPLATE_OPTIONS[0],
    [selectedTemplate],
  );

  useEffect(() => {
    setPrompt(selectedTemplateConfig.prompt);
  }, [selectedTemplateConfig]);

  useEffect(() => {
    let cancelled = false;
    setActiveView('latest');
    setIsLoadingHistory(true);
    api.listClinicianAgentRuns(patientId, 6)
      .then(async (runs) => {
        if (cancelled) return;
        setHistory(runs);
        if (!runs.length) {
          setActiveRun(null);
          return;
        }
        const detail = await api.getClinicianAgentRun(runs[0].id);
        if (!cancelled) {
          setActiveRun(detail);
          setActiveView('latest');
        }
      })
      .catch((error) => {
        if (cancelled) return;
        onError('Failed to load clinician copilot history', error);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, onError]);

  const handleRun = async () => {
    if (!prompt.trim()) return;
    setIsSubmitting(true);
    try {
      const run = await api.createClinicianAgentRun({
        patient_id: patientId,
        template: selectedTemplate,
        prompt: prompt.trim(),
      });
      setActiveRun(run);
      setActiveView('latest');
      setHistory((previous) => [
        {
          id: run.id,
          patient_id: run.patient_id,
          clinician_user_id: run.clinician_user_id,
          template: run.template,
          prompt: run.prompt,
          status: run.status,
          final_answer_preview: run.final_answer?.slice(0, 220) ?? null,
          safety_flags: run.safety_flags,
          created_at: run.created_at,
          completed_at: run.completed_at ?? null,
        },
        ...previous.filter((item) => item.id !== run.id).slice(0, 5),
      ]);
      pushToast('success', `${selectedTemplateConfig.label} completed for ${patientName}.`);
    } catch (error) {
      onError('Failed to run clinician copilot', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectHistory = async (runId: number) => {
    try {
      const run = await api.getClinicianAgentRun(runId);
      setActiveRun(run);
      setActiveView('latest');
    } catch (error) {
      onError('Failed to load copilot run details', error);
    }
  };

  const renderCitationLabel = (citation: ClinicianAgentCitation) => {
    const label = citation.label || citation.source_type;
    return citation.detail ? `${label}: ${citation.detail}` : label;
  };

  const hasActiveRun = activeRun !== null;

  return (
    <section className="clinician-copilot-panel clinician-panel-card" aria-label="Clinician copilot">
      <div className="clinician-copilot-header">
        <div>
          <p className="clinician-copilot-kicker">Clinician Copilot</p>
          <h3>Evidence-backed workflow</h3>
          <p className="clinician-copilot-text">
            Suggest-only, bounded orchestration for chart review. No automatic writes or sync actions.
          </p>
        </div>
        <span className="clinician-copilot-badge">{patientName}</span>
      </div>

      <div className="clinician-copilot-template-grid">
        {TEMPLATE_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            className={`clinician-copilot-template ${selectedTemplate === option.key ? 'active' : ''}`}
            onClick={() => setSelectedTemplate(option.key)}
          >
            <strong>{option.label}</strong>
            <span>{option.description}</span>
          </button>
        ))}
      </div>

      <label className="clinician-copilot-input-label">
        Scoped prompt
        <textarea
          className="clinician-copilot-textarea"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={3}
          placeholder={selectedTemplateConfig.prompt}
        />
      </label>

      <div className="clinician-copilot-actions">
        <button
          type="button"
          className="primary-button"
          onClick={handleRun}
          disabled={isSubmitting || prompt.trim().length < 3}
        >
          {isSubmitting ? 'Running…' : `Run ${selectedTemplateConfig.label}`}
        </button>
        <span className="clinician-copilot-hint">
          Fixed tools only. Results are persisted with a step trace and citations.
        </span>
      </div>

      <div className="clinician-copilot-tab-bar" role="tablist" aria-label="Clinician copilot views">
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'latest'}
          className={`clinician-copilot-tab ${activeView === 'latest' ? 'active' : ''}`}
          onClick={() => setActiveView('latest')}
        >
          Latest run
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'history'}
          className={`clinician-copilot-tab ${activeView === 'history' ? 'active' : ''}`}
          onClick={() => setActiveView('history')}
        >
          History
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeView === 'trace'}
          className={`clinician-copilot-tab ${activeView === 'trace' ? 'active' : ''}`}
          onClick={() => setActiveView('trace')}
          disabled={!hasActiveRun}
        >
          Trace
        </button>
      </div>

      <div className="clinician-copilot-tab-panel">
        {activeView === 'history' && (
          <div className="clinician-copilot-history clinician-copilot-pane">
            <div className="clinician-copilot-subheader">
              <h4>Recent runs</h4>
              <span>{isLoadingHistory ? 'Loading…' : history.length}</span>
            </div>
            {history.length === 0 ? (
              <p className="clinician-empty clinician-empty-friendly">No copilot runs yet for this patient.</p>
            ) : (
              <ul className="clinician-copilot-history-list">
                {history.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`clinician-copilot-history-item ${activeRun?.id === item.id ? 'active' : ''}`}
                      onClick={() => void handleSelectHistory(item.id)}
                    >
                      <strong>{item.template.replace(/_/g, ' ')}</strong>
                      <span>{formatDate(item.created_at)}</span>
                      <span>{item.final_answer_preview || item.prompt}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {activeView === 'latest' && (
          <div className="clinician-copilot-result clinician-copilot-pane">
            {!activeRun ? (
              <p className="clinician-empty clinician-empty-friendly">
                Select a patient task above to generate a bounded copilot run.
              </p>
            ) : (
              <>
                <div className="clinician-copilot-subheader">
                  <h4>Latest run</h4>
                  <span>{activeRun.status}</span>
                </div>
                <div className="clinician-copilot-run-meta">
                  <span>{activeRun.template.replace(/_/g, ' ')}</span>
                  <span>{formatDate(activeRun.completed_at ?? activeRun.created_at)}</span>
                </div>
                <p className="clinician-copilot-final-answer">{activeRun.final_answer}</p>

                {activeRun.citations.length > 0 && (
                  <div className="clinician-copilot-citations">
                    <div className="clinician-copilot-subheader">
                      <h4>Citations</h4>
                      <span>{activeRun.citations.length}</span>
                    </div>
                    <div className="clinician-copilot-chip-row">
                      {activeRun.citations.map((citation, index) => (
                        <span key={`run-citation-${index}`} className="clinician-copilot-chip">
                          {renderCitationLabel(citation)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {activeRun.safety_flags.length > 0 && (
                  <div className="clinician-copilot-flags">
                    {activeRun.safety_flags.map((flag) => (
                      <span key={flag} className="clinician-copilot-flag">{flag.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                )}

                {activeRun.suggestions.length > 0 && (
                  <div className="clinician-copilot-suggestions">
                    <div className="clinician-copilot-subheader">
                      <h4>Suggestions</h4>
                      <span>{activeRun.suggestions.length}</span>
                    </div>
                    <ul className="clinician-copilot-suggestion-list">
                      {activeRun.suggestions.map((suggestion) => (
                        <li key={suggestion.id} className="clinician-copilot-suggestion-item">
                          <strong>{suggestion.title}</strong>
                          <p>{suggestion.description}</p>
                          {suggestion.citations.length > 0 && (
                            <div className="clinician-copilot-chip-row">
                              {suggestion.citations.map((citation, index) => (
                                <span key={`${suggestion.id}-${index}`} className="clinician-copilot-chip">
                                  {renderCitationLabel(citation)}
                                </span>
                              ))}
                            </div>
                          )}
                          {suggestion.action_label && (
                            <button
                              type="button"
                              className="ghost-button compact clinician-copilot-suggestion-action-button"
                              onClick={() => {
                                if (suggestion.action_target) {
                                  onNavigate(suggestion.action_target);
                                }
                              }}
                              disabled={!suggestion.action_target}
                            >
                              {suggestion.action_label}
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeView === 'trace' && (
          <div className="clinician-copilot-result clinician-copilot-pane">
            {!activeRun ? (
              <p className="clinician-empty clinician-empty-friendly">
                Run a bounded copilot task first to inspect the step trace.
              </p>
            ) : (
              <>
                <div className="clinician-copilot-subheader">
                  <h4>Run trace</h4>
                  <span>{activeRun.steps.length} steps</span>
                </div>
                <div className="clinician-copilot-run-meta">
                  <span>{activeRun.template.replace(/_/g, ' ')}</span>
                  <span>{activeRun.status}</span>
                </div>
                {activeRun.steps.length > 0 ? (
                  <ol className="clinician-copilot-step-list">
                    {activeRun.steps.map((step) => (
                      <li key={step.id} className="clinician-copilot-step-item">
                        <div className="clinician-copilot-step-header">
                          <strong>{step.step_order}. {step.title}</strong>
                          <span>{step.status}</span>
                        </div>
                        {step.output_summary && <p>{step.output_summary}</p>}
                        {step.citations.length > 0 && (
                          <div className="clinician-copilot-chip-row">
                            {step.citations.map((citation, index) => (
                              <span key={`${step.id}-${index}`} className="clinician-copilot-chip">
                                {citation.label || citation.source_type}
                              </span>
                            ))}
                          </div>
                        )}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="clinician-empty clinician-empty-friendly">No trace steps were recorded for this run.</p>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
