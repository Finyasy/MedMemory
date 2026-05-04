# TurboQuant Execution Checklist

## Purpose

This is the short execution checklist for TurboQuant work in MedMemory.

Use this document to drive the work without reopening every planning document. When a step needs detail, follow the linked spec.

## Core References

- `docs/TURBOQUANT_ADR.md`
- `docs/TURBOQUANT_BENCHMARK_SPEC.md`
- `docs/TURBOQUANT_ASSET_SPEC.md`
- `docs/TURBOQUANT_SPRINT0_FEASIBILITY_SPEC.md`
- `docs/TURBOQUANT_BOOTSTRAP_SCRIPT_SPEC.md`
- `docs/TURBOQUANT_RUNTIME_HOOKS_NOTES.md`
- `docs/TURBOQUANT_MEDGEMMA_IMPLEMENTATION_PLAN_MAR_2026.md`

## Frozen Defaults

- local runtime target: `MLX`
- fallback runtime: `Transformers on MPS`
- Phase 1 scope: text-generation KV cache only
- first profile: `3.5-bit`
- `2.5-bit`: experimental
- first outlier policy: fixed, versioned partition
- first prototype style: correctness-first

## Phase Checklist

### Sprint 0: Feasibility

- Review `docs/TURBOQUANT_SPRINT0_FEASIBILITY_SPEC.md`
- Trace current MedGemma local generation path
- Map where K/V tensors are created, cached, and reused
- Determine whether `MLX` allows:
  - cache-write interception
  - compressed payload substitution
  - attention-time reconstruction or score-time use
- Capture the cache-shape contract:
  - target quantized dimension
  - layer/head layout
  - per-step cache update behavior
- Decide:
  - `MLX` first
  - or `Transformers on MPS` first

Sprint 0 exit condition:
- clear go/no-go on MLX-first

### Sprint 1: Assets and Baseline

- Review `docs/TURBOQUANT_BOOTSTRAP_SCRIPT_SPEC.md`
- Review `docs/TURBOQUANT_ASSET_SPEC.md`
- Define bootstrap asset output layout
- Define manifest schema and checksums
- Define integer-bit codebooks needed for the `3.5-bit` profile
- Define fixed outlier partition metadata
- Define `3.5-bit` composite profile manifest
- Prepare benchmark fixtures from `docs/TURBOQUANT_BENCHMARK_SPEC.md`
- Run full-precision baseline on the same MacBook
- Record:
  - TTFT
  - tokens/sec
  - end-to-end latency
  - memory pressure
  - swap usage
  - user-visible quality outputs

Sprint 1 exit condition:
- asset contract frozen
- baseline benchmark report available

### Sprint 2: First Prototype

- Implement correctness-first `TurboQuantmse`
- Keep `3.5-bit` as the first target profile
- Keep public API contracts unchanged
- Use explicit reconstruction path first
- Add enough logging to explain:
  - quality drift
  - memory behavior
  - performance changes
- Run benchmark matrix against the same local baseline

Sprint 2 exit condition:
- benchmark report for `TurboQuantmse 3.5-bit`
- recommendation on whether `TurboQuantprod` is needed

### Sprint 3: Promote or Pivot

- If `3.5-bit` is strong, prepare it as the default candidate
- If low-bit attention drift appears, prototype `TurboQuantprod`
- Keep `2.5-bit` experimental unless it clears the same benchmark gates
- Write decision memo:
  - keep `TurboQuantmse`
  - or promote `TurboQuantprod`

Sprint 3 exit condition:
- default profile recommendation
- default variant recommendation
- explicit status of `2.5-bit`

## Benchmark Checklist

- Same MacBook for baseline and quantized runs
- Same runtime family for comparison
- Same model
- Same prompt set
- Warm model before measuring
- Avoid heavy concurrent local workloads
- Prefer plugged-in runs

Minimum workload set:

- patient chat, short context
- patient chat, long context
- clinician summary
- long document Q&A with grounding
- long-context retrieval-style prompt

Track:

- answer correctness
- citation grounding quality
- refusal correctness
- summary completeness
- TTFT
- tokens/sec
- end-to-end latency
- memory pressure
- swap usage

## Asset Checklist

- rotation assets present
- required integer-bit codebooks present
- composite profile manifest present
- partition metadata present
- residual/QJL assets present if `TurboQuantprod` is enabled
- checksums and versions recorded
- startup validation fails closed on mismatch

## Go / No-Go Rules

### Go on `3.5-bit` if

- memory pressure drops materially
- swap-heavy behavior is reduced or delayed
- no visible answer-quality regression appears
- local runtime remains operationally manageable

### Keep `2.5-bit` experimental if

- long-context drift is visible
- grounding degrades
- quality is unstable run-to-run
- stronger inner-product protection is needed

### Pivot runtime if

- `MLX` cache interception is not clean enough
- compressed payload substitution is too invasive
- attention-time reconstruction cannot be bounded cleanly

## Deliverables To Expect

- feasibility note
- cache interception map
- asset manifest spec
- baseline benchmark report
- `TurboQuantmse 3.5-bit` prototype report
- variant decision memo
- profile recommendation memo

## One-Line Priority

Do not start quantization implementation until KV-cache interception feasibility is proven on the chosen local runtime.
