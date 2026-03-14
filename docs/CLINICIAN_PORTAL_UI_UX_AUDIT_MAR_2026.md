# Clinician Portal UI/UX Audit - March 2026

## Scope

This audit is based on the live local clinician portal running at:

- `http://127.0.0.1:5173/clinician`

Validation used:

- backend and frontend launched locally
- `./scripts/run_clinician_copilot_demo_check.sh` passed
- live screenshots captured under:
  - `artifacts/ui_audit/clinician-dashboard.png`
  - `artifacts/ui_audit/clinician-dashboard-expanded.png`
  - `artifacts/ui_audit/clinician-workspace.png`
  - `artifacts/ui_audit/clinician-workspace-patient-panel.png`

## Functional Status

The clinician portal is working on the current local build.

Verified working:

- clinician login
- active patient access flow
- quick open patient flow
- clinician copilot run creation
- persisted run rendering
- suggestion CTA click
- safe navigation from CTA to patient workspace sections

## High-Level UX Judgment

The portal is functional and understandable, but it is visually busier than it should be for a clinician-facing workflow.

The main issue is not broken interaction. The main issue is weak visual hierarchy across too many bordered surfaces competing for attention at the same time.

Current state:

- usable
- stable
- moderately cluttered
- not yet visually modern

## What Works

### 1. Clear operational framing

The top area communicates that this is a clinician-specific workspace, not the patient app.

### 2. Useful quick-start path

The "Open first active patient" action is correctly prominent and gives the user a direct path into work.

### 3. Bounded copilot behavior is visible

The copilot panel shows templates, trace, final answer, and suggestions in a way that matches the product safety model.

### 4. Patient context is present in parallel

The right-side panel gives the clinician persistent context while working in the main workspace.

## Where The UI Feels Cluttered

### 1. Too many boxed surfaces above the fold

The landing view has:

- status cards
- action bar
- left queue rail
- center quick-start card
- right patient panel

These are all bordered and similarly weighted. The page lacks one dominant focal point.

### 2. Borders are doing too much work

Almost every section uses a light orange outline. This creates a constant visual buzz and reduces the value of borders as a hierarchy signal.

### 3. The three-column workspace is dense

Once a patient is open, the left rail, center copilot area, right patient panel, and lower chat area all compete at once. The eye has to scan too many independent blocks.

### 4. The center column stacks too many concepts

In one vertical band, the user sees:

- template chooser
- prompt
- run history
- run trace
- suggestions
- chat composer

That is too much for a single continuous column without stronger grouping or tabs.

### 5. The patient panel is informative but visually flat

Documents, records, connections, and dependents all look too similar. Important clinical context is not visually elevated enough above secondary metadata.

### 6. Empty-state space is not being used well

The dashboard landing state still feels busy even though much of the central area has low information density.

## Screenshot-Based Notes

### Dashboard

From `artifacts/ui_audit/clinician-dashboard.png`:

- the top stats row is useful but oversized for the amount of information shown
- the left queue card and right patient panel both read as sidebars, but the center quick-start card does not sufficiently dominate them

### Expanded dashboard

From `artifacts/ui_audit/clinician-dashboard-expanded.png`:

- the checklist is good, but the card remains visually merged with the rest of the page
- the status chips are helpful, but the whole panel still competes with the side rails

### Patient workspace

From `artifacts/ui_audit/clinician-workspace.png`:

- the copilot flow is logically sound
- the run history and run trace occupy too much equal-weight card space
- the chat area sits too far below the main work surface and feels visually detached

### Patient panel state

From `artifacts/ui_audit/clinician-workspace-patient-panel.png`:

- the right panel is useful, but the stacked cards need stronger information hierarchy
- secondary areas like dependents should not visually compete with documents and records

## Modernization Direction

The right direction is not "more features on screen." It is less simultaneous chrome, stronger hierarchy, and progressive disclosure.

### Priority 1: Reduce surface count above the fold

- collapse the four stat cards into a single compact summary strip
- keep only one primary CTA in the action row
- reduce sidebar card count in the landing state

### Priority 2: Make the center column the clear primary workspace

- widen the central work area
- visually demote the left rail and right patient panel
- treat the center as the dominant task canvas

### Priority 3: Split copilot content into clearer groups

Recommended structure:

- top: template + prompt + run action
- middle tabs: `Latest run`, `History`, `Trace`
- bottom: clinician chat

This would remove the feeling of one long stack of unrelated cards.

### Priority 4: Rebuild the patient panel as a compact summary rail

Recommended order:

1. patient identity and status
2. counts and key alerts
3. documents and records
4. connections
5. dependents

Dependents should be collapsed by default unless they are relevant to the selected workflow.

### Priority 5: Use color more intentionally

- reserve orange for primary actions and active emphasis
- reduce orange border use across passive containers
- use neutral surfaces for most cards
- use green, blue, and amber only for actual status semantics

### Priority 6: Improve typography hierarchy

- larger section titles
- stronger contrast between heading, label, and helper text
- fewer all-caps labels
- more consistent spacing between title, subtitle, and action

## Concrete Design Changes Recommended For v1 Polish

### Layout

- change landing page from heavy three-column balance to `narrow rail / main canvas / compact summary rail`
- keep the patient panel narrower than the main canvas
- reduce top summary card height by roughly one third

### Components

- replace multiple bordered cards with quieter filled surfaces
- convert checklist and queue details into drawers or accordions
- make run history a compact list instead of full-height cards
- make run trace steps denser and easier to scan

### Copilot panel

- keep only the latest run visible by default
- move older runs into a collapsible history panel
- keep suggestions directly under the final answer
- put citations behind an expandable control if they are empty or repetitive

### Patient rail

- convert the right rail into a condensed summary with numeric badges
- show full section cards only when a clinician clicks into that section

### Chat area

- tighten vertical spacing
- reduce the empty band between workspace content and composer
- keep the composer more visually attached to the active patient context

## Suggested Design Principle

For the clinician portal, optimize for:

- one primary task at a time
- quick scanability
- minimal decorative chrome
- persistent but quiet patient context

The portal should feel operational, dense in information, and calm in presentation.

## Recommended Next UI Pass

Do these in order:

1. simplify the landing dashboard hierarchy
2. restructure the copilot center column into grouped sections or tabs
3. compress the patient summary rail
4. reduce border noise and rebalance typography
5. rerun screenshot audit before further feature additions

## Documentation Follow-Up

If UI changes are made from this audit, also update:

- `docs/LESSONS_LEARNED.md`
- `docs/DEMO_CHECKLIST.md` if the demo flow changes
- `docs/CLINICIAN_COPILOT_AGENT_V1_PLAN.md` if the workflow structure changes
