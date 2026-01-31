# Doctor Dashboard (Clinician Portal) - Backend Review + Proposal

Date: 2026-01-29
Owner: MedMemory
Scope: Backend review and a proposal for a clinician-facing dashboard (login/signup, review uploads, technical chat)
Status: Draft for review

**Implementation status (phases 1–2 + clinician chat):**
- **Phase 1 (Data model + auth):** Done — user role, clinician profiles, access grants, audit log, migration.
- **Phase 2 (Authorization):** Done — `get_authorized_patient` dependency; JWT includes `role`; chat uses authorized access with `chat` scope.
- **Clinician chat mode:** Done — `clinician_mode` query param on `/chat/ask` and `/chat/stream`; clinician system prompt (terse, citations, "Not in documents").
- **Phase 3 (Clinician API + UI):** Done. Backend: clinician signup/login, profile GET/PATCH, access request/approve/revoke, list patients, uploads, patient documents/records. Frontend: /clinician route with login/signup, dashboard (patient list + upload queue), patient view (documents, records, technical chat with clinician_mode).

---

## 1) Backend review (current state)

### Auth + user model
- User model: `users` table has email, password hash, full_name, is_active, **role** (patient | clinician | staff | admin). **Implemented.**
- Auth endpoints: `/api/v1/auth/signup`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`.
- **JWT access tokens include `role` for fast checks. Implemented.**

### Patient ownership + access
- `Patient.user_id` ties each patient to a single owner. **Clinician access:** `patient_access_grants`; `get_authorized_patient(patient_id, scope=...)` allows owner or clinician with active grant (documents, records, labs, medications, chat). **Implemented.**

### Document + record review features
- Documents, records, and ingestion endpoints exist and are scoped to the owning user via `get_patient_for_user` and `_get_document_for_user`.
- Document status endpoint includes chunk/indexing stats, helpful for understanding retrieval readiness.

### LLM + chat
- RAG service has patient-facing prompts and **clinician system prompt** (terse, citations, "Not in documents"). **Implemented.**
- **Clinician mode:** `clinician_mode=true` on `POST /chat/ask` and `POST /chat/stream`; access via `get_authorized_patient(..., scope="chat")`. **Implemented.**

### Remaining gaps for full doctor workflow
- Optional: patient-side UI to view and approve/revoke pending access requests (API exists: POST /patient/access/grant, POST /patient/access/revoke). Optional: clinician profile edit screen in UI.

---

## 2) Goals for the doctor dashboard

1) **Clinician login/signup** separate from patient accounts.
2) **Secure access to patient records** only with explicit authorization.
3) **Review and triage recent uploads** (documents, notes, labs).
4) **Technical chat interface** that is precise, grounded, and includes source references.

---

## 3) Proposed data model changes

### 3.1 Add user roles
Add a role to `User`:
- `role`: enum/string: `patient`, `clinician`, `staff`, `admin`.
- Migrate existing users to `patient` by default.

### 3.2 Clinician profile
New table:
- `clinician_profiles`
  - `user_id` (FK -> users)
  - `npi` / `license_number`
  - `specialty`, `organization_name`
  - `phone`, `address`
  - `verified_at` (optional)

### 3.3 Access grants (patient -> clinician)
New table:
- `patient_access_grants`
  - `patient_id`
  - `clinician_user_id`
  - `status` (pending/active/revoked/expired)
  - `scopes` (documents, records, labs, medications, chat)
  - `granted_at`, `expires_at`
  - `granted_by_user_id` (patient owner)

### 3.4 Audit log
New table:
- `access_audit_log`
  - `actor_user_id`, `patient_id`
  - `action` (view_document, download, chat_query, etc.)
  - `metadata` (document_id, endpoint, etc.)
  - `created_at`

---

## 4) Auth + authorization updates

### Token claims
- Include `role` in JWT for fast checks.
- Optional: include clinician_id or org_id.

### Access checks
Add a new dependency:
- `get_authorized_patient(patient_id)`
  - Allow if: owner user OR clinician has active grant with scope.
  - Enforce scope for documents/records/labs endpoints.

---

## 5) API additions

### Clinician auth
- `POST /api/v1/clinician/signup`
- `POST /api/v1/clinician/login`
- `GET /api/v1/clinician/profile`
- `PATCH /api/v1/clinician/profile`

### Access grants
- `POST /api/v1/clinician/access/request` (clinician -> patient)
- `POST /api/v1/patient/access/grant` (patient approves)
- `POST /api/v1/patient/access/revoke`
- `GET /api/v1/clinician/patients` (list patients with active grants)

### Upload review
- `GET /api/v1/clinician/uploads` (filter by status, time, patient)
- `GET /api/v1/clinician/patient/{id}/documents`
- `GET /api/v1/clinician/patient/{id}/records`

---

## 6) Clinician dashboard UX (proposed)

### Primary views
1) **Login / signup**
   - Clinician-specific verification fields (license/NPI).
2) **Dashboard**
   - Upload queue: newest docs, processing status, flags.
   - Patient list (active grants).
3) **Patient workspace**
   - Timeline (records + documents + labs)
   - Document viewer (OCR text, metadata, extracted tables)
   - Review actions (flag, add note, request reprocess)
4) **Technical chat**
   - Clinician-focused chat with source grounding.

---

## 7) Technical chat interface (clinician mode)

### Prompting behavior
- Use a **clinician system prompt** that is terse and technical.
- Require explicit citations: document_id + chunk excerpt or section name.
- Never invent values; if missing, say “Not in documents.”

### Output format suggestion
```
Summary:
- 1–2 sentences of factual summary.

