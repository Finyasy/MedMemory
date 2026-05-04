# TurboQuant Benchmark Spec

## Status

Draft

## Purpose

Define the benchmark process for evaluating TurboQuant on MedMemory on a MacBook.

This spec is intended to answer:

- does KV-cache compression reduce local memory pressure materially?
- does `3.5-bit` preserve answer quality well enough to continue?
- does `2.5-bit` remain experimental or become viable?
- is `TurboQuantprod` necessary beyond `TurboQuantmse`?

## Scope

Phase 1 benchmark scope is limited to:

- MedGemma text-generation KV cache

Out of scope for this spec:

- multimodal generation
- retrieval/index compression
- document extraction
- speech
- training-time weight quantization

## Baseline Rules

All comparisons must be done:

- on the same MacBook
- with the same model
- with the same prompt set
- with the same runtime family

Preferred local baseline:

- `MLX`

Fallback/comparison baseline:

- `Transformers on MPS`

Do not use the paper's `NVIDIA A100` numbers as acceptance thresholds.

Use them only as directional reference.

## Evaluation Matrix

The minimum benchmark set is:

1. patient chat, short context
2. patient chat, long context
3. clinician summary
4. long document Q&A with grounding
5. long-context retrieval-style prompt inspired by "Needle-In-A-Haystack"

Priority emphasis:

- long-context record retrieval
- clinician summary
- long document Q&A
- patient chat

## Profiles To Compare

At minimum, benchmark:

1. full-precision baseline
2. `TurboQuantmse` at `3.5-bit`
3. `TurboQuantmse` at `2.5-bit` if available

Conditionally benchmark:

4. `TurboQuantprod` at `3.5-bit`
5. `TurboQuantprod` at `2.5-bit`

Use `TurboQuantprod` when:

- low-bit quality drift appears
- attention-sensitive outputs degrade
- `2.5-bit` becomes a serious target

## Metrics

### User-visible quality metrics

Track:

- answer correctness
- citation grounding quality
- refusal correctness
- summary completeness
- visible omission or drift under long context

### Long-context metrics

Track:

- retrieval/fact recall on long prompts
- long-context answer stability versus baseline

The main question is:

- does long-context factual behavior degrade materially relative to the local baseline?

### Internal distortion metrics

If the prototype exposes internals, track:

- reconstruction MSE
- inner-product error
- inner-product bias for `TurboQuantmse`
- inner-product variance for `TurboQuantprod`

These are diagnostic metrics, not the only acceptance gate.

### System metrics on MacBook

Track:

- time to first token
- tokens per second
- end-to-end latency
- memory pressure
- swap usage
- thermal slowdown or obvious system instability

The local success condition includes both:

- quality retention
- reduced unified-memory pressure

## Outlier-Policy Recording

Every run using a split-channel profile must record:

- outlier channel count
- non-outlier channel count
- bit-width assigned to each group
- active profile id
- whether the partition is fixed or adaptive

If quality regresses, review the outlier policy before dismissing the whole approach.

## Run Protocol

For trustworthy local comparison:

1. warm the model before measurement
2. avoid heavy concurrent local workloads
3. prefer plugged-in runs
4. run baseline and quantized profiles in the same environment
5. repeat enough times to detect obvious instability

## Acceptance Gates

### Gate A: MLX feasibility

Proceed MLX-first only if:

- KV-cache interception is possible
- compressed payloads can be stored
- attention-time behavior is recoverable correctly

### Gate B: 3.5-bit viability

`3.5-bit` is a strong candidate only if:

- memory pressure drops materially
- swap-heavy behavior is delayed or avoided
- no visible answer-quality regression appears in priority workloads

### Gate C: 2.5-bit viability

`2.5-bit` remains experimental unless:

- long-context drift is controlled
- grounding remains acceptable
- repeated runs show stable behavior

### Gate D: Variant choice

Choose the default variant based on evidence:

- prefer `TurboQuantmse` if `3.5-bit` is clean and simpler
- promote `TurboQuantprod` if low-bit inner-product drift materially affects quality

## Deliverables

The benchmark process should produce:

- baseline report
- per-profile comparison report
- quality drift summary
- memory and latency comparison
- recommendation on `TurboQuantmse` vs `TurboQuantprod`
- recommendation on `3.5-bit` default and `2.5-bit` status
