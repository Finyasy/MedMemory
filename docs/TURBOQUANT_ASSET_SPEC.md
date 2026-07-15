# TurboQuant Asset Spec

## Status

Draft

## Purpose

Define the asset model for TurboQuant in MedMemory.

These assets are needed so the runtime can stay:

- data-oblivious
- startup-loaded
- fast during inference

## Principles

1. Assets are generated once and versioned.
2. Assets are loaded at startup, not learned at request time.
3. Composite profiles such as `3.5-bit` are defined as profile manifests, not single codebooks.
4. Assets must be tied to the actual quantized tensor dimension.

## Asset Classes

### 1. Rotation assets

Rotation assets define the random rotations used before scalar quantization.

Requirements:

- one or more `d x d` rotations
- `d` must match the quantized tensor axis
- versioned and deterministic once generated

Notes:

- for KV-cache work, `d` is usually the per-head K/V width or equivalent quantized channel dimension
- do not assume the full hidden size is the right dimension

### 2. Integer-bit codebooks

Integer-bit codebooks are the actual scalar quantization tables.

Supported examples:

- `1-bit`
- `2-bit`
- `3-bit`
- `4-bit`

Requirements:

- one codebook per supported dimension/bit-width combination
- generated from the same numerical procedure used for the TurboQuant family
- versioned explicitly

Do not assume:

- a single generic codebook is correct for all tensor dimensions
- undocumented higher-bit centroids should be hard-coded from memory

### 3. Composite profile manifests

Composite profiles define effective non-integer precisions such as:

- `2.5-bit`
- `3.5-bit`

These are not single codebooks.

Each composite profile should declare:

- profile id
- required integer-bit codebooks
- outlier/non-outlier partition policy
- bit allocation for each group
- whether `TurboQuantprod` residual correction is enabled

Example interpretation:

- `2.5-bit` may require `2-bit` and `3-bit` codebooks
- `3.5-bit` may require `3-bit` and `4-bit` codebooks

### 4. Outlier partition metadata

Outlier metadata defines how channels are split between:

- outlier
- non-outlier

For Phase 1, the expected policy is:

- fixed
- versioned
- reproducible

The metadata should define:

- partition id
- channel membership or channel-selection rule
- whether the split is global, per-layer, or per-head

### 5. Residual/QJL assets

If `TurboQuantprod` is enabled, the runtime also needs the residual-side configuration.

This should include:

- projection matrix specification or generation rule
- any deterministic seed/version metadata
- profile linkage to the relevant runtime mode

## Generation Strategy

Preferred generation pattern:

- use a bootstrap script inside the repo
- generate assets ahead of runtime
- write versioned outputs plus manifest metadata

Avoid:

- recomputing codebooks on every API startup
- request-time asset generation

Development-only exception:

- experimental mode may regenerate assets when explicitly requested

## Startup Loading Contract

At startup, the application should load:

- the required rotation assets
- the required integer-bit codebooks
- the active profile manifest
- the active outlier partition metadata
- residual/QJL assets if needed

Startup validation must confirm:

- required dimensions match the configured runtime
- required codebooks exist for the selected profile
- composite profiles reference valid integer codebooks
- the outlier partition metadata is present

## Suggested Manifest Fields

Each asset family should be tied together by a manifest with fields such as:

- `asset_version`
- `generated_at`
- `generator`
- `target_dimension`
- `supported_profiles`
- `codebooks`
- `rotations`
- `partitions`
- `residual_mode`
- `checksums`

## Failure Policy

Fail closed when:

- tensor dimensions do not match asset dimensions
- a selected profile references missing codebooks
- partition metadata is missing
- required residual assets are unavailable for `TurboQuantprod`

Do not silently degrade into mismatched assets.

## Phase 1 Required Assets

For the first `3.5-bit` prototype, the minimum asset set should include:

- the selected rotation asset for the target KV dimension
- integer-bit codebooks required by the `3.5-bit` profile
- the fixed outlier partition metadata
- a versioned composite profile manifest

For `2.5-bit`, add:

- the lower-bit composite profile manifest
- benchmark-only status in the profile metadata

For `TurboQuantprod`, add:

- residual/QJL assets and manifest linkage
