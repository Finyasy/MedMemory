# TurboQuant Sprint 0 Feasibility Spec

## Status

Draft

## Purpose

This document defines the Sprint 0 feasibility spike for TurboQuant on MedMemory.

The purpose of Sprint 0 is to retire the highest-risk unknown before implementation:

- can the local MedGemma runtime on this MacBook support clean KV-cache interception or substitution?

If the answer is no, the implementation plan must pivot before deeper engineering begins.

## Why Sprint 0 Exists

TurboQuant is only useful in this repo if the runtime can:

1. observe K/V tensors when they are produced
2. replace or wrap raw cache storage with compressed payloads
3. recover values correctly at attention time

If that path is not feasible in the chosen runtime, then:

- the math may still be correct
- the docs may still be correct
- but the implementation path is not yet shippable

## Scope

Sprint 0 is a feasibility and architecture spike only.

It does **not** implement:

- final quantization logic
- final codebook generation
- production profile loading
- benchmark automation

It does investigate:

- current local MedGemma generation runtime
- KV-cache shape and lifecycle
- available extension points in `MLX`
- fallback feasibility in `Transformers on MPS`

## Primary Question

Can `MLX` on this MacBook support a bounded, maintainable TurboQuant KV-cache implementation for MedMemory?

## Secondary Questions

1. Where are K/V tensors created and cached in the current local generation flow?
2. Can cache writes be intercepted before raw tensors are retained?
3. Can compressed payloads be stored instead of raw tensors?
4. Can attention-time reconstruction or score-time use be inserted cleanly?
5. If MLX is not clean enough, is `Transformers on MPS` a better first prototype path?

## Investigation Targets

### Target A: MLX path

Inspect the current MLX text-generation runtime path used by MedMemory and answer:

- where generation starts
- where cache objects are instantiated
- whether cache storage is explicit or hidden inside a lower-level runtime
- whether the app can replace, wrap, or intercept cache writes and reads

### Target B: Transformers on MPS fallback

Inspect the fallback path and answer:

- whether `Transformers` exposes cleaner cache controls than MLX
- whether `past_key_values` or equivalent structures are easier to wrap
- whether that path would reduce architectural risk for the first prototype

### Target C: Cache-shape contract

Capture the minimal data contract required for TurboQuant:

- layer count
- head count
- per-head key/value dimension
- cache tensor layout
- per-token append/update behavior
- reconstruction point in the generation cycle

## Required Artifacts

Sprint 0 must produce:

1. **Runtime feasibility note**
   - short summary of what is and is not possible in MLX
2. **Cache interception map**
   - concrete notes on where K/V tensors are created, stored, and consumed
3. **Cache-shape contract**
   - the exact tensor dimensions TurboQuant assets must target
4. **Go/No-Go decision**
   - proceed MLX-first
   - or pivot first prototype to `Transformers on MPS`

The first concrete evidence package for this spec is:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/TURBOQUANT_SPRINT0_FEASIBILITY_NOTE.md`

## Evaluation Criteria

### Go MLX-first if all are true

- cache writes can be intercepted or replaced cleanly
- compressed payload storage is technically plausible
- attention-time reconstruction or scoring can be inserted without invasive runtime surgery
- the resulting architecture remains bounded and maintainable

### No-Go for MLX-first if any are true

- cache writes are opaque and not practically interceptable
- compressed payload substitution would require unstable runtime patching
- attention-time reconstruction cannot be inserted cleanly
- the implementation would depend on brittle internals with poor maintenance prospects

## Deliverable Format

The Sprint 0 output should be a short decision package containing:

- chosen runtime
- key evidence
- main constraints
- follow-on implications for Sprint 1 and Sprint 2

## Recommended Sequence

1. Inspect the existing MedMemory local generation path.
2. Map the MLX cache lifecycle.
3. Identify candidate interception strategies.
4. Compare the MPS/Transformers fallback path.
5. Freeze the runtime decision.

## Out of Scope

Sprint 0 does not decide:

- final outlier policy values
- final `TurboQuantmse` versus `TurboQuantprod` choice
- final `2.5-bit` viability

Those decisions depend on later benchmarks.

## Exit Condition

Sprint 0 is complete when the team can answer, unambiguously:

- which runtime is the first implementation target
- what cache shape TurboQuant must support
- whether the first prototype is technically viable on the MacBook
