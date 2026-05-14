# iOS Patient Profile Recommendations (May 2026)

## Scope Reviewed

This recommendation is based on the current web patient experience, SwiftUI MVP, screenshots, and migration notes:

- Web profile source: `frontend/src/components/ProfileModal.tsx`
- Web dashboard/chat source: `frontend/src/App.tsx`, `frontend/src/components/dashboard/*`
- SwiftUI MVP source: `ios/MedMemoryHealthSyncMVP/*`
- Migration plan: `docs/SWIFTUI_PATIENT_APP_PLAN_MAR_2026.md`
- Visual references:
  - `artifacts/submission/medmemory-patient-dashboard-1280x720-final.png`
  - `artifacts/submission/medmemory-patient-chat-1280x720-final.png`
  - `frontend/e2e/visual.spec.ts-snapshots/dashboard-header-darwin.png`
  - `frontend/e2e/visual.spec.ts-snapshots/documents-panel-darwin.png`

## Summary Recommendation

Make the Swift iOS app a native patient companion, not a web clone. The app already has the right foundation: dashboard, chat, workspace, Apple Health sync, Keychain token storage, and backend wiring. The biggest missing product surface is the patient profile itself.

The next iOS milestone should be a native `Profile` tab or dashboard entry that lets patients review and update the profile data currently handled by the web modal: demographics, emergency contacts, allergies, conditions, family history, providers, lifestyle, language preference, and profile completion.

## Current Gap

The web profile is a complete patient-owned data management flow. It includes:

- Basic information: name, date of birth, sex, blood type, height, weight, phone, email, address, preferred language
- Emergency contacts
- Allergies with type, severity, and reaction
- Conditions with status and diagnosed date
- Family history
- Providers and pharmacies
- Lifestyle inputs
- Completion percentage
- Loading, retry, error, and save states

The SwiftUI app currently fetches only a lightweight `PatientProfileSummaryDTO` with `id`, `full_name`, `age`, and `date_of_birth`. That is enough for headers, but not enough for native profile parity.

## Recommended iOS Information Architecture

Use a bottom `TabView` with five patient-level destinations:

1. `Dashboard`
2. `Chat`
3. `Workspace`
4. `Profile`
5. `Sync`

If five tabs feels too crowded after testing, keep `Profile` as a prominent dashboard card and toolbar avatar destination. Do not bury it inside Sync/settings because profile data directly improves chat quality, emergency readiness, and dashboard personalization.

## Profile Screen Design

Build `PatientProfileView` as a native grouped form with a compact summary header.

Top header:

- Initials avatar matching the web profile modal
- Full name
- Age, sex, blood type when available
- Completion ring or linear progress
- Last updated status if backend supports it later

Sections:

- Identity
- Contact
- Emergency
- Medical
- Family History
- Care Team
- Lifestyle
- Language

Use native `NavigationLink` drill-ins for multi-item sections such as allergies, conditions, family history, and providers. Avoid recreating the web modal tabs exactly; on iPhone, drill-in lists and sheets are clearer than horizontal tab bars inside a long form.

## Data/API Recommendations

Extend the Swift DTO layer to support the full profile response already exposed by the backend:

- Add `FullPatientProfileDTO`
- Add `EmergencyContactDTO`
- Add `AllergyDTO`
- Add `ConditionDTO`
- Add `FamilyHistoryDTO`
- Add `ProviderDTO`
- Add `LifestyleDTO`
- Add `ProfileCompletionDTO`

Add `MedMemoryBackendClient` methods for the same profile endpoints used by the web:

- `GET /api/v1/profile?patient_id={id}`
- `PUT /api/v1/profile/basic?patient_id={id}`
- `POST /api/v1/profile/emergency-contacts?patient_id={id}`
- `DELETE /api/v1/profile/emergency-contacts/{contact_id}?patient_id={id}`
- `POST /api/v1/profile/allergies?patient_id={id}`
- `DELETE /api/v1/profile/allergies/{allergy_id}?patient_id={id}`
- `POST /api/v1/profile/conditions?patient_id={id}`
- `DELETE /api/v1/profile/conditions/{condition_id}?patient_id={id}`
- `POST /api/v1/profile/family-history?patient_id={id}`
- `DELETE /api/v1/profile/family-history/{history_id}?patient_id={id}`
- `POST /api/v1/profile/providers?patient_id={id}`
- `DELETE /api/v1/profile/providers/{provider_id}?patient_id={id}`
- `PUT /api/v1/profile/lifestyle?patient_id={id}`

