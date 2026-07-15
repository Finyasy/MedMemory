# MedMemory Kaggle Submission Plan (MedGemma Impact Challenge)

Last updated: February 20, 2026  
Competition deadline: February 24, 2026 at 11:59 PM UTC

## 1) Submission Strategy

### Recommended track selection
- Main Track (required for overall placement)
- One special prize only: **Agentic Workflow Prize** (recommended)

Why Agentic Workflow:
- MedMemory already has a strong workflow story: connect records -> approve/link patient -> open workspace -> grounded chart Q&A.
- This maps directly to "reimagines a complex workflow with intelligent agents/callable tools."

### Core judging narrative
- Problem: fragmented records and low-context health AI create unsafe or low-trust answers.
- Solution: patient-controlled, local-first, evidence-grounded MedGemma assistant integrated into a real clinician workflow.
- Differentiator: fail-closed guardrails, citations, refusal behavior when evidence is missing, and measurable hallucination controls.

## 2) Rubric-to-Evidence Mapping

### Effective use of HAI-DEF models (20%)
- Show exactly where MedGemma is used:
  - grounded patient Q&A
  - structured summaries
  - clinician technical chart chat
- Include one architecture diagram (in writeup image or repo README):
  - Retriever -> Evidence Validator -> MedGemma -> Citation/Numeric Validator -> UI
- State why generic alternatives were less appropriate for this exact workflow.

### Problem domain (15%)
- Define target users:
  - patient user: understanding personal records without unsupported claims
  - clinician user: rapid chart context review with evidence trail
- Quantify pain:
  - fragmented systems
  - time lost searching across portals
  - trust loss from uncited model outputs

### Impact potential (15%)
- Provide measurable outcomes with your eval set:
  - hallucination rate
  - citation coverage
  - refusal precision when evidence is missing
  - workflow completion time reduction (before vs after)

### Product feasibility (20%)
- Document reproducibility:
  - setup commands
  - model/runtime constraints on Mac M4
  - deployment architecture and guardrails
- Include known limitations and fallback behavior.

### Execution and communication (30%)
- Use one clean narrative across:
  - 3-page writeup
  - <=3 minute demo video
  - public code repository
- Keep visuals and demo steps tightly aligned to rubric.

## 3) Final Deliverables Checklist (Hard Requirements)

### Mandatory
- Kaggle Writeup (<=3 pages)
- Public code repository URL
- Video demo URL (<=3 minutes)

### Strongly recommended
- Public demo app URL
- Reproducible evaluation script and sample data loader
- Optional model artifact lineage (adapter/checkpoint references)

### Final package QA checklist
- No broken links
- All claims tied to numbers or explicit qualitative evidence
- Video and writeup tell the same story
- Track selection is Main + exactly one special prize

## 4) Freeze Plan (Feb 20 -> Feb 24, 2026)

### Feb 20 (today)
- Freeze scope: no new feature epics; focus on submission quality.
- Lock final architecture diagram and metrics definitions.
- Prepare seeded demo account + stable dataset snapshot.

### Feb 21
- Run final evaluation pipeline and export results table.
- Capture screenshots/short clips for writeup and video.
- Draft writeup v1 using template below.

### Feb 22
- Record video v1.
- Run internal rubric review (self-score each criterion).
- Fill evidence gaps in writeup.

### Feb 23
- Record final video.
- Final proofread/writeup compression to <=3 pages.
- Validate all links from a clean browser session.

### Feb 24
- Submit before deadline buffer (target at least 3 hours early).
- Re-check selected track options before final submit click.

## 5) Metrics Table Template (Use in Writeup + Repo)

| Metric | Definition | Baseline | Final | Evidence Source |
|---|---|---:|---:|---|
| Hallucination rate | Unsupported claims / total claims | [fill] | [fill] | [eval report path] |
| Citation coverage | Claims with traceable source / total claims | [fill] | [fill] | [validator report path] |
| Refusal precision | Correct refusals when context missing / total refusals | [fill] | [fill] | [gate report path] |
| Numeric claim fidelity | Correct numeric claims / total numeric claims | [fill] | [fill] | [numeric eval path] |
| Median answer latency | p50 end-to-end response time | [fill] | [fill] | [timing logs] |
| Workflow completion time | Minutes to complete clinician review flow | [fill] | [fill] | [usability run notes] |

## 6) Fill-In Writeup Template (Kaggle-Ready)

Copy this section into your Kaggle Writeup and replace placeholders.

---

## Project name
[Project name]

## Your team
- [Name] - [Role] - [What they built]
- [Name] - [Role] - [What they built]

## Problem statement
[Who is affected], [what friction exists], and [why current solutions fail].  
In our target workflow, users need [specific outcome], but today they face [fragmentation / latency / trust issue].  
If solved, this improves [clinical/patient impact] by [estimated magnitude].

## Overall solution
We built [one-sentence product summary] using [HAI-DEF model(s), including MedGemma].  

### How HAI-DEF is used
- Model(s): [exact model names]
- Task(s): [Q&A, summarization, extraction, workflow actions]
- Why this model fits: [domain alignment, local/edge feasibility, controllability]