Findings:
- [value] [unit] (source: doc_id:chunk_id)

Questions/Unclear:
- Items that are mentioned but missing specifics.
```

### Backend changes
- Add `system_prompt` override for clinician requests.
- Add a “clinician mode” flag in chat endpoints.

---

## 8) Security + compliance

- Strict access grants + audit log.
- Time-bounded access tokens for clinicians.
- Optional 2FA for clinician accounts.
- Prevent data leakage in chat: no patient data without explicit grant.

---

## 9) Migration plan (phased)

**Phase 1: Data model + auth** — DONE
- Add user role (User.role; default patient)
- Add clinician_profiles table
- Add patient_access_grants table
- Add access_audit_log table
- Migration: `20250129_00_doctor_dashboard_phase1.py` (or equivalent)

**Phase 2: Authorization** — DONE
- `get_authorized_patient(patient_id, scope=...)` in deps.py
- JWT access token includes `role` (auth.py: signup, login, refresh)
- Chat endpoints use `get_authorized_patient(..., scope="chat")` and support `clinician_mode` query param

**Phase 3: Clinician API + UI** — DONE
- Clinician system prompt and `clinician_mode` on /chat/ask and /chat/stream — DONE
- Clinician API: POST /clinician/signup, POST /clinician/login, GET/PATCH /clinician/profile — DONE
- Access grants: POST /clinician/access/request, GET /clinician/patients; POST /patient/access/grant, POST /patient/access/revoke — DONE
- Upload review: GET /clinician/uploads, GET /clinician/patient/{id}/documents, GET /clinician/patient/{id}/records — DONE
- Clinician dashboard UI: /clinician route, login/signup, patient list, upload queue, patient view (documents, records, technical chat) — DONE

---

## 10) Open questions

1) Do clinicians register themselves or are they invited by patients?
2) Should staff accounts be supported (scribe, nurse, admin)?
3) What level of verification is required before access is granted?
4) Should clinician accounts be tied to an organization?

---

## 11) Recommendation

Start with **role + access grant + clinician profile**. This will allow a separate portal without breaking existing patient workflows. Then add clinician-specific chat and UI.
