# TurboQuant Bootstrap Script Spec

## Status

Draft

## Purpose

This document specifies the bootstrap process that generates TurboQuant assets for MedMemory.

The bootstrap script exists so the runtime can:

- stay data-oblivious
- avoid request-time asset generation
- load versioned artifacts at startup

## Role in the System

The bootstrap script is responsible for generating or preparing:

- rotation assets
- integer-bit codebooks
- composite profile manifests
- outlier partition metadata
- optional residual/QJL assets for `TurboQuantprod`

The runtime is responsible only for:

- loading those assets
- validating them
- using them during inference

## Script Goals

The script should:

1. generate deterministic, versioned assets
2. emit a manifest linking all assets together
3. support the MacBook-first `MLX` plan without hard-coding MLX-specific math into asset generation
4. support Phase 1 text-generation KV-cache work

## Inputs

The bootstrap process should accept, directly or via config:

- target tensor dimension
- supported integer bit-widths
- composite profiles to build, such as `3.5-bit`
- outlier partition policy
- whether residual/QJL support is included
- output directory
- asset version or tag

## Outputs

At minimum, the bootstrap process should emit:

1. rotation assets
2. integer-bit codebook assets
3. profile manifests
4. partition metadata
5. top-level manifest with checksums and versioning

## Asset Requirements

### 1. Rotation assets

Rotation assets should include:

- target dimension
- seed or provenance metadata
- version metadata

The script should make it clear whether rotations are:

- generated deterministically from a seed
- or generated once and then frozen as immutable assets

### 2. Integer-bit codebooks

The script should support generation or import of:

- `1-bit`
- `2-bit`
- `3-bit`
- `4-bit`

For Phase 1, the minimum useful set is:

- the integer codebooks needed by the `3.5-bit` profile

The script should not assume:

- undocumented high-bit centroids can be copied from memory

It should instead:

- derive or import them from the same numerical family used by TurboQuant
- emit explicit metadata describing how they were obtained

### 3. Composite profiles

Composite profiles such as `3.5-bit` should be emitted as manifests, not as standalone codebooks.

Each profile manifest should declare:

- profile id
- required integer codebooks
- outlier group bit-width
- non-outlier group bit-width
- partition reference
- residual mode
- benchmark status such as `candidate` or `experimental`

For this repo:

- `3.5-bit` should be tagged as the default candidate
- `2.5-bit` should be tagged as experimental

### 4. Partition metadata

Partition metadata should support the initial fixed, versioned outlier policy.

The emitted metadata should answer:

- how many channels are treated as outliers
- how many as non-outliers
- whether the partition is global, per-layer, or per-head
- how the runtime should map channels to the chosen group

### 5. Residual/QJL assets

If `TurboQuantprod` is in scope, the bootstrap process should also define:

- QJL-related asset references
- any required seed or generation metadata
- linkage from the profile manifest to the residual mode

## Suggested CLI Shape

The exact CLI is implementation-dependent, but the bootstrap interface should support flags equivalent to:

- target dimension
- profile selection
- output dir
- asset version
- include residual mode
- partition policy

## Manifest Contract

The bootstrap process should write a top-level manifest containing fields such as:

- `asset_version`
- `generated_at`
- `generator`
- `target_dimensions`
- `profiles`
- `codebooks`
- `rotations`
- `partitions`
- `residual_assets`
- `checksums`

## Validation Rules

The bootstrap process should fail if:

- required integer codebooks cannot be produced
- composite profiles reference missing codebooks
- partition metadata is incomplete
- target dimensions are missing or inconsistent

The runtime should separately fail if:

- loaded assets do not match the live cache-shape contract

## Phase 1 Minimum Bootstrap Set

For the first `3.5-bit` prototype, the bootstrap process must generate:

- the required rotation asset
- the required integer codebooks
- the fixed outlier partition metadata
- the `3.5-bit` composite manifest
- a top-level asset manifest

Optional for Phase 1:

- `2.5-bit` composite manifest
- `TurboQuantprod` residual assets

## Non-Goals

The bootstrap script should not:

- perform request-time runtime logic
- decide final runtime selection
- benchmark the model
- silently mutate old assets in place

## Exit Condition

The bootstrap layer is ready when the runtime can be configured by:

- selecting an asset version
- selecting a profile id
- loading validated assets without recomputation
