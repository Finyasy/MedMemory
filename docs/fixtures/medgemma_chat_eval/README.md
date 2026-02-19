# MedGemma Chat Tone Eval Fixtures

This fixture pack is for Playwright chat-tone evaluation only.

## Data policy

- Public de-identified or synthetic examples only.
- No real patient identifiers.
- Records are normalized into MedMemory `records` payloads (`title`, `content`, `record_type`).

## Public source references

- PhysioNet MIMIC-IV Demo (de-identified demo EHR): <https://physionet.org/content/mimic-iv-demo/2.2/>
- MIMIC FHIR resources (de-identified): <https://mimic.mit.edu/fhir/>
- HL7/FHIR example resources: <https://build.fhir.org/>
- CMS Blue Button sandbox docs (synthetic Medicare data): <https://sandbox.bluebutton.cms.gov/docs/>

## Files

- `public_record_samples.json`: normalized sample records used for seeding.
- `scenarios.json`: scripted prompt scenarios and expectation metadata.
