## Frontend Refactor Plan (MedMemory)

This document outlines how to implement the frontend refactor recommendations without changing user-facing behavior. The goal is to reduce duplication, clarify responsibilities, and make it easier to extend the app.

---

## 1. Extract App-Level Responsibilities into Focused Hooks

**Goal:** Turn `App.tsx` into a thin shell that composes feature hooks instead of owning all logic.

### 1.1. `useAuthBootstrap`

**Current:** `App.tsx` runs `api.getCurrentUser()` inside a `useEffect`, handles 401/403, and calls `setAccessToken`/`setUser`.

**New hook:**
- Location: `src/hooks/useAuthBootstrap.ts`
- Responsibilities:
  - On mount (and when `accessToken` changes), fetch current user.
  - Handle auth errors consistently (clear tokens and surface a standardized error label).
  - Return `{ currentUser, isAuthLoading }`.

**Steps:**
1. Move the `useEffect` that calls `api.getCurrentUser()` from `App.tsx` into `useAuthBootstrap`.
2. Have `useAuthBootstrap` accept `accessToken` and `onError` (for toasts/banners).
3. In `App.tsx`, call `useAuthBootstrap` and remove the inline `useEffect`.

### 1.2. `usePrimaryPatientSelection`

**Current:** `App.tsx` auto-selects or creates a patient after login with a large `useEffect` (timeouts, logging, creation).

**New hook:**
- Location: `src/hooks/usePrimaryPatientSelection.ts`
- Responsibilities:
  - Given `currentUser`, `accessToken`, and `patientId`, ensure a primary patient exists.
  - Either:
    - Select first patient from `api.listPatients()`, or
    - Create a new patient for the user and select it.
  - Manage `patientLoadingFailed` and `autoSelectedPatient`.

**Steps:**
1. Move the entire “Auto-select or create patient when user logs in” `useEffect` into the new hook.
2. Expose:
   - `autoSelectedPatient`
   - `patientLoadingFailed`
   - `isLoadingPatient`
3. Use this hook in `App.tsx` to replace the corresponding local state/effects.

### 1.3. `useProfileSummary` + `usePrimaryPatientId`

**Current:** `App.tsx` fetches `/profile` in two separate `useEffect`s: one to get `primaryPatientId`, another to get `profileSummary`. `TopBar` also fetches `/profile` and `/dependents`.

**New hooks:**
- `useProfileSummary(patientId)`:
  - Fetches `/api/v1/profile?patient_id=...` and returns `{ profileSummary, isProfileLoading }`.
- `usePrimaryPatientId()`:
  - Fetches `/api/v1/profile` and returns `{ primaryPatientId, primaryPatientName }`.

**Steps:**
1. Move the profile-fetch `useEffect`s from `App.tsx` into these hooks.
2. Update `TopBar` to consume `usePrimaryPatientId` instead of calling `fetch` directly.
3. Update `App.tsx` to use `useProfileSummary(patientId)` instead of local `profileSummary` fetching.

---

## 2. Extract Document Workspace Logic

**Goal:** Have a dedicated hook for managing documents (state, actions, status) so both Dashboard and future views can reuse it.

### 2.1. `useDocumentWorkspace`

**Current logic scattered in `App.tsx`:**
- State:
  - `processingDocs`, `deletingDocs`
  - `selectedFile`, `documentStatus`
  - `documentPreview`, `documentDownloadUrl`
- Handlers:
  - `handleUploadDocument`
  - `handleProcessDocument`
  - `handleDeleteDocument`
  - `handleViewDocument`

**New hook:**
- Location: `src/hooks/useDocumentWorkspace.ts`
- Inputs:
  - `patientId`
  - `selectedPatient` (for disabled states)
  - `onError` (uses the shared `handleError`)
  - `pushToast`
  - `uploadWithDuplicateCheck` (from `useDocumentUpload`)
  - `documents`, `reloadDocuments` (from `usePatientDocuments`)
- Outputs:
  - `processingDocs`, `deletingDocs`
  - `selectedFile`, `setSelectedFile`
  - `documentStatus`, `setDocumentStatus`
  - `documentPreview`, `documentDownloadUrl`
  - Handlers: `onUpload`, `onProcess`, `onView`, `onDelete`, `onClosePreview`

**Steps:**
1. Create the hook and move the document-related state + handlers out of `App.tsx`.
2. Wire it into the Dashboard view:
   - Pass the returned props directly into `DocumentsPanel`.
3. Ensure types align with `DocumentItem` and `OcrRefinementResponse`.

---

## 3. Extract Chat Upload + Localization Orchestration

**Goal:** Separate complex chat-file interactions from the main `App.tsx` and make them reusable.

### 3.1. `useChatUploads`

**Current in `App.tsx`:**
- State:
  - `chatUploadStatus`, `isChatUploading` (status only)
  - `localizationPreview` (for localization modal)
- Handlers:
  - `handleChatUpload(file | File[])`
  - `handleLocalizeUpload(file)`
  - `handleSingleChatUpload(file)` (internal to chat upload)

**New hook:**
- Location: `src/hooks/useChatUploads.ts`
- Inputs:
  - `patientId`
  - `question`
  - `uploadWithDuplicateCheck`
  - Chat actions: `send`, `sendVision`, `sendVolume`, `sendWsi`, `pushMessage`
  - `api` instance and `handleError`, `pushToast`