Keep profile writes small and section-scoped, matching the web model. This keeps retry and validation behavior manageable on mobile.

## UX Improvements For The Existing Swift App

### Dashboard

The Swift dashboard should move from placeholder guidance toward patient-specific status:

- Show profile completion as one of the top summary cards.
- Show highest-risk allergy or active condition when present.
- Use the web highlight logic for out-of-range metrics, confidence, freshness, and provider source.
- Add quick actions: `Ask`, `Upload`, `Sync`, `Update profile`.

### Chat

The web screenshots emphasize a calm, sparse chat surface. Keep that, but add patient-specific affordances:

- Show citation badges as tappable source chips, not just a count.
- Add suggested questions from profile context, such as medications, recent labs, allergies, or family history.
- Preserve the refusal behavior: if information is not in records, say so clearly.
- Use the patient's preferred language from profile in the chat request flow.

### Workspace

The current Swift workspace correctly uses native upload and add-record actions. Improve it by:

- Adding document detail previews.
- Showing processing status and failure reasons.
- Adding camera scan as a first-class action.
- Grouping records by type/date instead of only showing the five most recent items.

### Sync

Keep Sync focused on native capabilities:

- HealthKit permission status
- Last sync result
- Background sync controls when implemented
- Token/session state

Move general profile editing out of Sync.

## Visual Direction From Screenshots

Carry forward these visual cues from the web images:

- Warm neutral background
- Orange primary action color
- Soft cards with light borders
- Initials/avatar treatment for identity
- Compact uppercase labels
- Calm empty states

Adjust for iOS:

- Reduce oversized card radius; use `12-16pt` for repeated rows and `18-20pt` for major grouped panels.
- Prefer SF Symbols over emoji icons for profile sections.
- Use native `Form`, `List`, `sheet`, `confirmationDialog`, and `NavigationStack` behavior where it improves accessibility and editing.
- Keep cards purposeful. Avoid stacking cards inside cards for long profile forms.

## Implementation Priority

### P0: Full profile read-only

- Add full profile DTOs.
- Fetch full profile in `HealthSyncViewModel`.
- Add `PatientProfileView`.
- Show demographics, completion, allergies, active conditions, emergency contacts, providers, and lifestyle read-only.

### P1: Core edits

- Edit identity/contact/language.
- Add/delete emergency contacts.
- Add/delete allergies.
- Add/delete conditions.

### P2: Profile-informed app behavior

- Use preferred language in chat.
- Add dashboard profile-completion card.
- Add suggested chat prompts based on missing or high-value profile fields.
- Add emergency summary card.

### P3: Production polish

- Offline cached profile snapshot.
- Conflict-safe refresh after saves.
- Field-level validation messages.
- Analytics for profile completion and failed saves.
- Accessibility pass for Dynamic Type, VoiceOver labels, and touch targets.

## Suggested File Changes

Start with these files:

- `ios/MedMemoryHealthSyncMVP/Models.swift`: add full profile DTOs and profile update payloads.
- `ios/MedMemoryHealthSyncMVP/MedMemoryBackendClient.swift`: add profile fetch/update methods.
- `ios/MedMemoryHealthSyncMVP/HealthSyncViewModel.swift`: add profile state, loading, save, add, delete, and refresh flows.
- `ios/MedMemoryHealthSyncMVP/PatientProfileView.swift`: new native profile screen.
- `ios/MedMemoryHealthSyncMVP/MedMemoryHealthSyncApp.swift` or `ContentView.swift`: add Profile tab or dashboard route.
- `ios/MedMemoryHealthSyncMVP/DesignSystem.swift`: add section row styles and compact status pills.

## Recommendation

Build the native patient profile next. It is the highest-leverage improvement because it closes the biggest parity gap with the website, improves the quality of grounded chat, makes emergency data accessible on-device, and gives the iOS app a clear patient-owned purpose beyond HealthKit sync.
