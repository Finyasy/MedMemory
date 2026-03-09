# MedMemory HealthKit Step Sync MVP (SwiftUI)

This is a minimal iPhone-side SwiftUI scaffold for:

- syncing Apple Health `stepCount` daily totals into the MedMemory backend endpoint
- starting a native patient app shell that mirrors the MedMemory patient experience

- `POST /api/v1/integrations/apple-health/patient/{patient_id}/steps/sync`

## What this MVP does

- Requests HealthKit read access for `stepCount`
- Reads daily step totals for the last `N` days
- Sends the totals to MedMemory (idempotent upsert by date)
- Shows sync result counts (`inserted`, `updated`, `unchanged`)
- Issues a short-lived patient-scoped mobile token and stores it in Keychain
- Includes an initial native patient shell with:
  - Dashboard tab
  - Chat tab wired to `/chat/ask`
  - Workspace tab
  - Sync/settings tab

## What this MVP does not do yet

- Background sync (`HKObserverQuery`)
- Anchored incremental sync (`HKAnchoredObjectQuery`)
- Token refresh / secure auth storage (use Keychain next)
- Production error analytics / retries with backoff

## Files

- `MedMemoryHealthSyncApp.swift` - app entry point
- `ContentView.swift` - UI for config + sync
- `DesignSystem.swift` - reusable colors, cards, and button styles
- `PatientDashboardView.swift` - native patient dashboard shell
- `PatientChatPrototypeView.swift` - patient chat view wired to backend chat
- `PatientWorkspaceView.swift` - records/documents workspace shell
- `SyncSettingsView.swift` - backend + HealthKit sync configuration
- `KeychainTokenStore.swift` - secure token storage on device
- `PatientExperienceModels.swift` - lightweight UI model types
- `HealthKitManager.swift` - HealthKit auth + daily steps query
- `MedMemoryBackendClient.swift` - posts to MedMemory API
- `HealthSyncViewModel.swift` - orchestration/state
- `Models.swift` - request/response payloads

## Xcode setup (required)

1. Create a new **iOS App** project in Xcode (SwiftUI, Swift).
2. Copy these files into the project.
3. Enable **Signing & Capabilities**:
   - Add `HealthKit`
4. Add `Info.plist` usage strings:
   - `NSHealthShareUsageDescription` = `MedMemory uses your step count to show trends in your dashboard.`
   - `NSHealthUpdateUsageDescription` = `Not required for read-only sync; only add if you later write data.`
5. Run on a **real iPhone** (HealthKit is limited in the simulator).

## Backend connectivity note

If your MedMemory backend runs on your Mac at `http://localhost:8000`, your iPhone cannot use `localhost`.
Use your Mac's LAN IP (example):

- `http://192.168.1.25:8000`

## Security note (MVP)

This scaffold now stores the patient mobile token in Keychain. The remaining production step is to replace the bootstrap pasted token with a first-class mobile sign-in screen.

## Patient design migration

The SwiftUI migration plan is documented in:

- [docs/SWIFTUI_PATIENT_APP_PLAN_MAR_2026.md](/Users/bryan.bosire/anaconda_projects/MedMemory/docs/SWIFTUI_PATIENT_APP_PLAN_MAR_2026.md)
