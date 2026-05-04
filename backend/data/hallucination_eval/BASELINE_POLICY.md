# Hallucination Baseline Policy

This folder stores the committed regression baseline used by CI:
`baseline_metrics_summary.json`.

## Update Rules

1. Only update the baseline after:
   - running `scripts/evaluate_rag_hallucination.py` on the committed eval set,
   - confirming gate pass with current CI thresholds,
   - reviewing the diff in a pull request.
2. Never update baseline and relax thresholds in the same commit unless a reviewer
   explicitly approves both changes.
3. Keep minimum coverage:
   - global `n_examples >= 22`
   - task coverage:
     - `numeric_grounding >= 4`
     - `numeric_citation >= 4`
     - `question_mode >= 4`
     - `context_gate >= 5`
     - `trend_direct >= 5`
4. Record the source command in PR description when baseline changes.

## Baseline Refresh Commands

```bash
cd backend
uv run python scripts/evaluate_rag_hallucination.py \
  --eval-file data/hallucination_rag_eval/eval.jsonl \
  --output-dir artifacts/hallucination_eval/current \
  --scope baseline \
  --min-policy-pass-rate 1.0
cp artifacts/hallucination_eval/current/metrics_summary.json \
  data/hallucination_eval/baseline_metrics_summary.json
```