### System design
- Retrieval: [vector DB/chunking/reranking]
- Guardrails: [evidence validation, citation checks, refusal policy]
- Output constraints: [structured schema, no-guess behavior]
- UX: [patient flow + clinician flow]

## Technical details

### Architecture and stack
- Backend: [framework + key services]
- Frontend: [framework + key pages/components]
- Data: [document ingestion, indexing, retrieval]
- Runtime: [Mac M4/local details if relevant]

### Evaluation methodology
- Dataset: [size, source, de-identification approach]
- Tasks: [numeric grounding, trend questions, context gate, etc.]
- Metrics: [hallucination rate, citation coverage, refusal precision, latency]

### Results
| Metric | Result |
|---|---:|
| Hallucination rate | [fill] |
| Citation coverage | [fill] |
| Refusal precision | [fill] |
| p50 latency | [fill] |

### Product feasibility
- Deployment path: [local/dev/prod]
- Reliability considerations: [monitoring, fallback]
- Security/privacy considerations: [PHI-safe logging, access controls]
- Known limitations: [clear bullet list]

### Impact estimate
- User segment: [fill]
- Time saved or quality gain: [fill]
- Risk reduction narrative: [fill]

### Links
- Video (required): [URL]
- Public code repo (required): [URL]
- Live demo (optional): [URL]
- Model/artifact lineage (optional): [URL]

---

## 7) Video Script (<= 3:00) - Production Version

Goal: hit every judging criterion with evidence and minimal filler.

### 0:00 - 0:15 (Hook + Problem)
Voiceover:
"Healthcare data is fragmented across portals and PDFs. Patients and clinicians ask critical questions, but AI responses are risky when context is incomplete."
On screen:
- Split view of fragmented record sources
- One concise problem statement overlay

### 0:15 - 0:35 (Solution One-Liner)
Voiceover:
"We built MedMemory, a patient-controlled assistant powered by MedGemma that only answers from retrieved evidence, cites sources, and refuses unsupported claims."
On screen:
- Landing page
- 3-value chips: grounded, cited, fail-closed

### 0:35 - 1:10 (Patient Workflow Demo)
Voiceover:
"A patient uploads records and asks a lab-specific question. The assistant answers with concise language and explicit evidence."
On screen:
- Upload record
- Ask question
- Response with source snippets/citations

### 1:10 - 1:45 (Clinician Workflow Demo)
Voiceover:
"In clinician mode, approved patient context opens a focused workspace for chart review. The assistant provides technical responses with citations and structured output."
On screen:
- Clinician portal queue -> open patient -> ask technical question
- Show records panel + answer + source anchors

### 1:45 - 2:20 (Guardrails + Evaluation)
Voiceover:
"Our safety layer validates evidence before and after generation. If evidence is weak or absent, the model returns a calibrated refusal."
On screen:
- Simple architecture diagram
- Evaluation table with hallucination/citation/refusal metrics

### 2:20 - 2:45 (Impact + Feasibility)
Voiceover:
"This system is feasible with open models and local-first architecture, and it improves trust by making evidence mandatory for claims."
On screen:
- Runtime/latency bullets
- Before vs after workflow time

### 2:45 - 3:00 (Close + Ask)
Voiceover:
"MedMemory demonstrates human-centered, evidence-grounded healthcare AI with MedGemma. Full code, reproducible evaluation, and demo links are in our submission."
On screen:
- Project name
- Repo URL
- Writeup + demo URL

## 8) Video Recording Checklist

- Record at 1440p or 1080p, 16:9.
- Keep UI zoom readable (minimum 125% if needed).
- Show cursor intentionally; avoid rapid scrolling.
- Use one clear audio take (no background noise).
- Keep transitions simple; avoid heavy effects.
- Confirm total runtime <= 3:00.

## 9) Repo Readiness Checklist (Before Submit)

- Root README has:
  - project summary
  - architecture diagram
  - setup/run commands
  - eval commands
  - demo credentials/instructions (if applicable)
- No broken imports/tests for core demo path.
- Large generated artifacts excluded from git or handled correctly.
- Environment variables documented with safe defaults.

## 10) Submission Dry-Run Procedure

1. Open writeup preview and verify formatting.
2. Click each required link from a logged-out browser.
3. Re-watch video at 1.25x and 1.0x for clarity issues.
4. Verify track selection: Main + one special prize.
5. Submit with time buffer before February 24, 2026 at 11:59 PM UTC.

## 11) Risk Register (Last-Mile)

- Risk: video exceeds 3 minutes  
Mitigation: hard cap script timings and trim pauses.

- Risk: claims in writeup not backed by metrics  
Mitigation: final evidence pass against metrics table.

- Risk: confusing track selection  
Mitigation: choose exactly one special prize.

- Risk: demo instability  
Mitigation: use seeded data and rehearse exact click path.

## 12) Optional Add-Ons (Only If Time Allows)

- One-page model card for MedMemory usage boundaries.
- Short appendix with failure examples and safe refusal behavior.
- Public dashboard screenshot for evaluation trend tracking.
