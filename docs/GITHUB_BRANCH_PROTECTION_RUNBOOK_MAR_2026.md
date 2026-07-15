# MedMemory GitHub Branch Protection Runbook

Date: 2026-03-19

## Purpose

The clinician copilot demo gate now exists in repo, but GitHub still has to enforce it. This runbook captures the exact branch-protection step that cannot be completed from local code alone.

## Required Check

Workflow file:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`

Required status check name:

- `Clinician Copilot Demo Gate / clinician-copilot-demo-gate`

## GitHub UI Steps

1. Open the repository on GitHub.
2. Go to `Settings` -> `Branches`.
3. Create or edit the protection rule for `main`.
4. Enable:
   - `Require a pull request before merging`
   - `Require status checks to pass before merging`
5. Add this required check:
   - `Clinician Copilot Demo Gate / clinician-copilot-demo-gate`
6. Save the rule.

## Notes

- The workflow must have run at least once on GitHub before the check name becomes selectable in the UI.
- This repo change is necessary but not sufficient; branch protection is a GitHub setting, not a file in the repository.
- Keep the check name aligned with `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`.