- Outputs:
  - `chatUploadStatus`, `isChatUploading`
  - `localizationPreview`, plus a `clearLocalizationPreview` helper
  - `handleChatUpload`
  - `handleLocalizeUpload`

**Steps:**
1. Move chat-upload-related `useState`s and functions into `useChatUploads`.
2. Keep all user-facing strings intact (no text changes).
3. In `App.tsx`, replace inline handlers with the hook outputs and pass them to `ChatInterface` and `LocalizationModal`.

---

## 4. Harden and Centralize Error + Auth Handling

**Goal:** Have a single pattern for reporting errors and handling auth failures.

### 4.1. `useAppErrorHandler`

**Current:** `App.tsx` defines `handleError(label, error)` and passes it deep into hooks/components. Some places handle 401/403 inline (e.g. `useChat` calling `setAccessToken(null)`).

**New hook:**
- Location: `src/hooks/useAppErrorHandler.ts`
- Responsibilities:
  - Wrap `getUserFriendlyMessage` for consistent user messages.
  - Optionally detect auth-related errors and trigger logout or token clear.
  - Emit both banner text and toast via callbacks provided by the caller.

**Steps:**
1. Encapsulate the `handleError` from `App.tsx` into `useAppErrorHandler`.
2. Have `App.tsx` call the hook and pass `setErrorBanner` + `pushToast`.
3. Gradually update other hooks (`useChat`, `useIngestion`, etc.) to rely on this shared pattern for auth errors (401/403) where appropriate.

---

## 5. Unify Profile, Dependents, and View-Context State

**Goal:** One source of truth for “who we’re viewing” and “who owns the profile”.

### 5.1. `useProfileContext`

**New hook:**
- Location: `src/hooks/useProfileContext.ts`
- Responsibilities:
  - Combine:
    - Primary patient ID / name.
    - Current patient ID (`patientId` from store).
    - `profileSummary` (for the current view).
    - Dependents list and switching logic (currently in `TopBar`).
  - Expose:
    - `selectedPatient` (with dependent flag).
    - `primaryPatientId`, `primaryPatientName`.
    - `switchToPrimary()`, `switchToDependent(id)`.

**Steps:**
1. Build `useProfileContext` from the existing logic in:
   - `TopBar` (dependents and primary patient fetch).
   - `App.tsx` (profile summary and primary patient ID).
2. Update `TopBar` to consume `useProfileContext` for:
   - Switcher options,
   - “Back to My Health” behavior,
   - Editing profiles.
3. Update `App.tsx` to use the `selectedPatient`/`profileSummary` from this hook instead of separately fetched state where feasible.

---

## 6. Centralize Status/Copy Constants (Optional but Recommended)

**Goal:** Avoid copy drift and make status strings easy to maintain.

**New file(s):**
- `src/constants/statusMessages.ts`
  - Status labels for uploads, processing, localization, etc.
- `src/constants/errorLabels.ts`
  - Human-readable labels for `useApiList` errorLabel values (`"Failed to load patients"`, `"Failed to load documents"`, etc.).

**Steps:**
1. Introduce a single source of truth for existing status/error strings.
2. Update hooks and handlers to import these constants rather than inlining strings.

---

## 7. Testing / Verification Strategy

**Goal:** Ensure the refactor preserves behavior.

### 7.1. Unit / Component Tests

1. **Existing Vitest suites**:
   - Run `npm run test` after each major extraction (auth hooks, document workspace, chat uploads) to catch regressions.
2. **Add targeted tests where valuable**:
   - `useApiList` is already well-isolated; consider a small test for `useDocumentWorkspace` once it exists (mock `api` and `uploadWithDuplicateCheck`).
   - For `TopBar`, keep the current tests but adjust expectations if the source of profile data changes.

### 7.2. E2E Smoke (Playwright)

After the refactor stabilizes:
- Run the existing Playwright suites (auth, documents, patients, visual) to ensure:
  - Login still works.
  - Patient auto-selection/creation behaves as expected.
  - Document upload + display + delete flows still work.
  - Chat file uploads (image/report/volume/WSI) still invoke the right endpoints.

---

## 8. Suggested Implementation Order

To reduce risk and keep changes reviewable:

1. **Hooks-first, no behavior changes:**
   - Implement `useAuthBootstrap`, `usePrimaryPatientSelection`, `useProfileSummary`, `usePrimaryPatientId`, and update `App.tsx` + `TopBar` wiring.
2. **Document workspace extraction:**
   - Implement `useDocumentWorkspace`, update Dashboard wiring, and re-run tests.
3. **Chat uploads extraction:**
   - Implement `useChatUploads`, wire into `App.tsx`, ensure MedGemma flows still behave identically.
4. **Error/auth handler centralization:**
   - Introduce `useAppErrorHandler` and apply it incrementally to hooks.
5. **Profile context unification:**
   - Implement `useProfileContext` and retrofit `TopBar` and `App.tsx`.
6. **Constants for status/copy (optional, low risk):**
   - Move existing strings into constants with no logic changes.

At each step, keep PRs/refactor commits focused and run:
- `npm run test`
- `SKIP_API_GEN=1 npm run build`

to confirm the frontend remains healthy.

