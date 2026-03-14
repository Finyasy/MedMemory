# Clinician Portal v1 Polish Spec - March 2026

## Purpose

This spec translates the UI audit into a bounded first polish pass for the clinician portal.

It is not a full redesign.

It focuses on:

- improving hierarchy
- reducing visual clutter
- making the main task canvas more dominant
- keeping all current clinician workflows intact

Source audit:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/CLINICIAN_PORTAL_UI_UX_AUDIT_MAR_2026.md`

## Scope For This Pass

### In scope

- overview strip visual compression
- quick-action hierarchy cleanup
- calmer left rail and patient rail styling
- stronger center-canvas emphasis
- lighter card chrome across the clinician dashboard

### Out of scope

- new clinician workflow features
- copilot template logic changes
- chat behavior changes
- tabbed copilot redesign
- information architecture changes that require new API data

## Design Goals

1. The center workspace should become the obvious focal point.
2. Secondary rails should still be useful, but quieter.
3. Borders should stop competing with content.
4. The top of the page should read as one coherent dashboard header, not several unrelated boxes.

## Target Layout Behavior

### Before

- four equally loud stat cards
- action row with equal-weight buttons
- left rail and right rail visually compete with the center
- many orange outlines and similar cards

### After

- compressed overview strip with lighter surfaces
- one clear primary CTA
- quieter side rails
- stronger central quick-start/workspace canvas

## Planned UI Changes

### 1. Overview strip

- reduce vertical padding
- reduce border contrast
- keep metric accents, but tone down decorative dots and bars
- make each card feel like part of a compact status band rather than a standalone promo tile

### 2. Quick-action row

- separate secondary actions from the primary action
- keep `Open first active patient` visually dominant
- group `Link patient` and `Refresh queue` as quieter controls
- keep sync status visible but demoted

### 3. Left rail

- reduce card heaviness
- make queue and linking surfaces feel like utilities, not focal panels
- keep patient list readable, but use softer card treatment

### 4. Center canvas

- increase visual emphasis on the quick-start card and active workspace
- use cleaner surfaces and slightly larger internal spacing
- make the center panel read as the main operating area

### 5. Right patient rail

- reduce chrome and border noise
- keep patient identity and counts at the top
- make section cards more compact and less visually repetitive

## Implementation Notes

This pass should prefer:

- CSS-driven cleanup
- small markup changes only where needed for hierarchy
- no behavioral regressions

## Acceptance For This Pass

- clinician portal remains fully functional
- `./scripts/run_clinician_copilot_demo_check.sh` still passes
- the dashboard has a clearer primary focal point
- side rails feel quieter than the center
- the page looks less cluttered in screenshot review

## Documentation Follow-Up

If this pass lands, update:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/LESSONS_LEARNED.md`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/CLINICIAN_PORTAL_UI_UX_AUDIT_MAR_2026.md` if findings materially change

## Addendum - Follow-On v1 Polish

The first polish pass exposed two dense areas that still needed bounded cleanup without changing backend behavior:

- the copilot center column, which now uses grouped `Latest run`, `History`, and `Trace` tabs
- the right patient rail, which should keep one section expanded at a time and show compact summaries for `Documents`, `Records`, `Connections`, and `Dependents`
- the left rail, which should keep `Linked patients` primary while reducing `Patient queue`, `Link a patient`, and `Recent uploads` into denser utility surfaces
- the top overview and action strip, which should tighten and reflow earlier on narrower desktop widths so the three-column workspace starts sooner
- the center workspace, which should reduce copilot and chat spacing so the first meaningful patient context appears higher above the fold
- the queue and active patient status language, which should reuse one compact chip grammar across the header and left rail so readiness is easier to scan
- the right patient rail, which should reuse the same compact chip grammar for the selected-patient badge and resource counts so the full workspace reads as one system
- the patient-rail section interiors, which should keep section count badges and empty states as compact as the section headers so the rail stays scannable when expanded
- the patient-rail list rows, which should collapse status, date, and issue details into one compact metadata line under each title so expanded sections stay readable
- long sync/provider error text, which should truncate by default and expose an explicit `More/Less` pattern so compact rows do not become tall by accident
- connection rows and recent sync events, which should sort by attention level and carry one compact severity chip so failed items surface before healthy ones without adding more vertical chrome
- recent sync activity labels, which should use provider display names instead of raw slugs so the patient rail keeps one readable naming system throughout
- errored connection and sync rows, which should include a compact “needs attention” sublabel so clinicians understand the failure reason without expanding full error text
- the connections rail, which should offer an `Attention only` toggle so clinicians can temporarily filter both connection rows and sync activity down to items that need review
- the collapsed `Connections` section, which should surface review counts in the header/summary so clinicians can see attention load before expanding the rail
- the collapsed `Connections` attention badge, which should be clickable and open the section directly into the review-only state
- repeated provider names in the patient rail, which should live inside explicitly labeled lists so accessibility and browser-test selectors stay stable once the same provider appears in both connections and sync activity

These remain within the same v1 goal: reduce visual competition around the center workspace while keeping current workflows intact.
