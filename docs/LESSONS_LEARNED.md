# Lessons Learned

This file captures implementation and operating lessons that should change how MedMemory is built, tested, and demoed.

## Clinician Copilot v1

Date: 2026-03-10

- If a UI element is part of the product plan, it must be functional. Placeholder CTAs are not acceptable for demo or release paths.
- Every important workflow needs both:
  - a scriptable smoke check
  - a browser-path smoke check
- Important fixes must update the nearest operational docs in the same change. For clinician copilot v1, that includes:
  - the implementation plan
  - the scripts README
  - the E2E README
- Demo readiness must be one command, not tribal knowledge. The current gate is:
  - `./scripts/run_clinician_copilot_demo_check.sh`
- Access-control fixes need regression coverage, especially when persisted records can outlive the original authorization event.
- Suggestion actions must remain safe and bounded:
  - navigational only
  - no implicit writes
  - no hidden side effects
- Screenshot-based UI audits are worth doing before clinician demos. Dense three-column operational layouts accumulate clutter quickly unless the main task canvas is kept visually dominant.
- For clinician UI polish, start with a bounded visual spec before touching CSS. Screenshot audit -> polish spec -> implementation is safer than styling ad hoc from memory.
- When a clinician workspace center column carries multiple job types at once, group them with tabs or progressive disclosure before adding more cards. `Latest run`, `History`, and `Trace` is a better v1 pattern than showing all copilot surfaces at the same time.
- In a three-column clinician layout, the right-side patient rail should not keep every subsection open at once. Secondary clinical context should collapse into short summaries by default so the copilot/chat center stays dominant.
- In the left rail, only the patient list should stay fully expanded by default. Queue status, link-patient utilities, and recent-upload activity should read as compact utilities unless the clinician explicitly opens them.
- The header needs its own responsive compression rules before the three-column workspace collapses. If overview cards and quick actions wait too long to stack or tighten, they consume too much vertical space and make the workspace feel pushed down.
- Once a patient workspace is open, the center column needs its own vertical budget. Copilot setup, chat header, and first-message spacing should be tightened so the user reaches actual conversation context without losing the bounded copilot controls.
- Repeated clinician status surfaces should share one compact grammar. Queue counts, active patient rows, and similar “is this actionable right now?” indicators are easier to scan when they reuse the same small chip language instead of inventing a new card treatment in each column.
- That same compact status grammar needs to extend across all three columns. The selected-patient badge and patient-rail counts should not fall back to a different badge style once the clinician opens a workspace.
- Section interiors should follow the same rule as section headers. If a patient-rail header uses compact chips, the section count badge and empty state inside it should stay equally terse; otherwise the rail starts dense again once a section opens.
- Patient-rail list items need one compact metadata row. Status, timestamp, and issue details should collapse into a single terse line under the title; stacked secondary lines make the rail look denser than it is.
- Long provider issues need explicit truncation and expansion. A compact row should stay compact by default; verbose sync errors should only expand when the clinician asks for the full text.
- Compact rows still need attention ordering. When provider connections or sync events mix healthy and failed states, the errored items should sort to the top and carry one severity chip; otherwise the clinician has to read every line to find the problem.
- The naming system has to stay human-readable inside compact rails. If one section uses full provider names and another falls back to raw slugs, the workspace stops feeling cohesive even when the layout is clean.
- Error rows also need a short human explanation before the raw issue text. A one-line “needs attention” reason lets the clinician understand the problem quickly while keeping the full technical error behind the existing expand pattern.
- Once a rail contains both healthy and unhealthy rows, it needs a temporary attention filter. Clinicians should be able to collapse the rail down to review-only items without losing the full list or adding a second page.
- If a section can be collapsed, its header still has to carry the review load. Clinicians should not have to open `Connections` just to discover there are items needing attention.
- If a collapsed header advertises review load, that signal should be actionable. The shortest path is to let the clinician click the review badge and land directly in the filtered review state.
- Local demo tooling should prefer an explicit loopback host when needed. If `localhost` resolves to IPv6 on the machine but the backend is bound to IPv4, rerun the demo gate with `--backend-url http://127.0.0.1:8000`.
- Repeated provider names across `Connections` and `Recent sync activity` need explicit accessible labels on each list. Without that, browser tests drift into brittle text-only selectors once the same provider appears in both places.
- Demo gates should validate the frontend shell before opening a browser test. If the local UI is stale or down, the runbook should offer one explicit recovery flag such as `--restart-frontend` instead of failing deep inside Playwright.
- The v1 boundary remains important:
  - bounded orchestration
  - typed read-only tools
  - evidence-grounded output
  - no open-ended agent loop

## Update Rule

Add an entry here whenever a change introduces or clarifies:

- a release or demo gate
- a safety boundary
- an access-control failure mode
- a required operational command
- a recurring implementation mistake worth preventing
