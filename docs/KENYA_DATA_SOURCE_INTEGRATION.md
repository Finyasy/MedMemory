# Kenya Data Source Integration Guide

This project now uses a Kenya-first data source catalog in the dashboard connection flow.

## Active data source catalog

1. Digital Health Agency (DHA)
2. National Shared Health Record (SHR) / AfyaYangu
3. Kenya Health Information System (KHIS)
4. Integrated Health Information System (IHIS/HIE)
5. MoH Data Warehouse (DWH / DWAPI)
6. AfyaRekod
7. Medbook (AphiaOne HMIS)
8. RUPHAsoft
9. Ksatria Hospital Information System
10. Dawascope
11. KeHMIS Interoperability Layer
12. SHIELD Surveillance Linkage
13. KEMSA LMIS
14. Kenya Master Health Facility List (KMHFL)

Note: Dawascope and SHIELD are included per requested source list; confirm direct API onboarding docs before production integration.

## Integration approach

### 1) Use DHA onboarding and trust framework first

- Register systems through the DHA ecosystem before production exchange.
- Anchor partner identity and permissions with the DHA-led interoperability model.

### 2) Normalize exchange to HL7 FHIR resources

For inbound payloads from DHA/SHR/KHIS/partner systems, map FHIR to MedMemory ingestion contracts:

- `Observation` -> `/ingest/labs` or `/ingest/labs/batch`
- `DiagnosticReport` + `Observation` -> `/ingest/labs/panel`
- `MedicationRequest` / `MedicationDispense` -> `/ingest/medications` or `/ingest/medications/batch`
- `Encounter` -> `/ingest/encounters` or `/ingest/encounters/batch`

### 3) Keep facility identity consistent

- Use KMHFL facility codes as canonical facility identifiers.
- Carry source labels in `source_system`, `performing_lab`, `provider_name`, and `facility` fields.

### 4) Use the dashboard connection layer as the sync control plane

- Register connections via `POST /dashboard/patient/{patient_id}/connections`.
- Trigger incremental updates via `POST /dashboard/patient/{patient_id}/connections/{connection_id}/sync`.
- Validate live API configuration before ingest via `POST /dashboard/patient/{patient_id}/connections/{connection_id}/sync/dry-run`.
- Adapter routing lives in `backend/app/services/provider_sync.py` and now includes Kenya source slugs.

### 5) Enforce data governance and legal controls

- Align implementation to the Digital Health Act and Health Information Exchange Regulations.
- Ensure consent, access control, auditability, and minimum-necessary data exchange.

## Live API runtime setup

Set these backend environment variables (JSON objects are required for maps):

- `PROVIDER_SYNC_LIVE_ENABLED=true`
- `PROVIDER_SYNC_LIVE_BASE_URLS`:
  `{\"digital_health_agency_dha\":\"https://<dha-fhir-base>\",\"kenya_health_information_system_khis\":\"https://<khis-fhir-base>\",\"national_shr_afyayangu\":\"https://<shr-fhir-base>\",\"afyarekod\":\"https://<afyarekod-fhir-base>\"}`
- `PROVIDER_SYNC_LIVE_BEARER_TOKENS`:
  `{\"digital_health_agency_dha\":\"<token>\",\"kenya_health_information_system_khis\":\"<token>\",\"national_shr_afyayangu\":\"<token>\"}`
- `PROVIDER_SYNC_LIVE_API_KEYS` (if provider requires API key header):
  `{\"medbook_aphiaone_hmis\":\"<api-key>\",\"ruphasoft\":\"<api-key>\"}`
- Optional:
  - `PROVIDER_SYNC_LIVE_PATIENT_IDENTIFIER_SYSTEM` (FHIR identifier system URI)
  - `PROVIDER_SYNC_LIVE_TIMEOUT_SECONDS` (default `30`)
  - `PROVIDER_SYNC_LIVE_VERIFY_SSL` (default `true`)
  - `PROVIDER_SYNC_LIVE_PAGE_SIZE` (default `200`)
  - `PROVIDER_SYNC_LIVE_MAX_PAGES_PER_RESOURCE` (default `20`)
  - `PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN` (default `true`)

The live adapter pulls `Observation`, `MedicationRequest`, and `Encounter` from FHIR and ingests them into MedMemory with dedupe on `patient_id + source_system + source_id`.

Dry-run response includes resolved provider mode/key, patient reference, and resource counts (`Observation`, `MedicationRequest`, `Encounter`) without writing ingested records.

If live endpoint checks fail and `PROVIDER_SYNC_LIVE_FALLBACK_TO_LOCAL_SCAN=true`, dry-run returns `mode=local_fallback` with details and sync uses local delta scanning instead of failing hard.

Recommended local workflow:

```bash
cd backend
python scripts/apply_provider_sync_env.py \
  --env-file .env \
  --base-urls "<JSON_OR_PATH>" \
  --bearer-tokens "<JSON_OR_PATH>" \
  --api-keys "<JSON_OR_PATH>"

python scripts/dry_run_provider_connections.py \
  --base-url http://localhost:8000/api/v1 \
  --patient-id <PATIENT_ID> \
  --token "<JWT>"
```

## Verified references used

- DHA portal: https://www.dha.go.ke/
- DHA med portal: https://med.kenya-hie.health/
- DHA client registry API docs: https://afyalink.dha.go.ke/apidocs/client-registry-api
- HL7 FHIR standard: https://www.hl7.org/fhir/
- Kenya Digital Health Act (2023): https://new.kenyalaw.org/akn/ke/act/2023/15/eng%402023-11-24
- Kenya Health Information Exchange Regulations (2025): https://new.kenyalaw.org/akn/ke/act/ln/2025/77/eng%402025-04-11
- Ministry of Health digital platforms page (KHIS, KMHFL links): https://www.health.go.ke/
- KHIS implementation network references: https://hiskenya.org/
- KeHMIS interoperability overview: https://kenyahmis.org/documentation/summary-interoperability/
- National Data Warehouse overview: https://kenyahmis.org/documentation/summary-national-data-warehouse/
- AfyaRekod: https://www.afyarekod.com/
- Medbook (AphiaOne): https://www.medbookafrica.com/aphiaone/
- RUPHAsoft communication brief: https://rupha.co.ke/wp-content/uploads/2025/05/RUPHAsoft-Version-1-Communication.pdf
- Ksatria Kenya page: https://www.ksatria.io/en/hospital-information-system/kenya/
- KEMSA site (LMIS link): https://www.kemsa.go.ke/
