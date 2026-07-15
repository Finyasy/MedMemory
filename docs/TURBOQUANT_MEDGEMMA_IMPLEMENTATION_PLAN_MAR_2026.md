# TurboQuant x MedGemma Implementation Plan

## Purpose

This document explains how TurboQuant, based on the paper in `/Users/bryan.bosire/Downloads/TurboQuant.pdf`, should be evaluated and introduced into MedMemory without changing product behavior blindly.

The goal is not to "improve MedGemma's medical knowledge" directly. The goal is to improve the **runtime efficiency envelope** around MedGemma so the model can handle longer grounded contexts, lower memory pressure, and potentially serve more sessions with less quality loss.

Based on the source material, the most credible expected outcome is **large KV-cache compression with minimal quality loss**, not a direct reasoning-quality upgrade.

## Executive Summary

For MedMemory on a MacBook, this plan adopts the following implementation decisions:

- primary local runtime target: `MLX` on Apple Silicon
- Phase 1 scope: **text-generation KV cache only**
- default candidate profile: `3.5-bit`
- experimental candidate profile: `2.5-bit`
- first outlier policy: **fixed, versioned partition**
- first prototype style: **correctness-first**, even if it is not the fastest path
- startup asset strategy: **bootstrap script inside the repo**, then load assets at startup

These are implementation choices for this repo. They are not all directly established by the paper itself.

## Decision Log

### Current decisions

1. **Runtime target**
   - Use `MLX` as the preferred local runtime target on the MacBook.
   - Keep `Transformers on MPS` as a fallback or comparison path.
2. **Phase 1 scope**
   - Limit Phase 1 to text-generation KV-cache compression.
3. **Bit-width policy**
   - Treat `3.5-bit` as the default target.
   - Treat `2.5-bit` as experimental.
4. **Outlier policy**
   - Start with a fixed, versioned split-channel partition.
5. **Priority workloads**
   - Long-context record retrieval
   - Clinician summary
   - Long document Q&A
   - Patient chat
6. **Prototype philosophy**
   - Prefer correctness and observability before deeper optimization.
7. **Asset generation**
   - Generate assets with a bootstrap script in the repo and load them at startup.

## Companion Documents

- `docs/TURBOQUANT_ADR.md`
  - architecture decisions and trade-offs
- `docs/TURBOQUANT_BENCHMARK_SPEC.md`
  - benchmark matrix, MacBook baseline rules, and acceptance gates
- `docs/TURBOQUANT_ASSET_SPEC.md`
  - rotation/codebook/profile asset model and startup loading contract
- `docs/TURBOQUANT_SPRINT0_FEASIBILITY_SPEC.md`
  - MLX KV-cache interception feasibility and go/no-go gate
- `docs/TURBOQUANT_SPRINT0_FEASIBILITY_NOTE.md`
  - initial evidence note from repo inspection and provisional runtime recommendation
- `docs/TURBOQUANT_BOOTSTRAP_SCRIPT_SPEC.md`
  - bootstrap generation contract for TurboQuant assets
- `docs/TURBOQUANT_RUNTIME_HOOKS_NOTES.md`
  - runtime integration surfaces and hook candidates for MLX and MPS
- `docs/TURBOQUANT_EXECUTION_CHECKLIST.md`
  - short operator checklist for executing the plan end-to-end

## What TurboQuant Is

TurboQuant is an online vector quantization method designed for:

- low distortion under mean-squared error (MSE)
- low-distortion, unbiased inner-product estimation via a residual Quantized JL step
- online use, without expensive dataset-specific codebook training
- accelerator-friendly deployment for KV cache compression and vector search

### What "data-oblivious" and "online" mean here

These terms are easy to misread, so they should stay explicit in this plan.

They do **not** mean:

- internet-connected
- cloud-dependent
- remote inference

In the TurboQuant paper, they mean the following:

#### Data-oblivious

`Data-oblivious` means the quantization method does not need to be fit or calibrated on a specific dataset before it can be used.

For MedMemory, that means:

- no dataset-specific codebook training before deployment
- no patient-data-specific calibration pass
- no offline learning stage like traditional product quantization pipelines

The reason this is possible is:

- TurboQuant applies a random rotation to the vectors being quantized
- in high dimension, the rotated coordinates follow a predictable distribution
- because that distribution is mathematically tractable, scalar quantization codebooks can be precomputed once and reused

So, in practical MedMemory terms:

- the quantization assets are static runtime assets
- they can be generated once, versioned, and loaded at startup
- they do not need to be retrained on MedMemory records or MedGemma weights

#### Online

`Online` means the method is designed to run during live inference, in the moment that vectors are produced and cached.

For MedMemory, that means:

- quantization can happen during MedGemma generation
- K/V vectors can be compressed as they are written into the KV cache
- the method is intended to be lightweight enough for streaming generation rather than only batch preprocessing

This is the key operational contrast with slower offline methods:

- no heavy indexing/training stage before use
- no per-request learning step
- no expensive search over learned codebooks at runtime

So, in practical MedMemory terms:

- vectors are rotated and quantized at generation time
- compressed cache state is stored immediately
- the runtime remains suitable for local inference and streaming chat if the implementation stays fully vectorized

The paper claims several especially relevant practical results:

- KV-cache compression by **at least `4.5x`** and in some cases exceeding **`5x`**
- near quality neutrality for KV cache quantization at about `3.5 bits/channel`
- only marginal degradation at about `2.5 bits/channel`
- identical long-context retrieval behavior to full precision in the reported "Needle-In-A-Haystack" evaluation

The paper evaluates these gains on other decoder-based transformer models, not on MedGemma specifically. So these are strong prior expectations, not MedGemma-certified outcomes.

Those are promising results, but they are not MedGemma guarantees. They need to be reproduced on this app's workloads.

## Current MedMemory State

MedMemory already has several quantization and runtime controls:

- `backend/app/services/llm/model.py`
  - loads MedGemma through Transformers
  - prefers MLX on Apple Silicon when configured
  - already supports weight quantization paths
- `backend/app/config.py`
  - exposes `llm_use_mlx`
  - exposes `llm_mlx_quantized_model_path`
  - exposes `llm_mlx_quantization_bits`
  - exposes `llm_quantize_4bit`
- `backend/MODEL_SETUP.md`
  - documents the current `INT4` model-weight quantization flow

That matters because the app already compresses **weights**, but TurboQuant is most valuable for compressing **runtime vectors**, especially:

- MedGemma KV cache during long-context generation
- possibly embedding/index vectors later

So TurboQuant should be treated as a **runtime vector compression project**, not as a replacement for the current model download or 4-bit weight loading flow.

### FastAPI and MedMemory integration shape

For this codebase, TurboQuant should be integrated around the existing application lifecycle, not bolted onto individual endpoints.

The concrete MedMemory insertion points are:

- `backend/app/main.py`
  - already defines a FastAPI `lifespan` hook for startup/shutdown work
- `backend/app/services/llm/model.py`
  - already centralizes MedGemma loading and generation
  - currently routes text, multimodal, and streaming generation through `self.model.generate(...)`

That means the correct architecture is:

1. preload static TurboQuant assets during FastAPI startup
2. expose them through a dedicated runtime service next to `LLMService`
3. apply quantization inside KV-cache handling during generation
4. keep the external HTTP API unchanged

### Startup-loaded static assets

TurboQuant is data-oblivious, so it should use static, versioned assets rather than request-time fitting.

At startup, MedMemory should load or initialize:

- rotation matrices
- scalar quantization codebooks
- profile definitions for operating points such as `3.5-bit` and `2.5-bit`
- optional residual/QJL helper state if `TurboQuantprod` is enabled

Important correction:

- the rotation matrix dimension should match the tensor axis actually being quantized
- for KV-cache work, that is usually the per-head K/V vector width, not blindly the full MedGemma hidden size

So the working assumption should be:

- one or more `d x d` rotations where `d` matches the quantized head/channel dimension

### Why the codebooks can be precomputed

The codebooks are precomputable because TurboQuant does not try to learn centroids from MedMemory data or from MedGemma activations directly.

Instead, the method relies on a predictable distribution that appears after random rotation.

The high-level mechanism is:

1. apply a random rotation to a high-dimensional vector
2. treat each rotated coordinate as coming from a known distribution
3. solve a one-dimensional scalar quantization problem for that distribution
4. reuse the resulting centroids as a fixed codebook

#### The role of random rotation

After applying the random rotation, each coordinate of the rotated vector follows a mathematically predictable distribution on `[-1, 1]`.

The paper models this with a Beta-family density of the form:

`f(x) = Gamma(d/2) / (sqrt(pi) * Gamma((d-1)/2)) * (1 - x^2)^((d-3)/2)` for `x in [-1, 1]`

For implementation planning, the important point is not the exact formula itself. The important point is:

- the distribution is determined by the dimension `d`
- it does not depend on a particular patient dataset
- it does not depend on MedMemory retrieval examples
- it does not require retraining on MedGemma outputs

That is why the method stays data-oblivious.

#### Codebook generation as a 1D optimization problem

Once the rotated-coordinate distribution is known, the scalar codebook can be computed by solving a one-dimensional quantization problem for a chosen bit-width `b`.

Conceptually, the solver chooses `2^b` centroids that minimize expected squared error under that distribution.

In practice, this means:

- one codebook per supported dimension/bit-width combination
- Voronoi-style nearest-centroid assignment at runtime
- no dataset-specific k-means over MedMemory records

The paper describes this as a continuous one-dimensional k-means problem, typically solved numerically with a Lloyd-Max style procedure.

#### Important distinction: integer codebooks vs effective bit profiles

The documentation should be explicit here:

- integer bit-widths such as `1-bit`, `2-bit`, `3-bit`, and `4-bit` correspond to actual scalar codebooks
- effective precisions such as `2.5-bit` or `3.5-bit` do **not** correspond to one standalone scalar codebook

For MedMemory, that means:

- a `3.5-bit` runtime profile should be treated as a **composite profile**
- it will typically require two integer-bit quantizers, not one magical `3.5-bit` centroid table

In practical terms:

- `2.5-bit` is implemented by mixing something like `3-bit` outlier channels with `2-bit` regular channels
- `3.5-bit` is implemented by mixing something like `4-bit` outlier channels with `3-bit` regular channels

So when the app loads a `3.5-bit` profile, it should expect to load:

- a `3-bit` codebook
- a `4-bit` codebook
- plus the channel-partition metadata that decides where each codebook applies

It should **not** expect a single universal `3.5-bit` centroid table from the paper.

#### What the paper actually provides for centroids

The paper indicates that the authors numerically solved optimal scalar codebooks for bit-widths including `1`, `2`, `3`, and `4`.

But in the material we are using here, only the low-bit examples are explicitly written out.

The documented examples are:

- `1-bit`
  - centroids of the form `{± sqrt(2 / (pi d))}`
- `2-bit`
  - centroids of the form `{± 0.453 sqrt(d), ± 1.51 sqrt(d)}`

For higher integer bit-widths such as `3-bit` and `4-bit`:

- the paper states they can be obtained numerically
- the underlying procedure is the same Lloyd-Max style one-dimensional optimization
- the full centroid tables are not fully listed in the excerpted source material

For this repo, the safe planning assumption is:

- do not hard-code undocumented `3-bit` or `4-bit` centroid values from memory
- derive or import them from the same numerical procedure used for the published codebook family
- version them as explicit assets

#### High-dimensional simplification

In high dimension, the rotated-coordinate distribution becomes close to Gaussian.

That matters because:

- it makes standard codebook computation easier
- it helps justify reusable centroids at practical dimensions
- it explains why the codebooks can be prepared once and then reused broadly

For MedMemory, the safe interpretation is:

- codebooks should be tied to actual quantized tensor dimension
- the app should not assume a paper example centroid set is automatically correct for every MedGemma layer/head shape

#### What happens at runtime

At runtime, the API should not solve any new optimization problem.

The online path should only:

1. rotate the vector
2. assign each coordinate to the nearest centroid index
3. store the indices and any required metadata
4. reconstruct by reading centroids and rotating back when needed

That is why the method is lightweight enough for live inference when implemented correctly.

#### Startup loading vs startup computation

There is an important distinction between:

- codebooks being **precomputable**
- codebooks being **recomputed on every FastAPI startup**

For production MedMemory, the preferred pattern is:

- generate and version codebooks offline or during a bootstrap step
- load them during FastAPI startup
- validate that they match the configured tensor dimensions and bit-width profiles
- for composite profiles such as `3.5-bit`, validate that all required integer codebooks are present

The API should avoid numerically recomputing codebooks on every boot unless it is in an experimental or development-only mode.

### Dedicated runtime service, not route logic

TurboQuant logic should live in a dedicated runtime component, not in FastAPI route handlers.

That component should:

- own the loaded codebooks and rotation matrices
- expose vectorized quantize/dequantize operations
- expose cache-oriented APIs for compressed K/V storage and reconstruction
- hide whether the active mode is baseline, `TurboQuantmse`, or `TurboQuantprod`

Because MedMemory already runs through existing local inference backends, the first implementation should stay within the current stack and should **not** introduce JAX as a new dependency.

For this specific MacBook-oriented plan:

- the preferred local execution target is `MLX`
- `Transformers on MPS` remains a useful comparison and fallback path
- but the quantization logic itself should still be specified in a backend-neutral way where possible
- any MLX-specific optimization should come after the algorithm and metrics are validated

### Generation-path interception

The hard part is not the FastAPI endpoint layer. The hard part is intercepting MedGemma's cache behavior inside the Hugging Face generation path.

For this repo, the relevant integration point is inside `backend/app/services/llm/model.py`, where MedMemory currently delegates generation to `self.model.generate(...)`.

So the actual implementation will require MedMemory-specific engineering such as:

- a custom `past_key_values` or cache wrapper
- a Transformers-compatible cache backend
- or a narrow experimental generation path that quantizes keys and values before cache persistence

The paper does not specify this integration detail. It must be designed independently for this codebase.

### Async API, vectorized runtime

FastAPI endpoints should remain `async`, but TurboQuant should not become Python-level async token logic.

The right production pattern is:

- keep endpoints async for request concurrency
- keep quantization vectorized and colocated with inference
- avoid Python loops over tokens or channels
- never rebuild matrices or codebooks per request

### Compressed cache payloads

The runtime should store compressed cache payloads instead of raw float K/V tensors.

Depending on the chosen profile, this stored state may include:

- centroid indices
- outlier/non-outlier channel metadata
- residual sign sketches for `TurboQuantprod`
- residual scale or norm values required for reconstruction

That is the actual source of the expected `4.5x` to `>5x` memory reduction.

### Outlier-aware runtime profiles

The paper's non-integer bit-widths rely on different treatment of critical and non-critical channels.

So the implementation should assume named profiles such as:

- `turboquant_3_5bit`
- `turboquant_2_5bit`

Each profile can define:

- outlier channel allocation
- regular channel bit-width
- outlier channel bit-width
- whether residual QJL correction is enabled

### Outlier treatment strategy

To reach non-integer effective precisions such as `2.5-bit` or `3.5-bit`, the implementation should explicitly split channels into two groups and quantize them separately.

The required structure is:

1. partition channels into `outlier` and `non_outlier` sets
2. run one TurboQuant instance for outlier channels
3. run a second TurboQuant instance for non-outlier channels
4. combine the result into a weighted average effective bit precision

For the outlier group:

- use higher precision, for example `3 bits`
- prioritize preserving the most sensitive channels

For the non-outlier group:

- use lower precision, for example `2 bits`
- maximize memory reduction on the bulk of the cache

The paper's concrete `2.5-bit` example uses `128` total channels:

- `32` outlier channels at `3 bits`
- `96` non-outlier channels at `2 bits`
- effective precision: `(32 x 3 + 96 x 2) / 128 = 2.5 bits/channel`

This matters for MedMemory because it gives a practical path to:

- safe higher precision where it matters
- aggressive compression where it matters less
- non-integer operating points without changing the public API

#### What the paper specifies

The source material is clear about the **allocation pattern**, even if it is not fully explicit about the **selection rule**.

What the paper does specify is:

- channels are split into `outlier` and `non_outlier` groups
- two independent TurboQuant instances are applied to those two groups
- outliers receive higher precision
- non-outliers receive lower precision
- fixed-ratio examples are used in the reported experiments

So for documentation purposes, the safe statement is:

- the paper gives a concrete bit-allocation strategy
- it does **not** fully specify a universal MedGemma-specific outlier detector

#### Fixed-ratio experimental pattern

In the reported experiments, the outlier treatment appears as a fixed allocation pattern rather than a per-token dynamic thresholding rule.

The clearest example is the `128`-channel `2.5-bit` profile:

- `32` channels treated as outliers
- `96` channels treated as non-outliers
- outliers quantized at `3 bits`
- non-outliers quantized at `2 bits`

This is important for MedMemory because it suggests that the first implementation does **not** need to invent a token-by-token adaptive outlier detector on day one.

A practical first design can instead use:

- a fixed partition policy
- versioned profile definitions
- benchmark-driven revision if quality drift appears

This is also the chosen first policy for this repo.

#### What the paper does not specify

The paper does not provide a full mathematical step-by-step rule for identifying which exact channels should be classified as outliers for MedGemma.

That means the documentation should not overclaim:

- there is no paper-provided MedGemma outlier detector in this repo
- there is no paper-provided threshold formula here that can simply be copied into production
- the cited methodology is described as being consistent with prior work rather than fully rederived in the paper excerpt

So for MedMemory, outlier identification remains an implementation choice that must be validated locally.

#### What MedMemory still has to decide

The repo still needs an explicit policy for how outlier channels are chosen.

At minimum, that policy must answer:

- is the partition fixed or updated dynamically
- is the partition global, per-layer, or per-head
- is the partition derived from magnitude, variance, or another heavy-hitter signal
- is the partition the same across devices and runtimes

Because this project is being evaluated on a MacBook first, the practical bias should be toward:

- simple
- fixed
- reproducible
- benchmarkable

before attempting more complex adaptive policies.

Important limitation:

- the source material makes the split-channel strategy clear
- but it does not fully specify the exact MedGemma-specific outlier selection rule for this codebase

So MedMemory still needs to define and freeze:

- how outliers are identified
- whether the split is static or runtime-derived
- whether the split is global, per-layer, or per-head

Operationally, this strategy still remains `online`:

- the partitioning policy is chosen ahead of time
- the two TurboQuant instances operate during live generation
- the KV cache is written in compressed form during streaming inference

#### Recommended documentation stance

The strongest defensible wording for this repo is:

- MedMemory should document outlier handling as a **profiled split-channel policy**
- the first implementation should likely use a fixed, versioned partition
- any more advanced outlier detector should be introduced only after benchmark evidence shows that the fixed policy is insufficient

### TurboQuantmse vs TurboQuantprod

The main trade-off between the two variants is:

- `TurboQuantmse` is simpler and optimized for reconstruction fidelity
- `TurboQuantprod` is more complex but optimized for unbiased inner-product preservation

For MedMemory, this matters because transformer attention depends on inner products, while implementation cost and runtime simplicity still matter for production rollout.

#### TurboQuantmse

`TurboQuantmse` is the lower-complexity variant.

Its properties are:

- one-stage algorithm
- random rotation
- scalar quantization against precomputed codebooks
- optimized to minimize reconstruction mean-squared error

Its trade-off is:

- it is **biased** for inner-product estimation, especially at low bit-widths
- that bias decreases as bit-width increases
- at sufficiently high bit-widths, the practical penalty from that bias may become small enough to accept

This makes `TurboQuantmse` attractive for:

- first implementation prototypes
- simpler runtime integration
- operating points where reconstruction fidelity matters more than strict unbiasedness
- higher-bit regimes where bias is less concerning

#### TurboQuantprod

`TurboQuantprod` is the more attention-sensitive variant.

Its properties are:

- two-stage algorithm
- first applies `TurboQuantmse` with `b - 1` bits
- then quantizes the residual with a `1-bit` QJL transform
- stores additional residual-related information such as scale or norm
- provides **unbiased** inner-product estimates

Its trade-off is:

- more runtime complexity
- more bookkeeping in the cache representation
- more implementation effort in the generation path

This makes `TurboQuantprod` attractive for:

- low-bit regimes where inner-product bias would otherwise be problematic
- attention-sensitive transformer workloads
- cases where preserving inner-product behavior is the highest priority

#### Why the two-stage design exists

The two-stage design exists because an MSE-optimal quantizer is not automatically an inner-product-optimal quantizer.

In practical terms:

- `TurboQuantmse` is very good at reconstructing vectors
- but at low bit-widths it introduces systematic bias when those reconstructed vectors are used inside inner-product computations
- that is a real concern for transformer attention, where inner products are the core operation

`TurboQuantprod` is designed to bridge that gap:

- keep the strong reconstruction behavior of the MSE path
- then remove the inner-product bias through a residual correction step

#### Stage 1: MSE-optimal quantization

In the first stage, `TurboQuantprod` applies `TurboQuantmse` using `b - 1` bits from the total budget.

The purpose of this stage is:

- get a strong compressed approximation of the original vector
- minimize reconstruction error
- make the residual vector as small as possible

Formally, this produces:

- an MSE-reconstructed component
- a residual vector `r = x - x_tilde_mse`

That residual is exactly what the second stage operates on.

#### Stage 2: 1-bit QJL on the residual

In the second stage, `TurboQuantprod` applies a `1-bit` Quantized Johnson-Lindenstrauss transform to the residual.

The purpose of this stage is:

- correct the inner-product bias introduced by the first stage
- preserve geometric behavior more faithfully for attention and search workloads

Operationally, this produces:

- a sign-based sketch of the residual
- additional residual metadata such as norm or scale needed for reconstruction

The final reconstructed vector is then:

- the MSE component from stage 1
- plus the QJL-corrected residual component from stage 2

#### How inner products are computed under `TurboQuantprod`

For MedMemory, the important operational question is not only how vectors are compressed, but how the attention-time inner product is recovered from the compressed cache entry.

At a high level, the estimator uses:

- a query vector `y`
- the compressed cache payload for `x`
- the global TurboQuant assets such as rotations, codebooks, and the QJL projection matrix

For a compressed `TurboQuantprod` entry, the cache payload is conceptually:

- `idx` for the MSE-quantized component
- `qjl` for the residual sign sketch
- `gamma` for the residual magnitude or norm term

The estimator is then formed from two pieces:

- the inner product with the MSE-reconstructed component
- the inner product with the QJL-reconstructed residual component

Conceptually:

- `ip_estimate = <y, x_tilde_mse> + <y, x_tilde_qjl>`

Where:

- `x_tilde_mse` is reconstructed from the stored centroid indices and the inverse rotation
- `x_tilde_qjl` is reconstructed from the residual sketch using the paper's `DeQuantprod` scaling and projection rule

For the documentation in this repo, the important part is the structure, not memorizing the constant:

1. read `idx`, `qjl`, and `gamma` from the cache
2. reconstruct `x_tilde_mse`
3. reconstruct `x_tilde_qjl` using the paper's QJL dequantization formula
4. combine the two contributions for the attention-time inner product

This is why `TurboQuantprod` can remain unbiased for inner products:

- the MSE stage handles coarse reconstruction efficiently
- the QJL residual stage corrects the bias that the first stage would otherwise leave behind

#### Average inner product as a diagnostic signal

In the paper, average inner product is used as a way to study how error behaves as the underlying similarity level changes.

For MedMemory, that is useful as a diagnostic metric:

- under `TurboQuantmse`, bias can grow with the effective inner-product magnitude
- under `TurboQuantprod`, the goal is that bias stays at zero while variance remains stable

This makes average inner-product slices useful for analysis when a low-bit profile starts drifting.

But it should not be treated as the only production metric.

For this app, it is a supporting signal next to:

- answer quality
- citation correctness
- long-context recall
- latency and memory pressure

#### First implementation guidance for a MacBook

On a MacBook, the first implementation should prefer correctness and observability over clever kernel fusion.

So the initial local prototype should likely:

- reconstruct the two components explicitly
- compute the inner product in a clear, debuggable way
- expose intermediate metrics for drift analysis

This should be treated as a validation-first implementation choice, not as a claim that full-vector reconstruction is the only or final production path.

Only after that works should the implementation consider a more optimized path such as:

- direct score computation from compressed payloads
- fused attention-side reconstruction
- lower-level runtime-specific optimization

That is the right trade-off on Apple Silicon:

- validate the math first
- then optimize the path if the benchmark results justify the engineering cost

#### Why this matters for MedMemory

This is the mathematically stronger option for MedMemory whenever the application is sensitive to inner-product drift.

That includes:

- transformer attention during long-context generation
- attention-heavy low-bit KV-cache operation
- any future vector-search or ANN use of the same quantization family

The key point is:

- stage 1 keeps distortion low
- stage 2 removes the bias problem that low-bit MSE quantization alone can introduce

#### Practical implication for rollout

For MedMemory, this means `TurboQuantprod` should be considered the stronger candidate when:

- `2.5-bit` operation is a real target
- attention fidelity is degrading under `TurboQuantmse`
- benchmarks show systematic low-bit drift rather than just random noise

If those conditions do not appear, `TurboQuantmse` may still remain the better default because it is simpler to implement and cheaper to operate.

#### Practical guidance for MedMemory

The right default decision rule for this app is:

- start evaluation with `TurboQuantmse` because it is the simplest bounded prototype
- use `TurboQuantprod` if low-bit quality drift appears in attention-heavy workloads
- treat `TurboQuantprod` as the stronger candidate for aggressive profiles such as `2.5-bit`
- allow `TurboQuantmse` to remain a valid option for safer or higher-bit regimes if benchmarks stay clean

The most important point is:

- `TurboQuantmse` is easier to ship
- `TurboQuantprod` is safer mathematically for inner-product preservation

#### Variant trade-off table

| Feature | TurboQuantmse | TurboQuantprod |
|---|---|---|
| Primary goal | Minimize reconstruction MSE | Preserve inner products without bias |
| Inner-product bias | Biased, especially at low bits | Unbiased |
| Algorithm shape | 1-stage | 2-stage |
| Runtime complexity | Lower | Higher |
| Cache payload complexity | Lower | Higher |
| Best early use | Simpler prototype, higher-bit operation | Low-bit attention-sensitive operation |
| Best fit in MedMemory | First implementation pass | Fallback or promotion path when attention fidelity matters most |

#### Recommendation for rollout

For MedMemory, the practical rollout order should be:

1. implement the infrastructure so both variants are possible
2. benchmark `TurboQuantmse` first at `3.5-bit`
3. add `TurboQuantprod` if:
   - low-bit quality regressions appear
   - attention-sensitive outputs drift
   - `2.5-bit` becomes a serious target
4. prefer measured behavior over theoretical elegance when choosing the default runtime path

## What TurboQuant Would Improve For MedGemma

### Source-grounded expected impact

Applied to a decoder-based transformer model such as `medgemma-1.5-4b-it`, the most likely first-order effect is **significant KV-cache compression with little or no visible degradation at the right operating point**.

The source-backed expected benefits are:

- **Memory reduction**
  - KV cache compression should be expected in the range of roughly **`4.5x` to `>5x`**
  - non-integer operating points like `2.5-bit` and `3.5-bit` are practical, not just theoretical
  - the paper's setup uses mixed precision across channels, assigning more bits to outlier channels and fewer to regular channels
- **Maintained model quality**
  - at around `3.5 bits/channel`, the reported outcome is effectively **quality neutrality**
  - at around `2.5 bits/channel`, the reported outcome is **marginal quality degradation**
  - on long-context retrieval-style evaluation, the paper reports **identical performance to full precision**
- **Inference efficiency**
  - reduced KV-cache size lowers memory-bandwidth pressure
  - that should translate into lower latency and lower inference cost on long prompts
  - the algorithm is explicitly designed to be lightweight and accelerator friendly for online generation
- **Technical fit for transformer inference**
  - `TurboQuantprod` provides **unbiased inner-product estimates**
  - that matters for transformer attention behavior, where inner-product preservation is critical
  - the method is **data-oblivious**, so it does not require heavy codebook training or dataset-specific preprocessing before use
  - the method is **online**, so it is intended to operate during live generation rather than only as an offline preparation step

For MedMemory, this means the strongest expected product improvement is:

- more context retained during grounded generation
- less prompt shrinking under hardware limits
- fewer long-context failures
- better deployment headroom on local or constrained inference setups

### 1. Longer grounded context on the same hardware

This is the strongest expected benefit.

In MedMemory, long chats, large record summaries, multi-document prompts, and clinician workflows can all become KV-cache heavy. Current 4-bit model-weight quantization does not fully solve that. If TurboQuant behaves similarly on MedGemma, the app should be able to cut KV-cache memory by around `4.5x` or more while keeping answer quality nearly unchanged at safer operating points like `3.5 bits/channel`.

Expected product effect:

- fewer memory failures on long patient and clinician sessions
- more room for retrieved evidence in context
- more stable long-record summarization

### 2. Lower inference latency under long contexts

The paper frames latency improvement mainly as reduced memory bandwidth pressure between accelerator memory layers. That maps well to MedMemory because retrieval-augmented answers often force MedGemma to process long prompts with many chunks and citations.

Expected product effect:

- lower response latency on long prompts
- better throughput for local development and single-node deployment
- more predictable performance as context length grows

### 3. More useful MedGemma on constrained local machines

MedMemory already runs on Apple Silicon and mixed local setups. TurboQuant could expand what is practical locally, especially when MedGemma is used alongside:

- embeddings
- reranking
- speech
- document parsing

Expected product effect:

- better headroom on shared local hardware
- more stable demos with large patient histories
- less pressure to shrink prompts aggressively

### 4. Possible future gains for retrieval storage and ANN search

This is a secondary path, not the first one to implement.

The paper also shows strong retrieval/indexing behavior for vector search and reports indexing time that is effectively near-zero compared to codebook-trained approaches such as product quantization. MedMemory currently uses embeddings plus pgvector-style retrieval, and that stack is not an immediate drop-in target for TurboQuant. A later phase could evaluate a compressed ANN sidecar or archive tier, but that should not be the first delivery.

Expected future effect:

- smaller embedding storage footprint
- faster approximate retrieval experiments
- near-zero codebook/index training overhead compared with product quantization

## What TurboQuant Will Not Improve Directly

This needs to stay explicit:

- It will **not** directly improve MedGemma's medical reasoning quality.
- It will **not** replace RAG quality work.
- It will **not** replace domain fine-tuning or QLoRA.
- It will **not** fix hallucinations by itself.
- It will **not** improve retrieval relevance unless we later apply it to the retrieval/index layer.

If answer quality improves, it will usually be indirect:

- more relevant context fits in prompt
- fewer truncation tradeoffs
- less pressure to summarize evidence too aggressively before generation

The correct claim is:

- TurboQuant can help MedGemma **retain more useful context with less memory**
- TurboQuant does **not** make MedGemma clinically smarter on its own

## Recommended Scope

### Phase 1

Prototype TurboQuant only for:

- MedGemma text-generation KV cache

Do not start with:

- document extraction
- vision path
- embedding store compression
- speech path
- training-time weight quantization

Reason:

KV-cache compression is the cleanest path to measurable value in this app. It targets the main system bottleneck that current weight quantization does not fully solve.

It also fits the current backend well:

- FastAPI already has a startup lifecycle hook
- MedGemma already runs through a single service boundary
- the public API does not need to change
- the quantization assets can be preloaded once and reused without data-specific training

This document treats that scope as a fixed first step, not a tentative option.

### Phase 2

If Phase 1 works, expand to:

- clinician long-record summarization
- document-heavy patient Q&A
- optionally multimodal prompts if the runtime hook is stable

### Phase 3

Only after Phase 1 and 2 are validated:

- retrieval/index compression experiments for dense vectors

## Proposed Implementation Plan

### Sprint 0: Runtime feasibility spike

### Goal

Retire the highest-risk architectural unknown before investing heavily in implementation.

### Focus

Determine whether `MLX` on this MacBook can support clean KV-cache interception or substitution during MedGemma generation.

### Work

1. Trace where K/V tensors are created, cached, and read in the current local MedGemma runtime.
2. Identify whether the runtime allows:
   - interception of cache writes
   - substitution of compressed cache payloads
   - explicit reconstruction or score-time use during attention
3. Decide whether the cleanest first implementation path is:
   - `MLX` first
   - `Transformers on MPS` first
   - or a narrow experimental generation path
4. Write down the cache-shape contract needed by TurboQuant:
   - tensor dimension being quantized
   - layer/head layout
   - per-step cache update behavior

### Deliverables

- runtime feasibility note
- cache-shape and interception map
- go/no-go decision for `MLX` as the first working prototype target

### Decision gate

Proceed MLX-first only if cache interception is clean enough to:

- write compressed KV payloads
- recover attention-time values correctly
- keep the implementation bounded and maintainable

If not, switch the first working prototype target to `Transformers on MPS` while keeping the rest of the benchmark plan unchanged.

### Sprint 1: Design, instrumentation, and benchmark harness

### Goal

Create a reliable benchmark framework before changing inference.

### Work

1. Define a MedMemory-specific TurboQuant evaluation matrix.
   - short patient chat
   - long patient chat
   - clinician summary
   - long document-grounded answer
   - long-context retrieval-style prompt inspired by "Needle-In-A-Haystack"
   - prioritize MultiQA-style and summarization-style tasks first

2. Measure the baseline runtime first.
   - peak memory
   - time to first token
   - tokens/sec
   - end-to-end latency
   - max stable context length
   - output quality deltas

3. Reuse existing MedMemory evaluation surfaces where possible.
   - hallucination and grounding checks
   - local MedGemma smoke tests
   - clinician/patient prompt fixtures
   - QLoRA baseline-vs-adapter evaluation patterns where useful

4. Choose runtime target by platform.
   - on this MacBook, prefer `MLX` as the primary local target
   - keep `Transformers on MPS` as a fallback or comparison path
   - treat any CUDA path as a secondary research reference, not the main local acceptance target

5. Define the asset lifecycle explicitly.
   - what is generated by the bootstrap script
   - what is loaded in FastAPI lifespan
   - what dimensions are supported
   - which runtime profiles are exposed by config
   - how outlier partitions are defined and versioned

6. Define the bootstrap assets explicitly.
   - random rotation matrices generated once
   - integer-bit codebooks for the supported profiles
   - composite profile manifests such as `3.5-bit`
   - checksums and version metadata for all assets

### Deliverable

A benchmark report that answers:

- where MedMemory is currently bottlenecked
- how much of that is KV-cache pressure
- which workloads are worth quantizing first
- what the full-precision MacBook baseline looks like before any TurboQuant work

### Monitoring marginal degradation on a MacBook

Because MedMemory is being developed on a MacBook, the quality-monitoring plan should be tuned for **Apple Silicon local inference**, not copied directly from the paper's `NVIDIA A100` environment.

The correct benchmark rule is:

- compare quantized and non-quantized runs on the **same MacBook**
- use the **same runtime path** for both sides of the comparison
- treat the paper's A100 numbers as directional, not as acceptance thresholds

That means:

- if the local baseline is MLX, compare against MLX
- if the local baseline is Transformers on MPS, compare against that
- do not compare absolute latency or throughput numbers against the paper
- compare **relative degradation** and **relative efficiency gain** on your own machine

For this plan, the intended baseline is:

- `MLX` on the same MacBook, with the same model and prompt set

#### 1. Primary user-visible checks

The first acceptance layer should be user-visible MedMemory tasks, not only internal math metrics.

On a MacBook, the minimum practical benchmark set should include:

- short patient chat
- long patient chat
- clinician summary
- document-grounded answer with citations
- long-context retrieval-style prompt inspired by "Needle-In-A-Haystack"

For these runs, track:

- answer correctness
- citation grounding quality
- refusal correctness
- summary completeness
- visible drift in wording or omission under long context

#### 2. Long-context degradation checks

The paper's long-context results are useful as a pattern, but local MacBook testing should be sized to what the machine can sustain repeatably.

That means:

- use a MedMemory-specific long-context fixture set first
- add a local "needle in a haystack" style benchmark for retrieval from long prompts
- use context lengths that are realistic for the current MacBook runtime budget

The key signal is not matching the paper's exact context window. The key signal is:

- whether recall or factual extraction drops materially compared with the local baseline

#### 3. Internal distortion checks

If the prototype exposes KV-cache internals, then track geometric drift directly.

The most useful metrics are:

- reconstruction MSE
- inner-product error
- inner-product bias for `TurboQuantmse`
- inner-product variance for `TurboQuantprod`

For MedMemory, these metrics are secondary acceptance checks:

- they help explain failures
- they do not replace user-visible prompt evaluation

#### 4. Retrieval metrics only when retrieval is in scope

Metrics such as recall-at-k or top-k retention are important if TurboQuant is later applied to vector retrieval or ANN search.

For Phase 1 KV-cache work on MedGemma generation:

- retrieval metrics are optional supporting signals
- they are not the main acceptance gate

#### 5. Outlier-policy monitoring

If `2.5-bit` or other non-integer profiles are used, the outlier split must be part of the benchmark record.

Each run should capture:

- outlier channel count
- non-outlier channel count
- bit allocation per group
- observed quality change versus baseline

If quality regresses on the MacBook runtime, the first parameter to revisit is often:

- the outlier/non-outlier split

not necessarily the whole TurboQuant approach.

#### 6. MacBook system-health metrics

On a MacBook, system behavior itself can distort benchmarking if it is not controlled.

In addition to quality and latency, track:

- time to first token
- tokens per second
- end-to-end latency
- memory pressure
- swap usage
- whether the run triggered obvious thermal throttling or system slowdown

The important operational constraint on Apple Silicon is unified memory.

So the local success condition is not just "does quality hold?" It is also:

- does quantization materially reduce memory pressure on the same machine
- does it delay or avoid swap-heavy behavior
- does it keep long-context generation usable under local constraints

#### 7. Practical baseline discipline for local runs

To keep MacBook benchmark results trustworthy:

- run the baseline and quantized comparisons on the same machine
- keep the same model, prompt set, and runtime path
- warm the model before measuring
- avoid heavy concurrent local workloads during evaluation
- prefer plugged-in runs for repeatability when possible

The practical acceptance rule for this repo is:

- if `3.5-bit` reduces memory pressure materially on the MacBook with no visible answer-quality regression, it is a strong candidate
- if `2.5-bit` shows even small but repeatable quality drift in long-context grounded tasks, it should remain experimental until corrected

### Sprint 2: Controlled prototype on MedGemma KV cache

### Goal

Integrate a bounded experimental TurboQuant KV-cache path behind a feature flag.

### Work

1. Add an isolated quantization backend toggle.
   - baseline
   - experimental TurboQuant KV-cache path
   - named profiles for `3.5-bit` and `2.5-bit`
   - variant selection for `TurboQuantmse` vs `TurboQuantprod`

2. Start with the MSE-optimized path for KV tensors.
   - this is the lowest-complexity route
   - it is the most aligned with memory reduction and token generation efficiency
   - it should be implemented in a way that does not block later promotion to `TurboQuantprod`
   - use `3.5-bit` as the default first target profile

3. Keep the residual QJL inner-product correction as optional experimental work.
   - this corresponds to the stronger `TurboQuantprod` path
   - it is more important when unbiased inner-product preservation is the goal
   - it may be needed if the simpler MSE-oriented path shows quality drift in attention-sensitive workloads
   - it should be benchmarked explicitly before any aggressive low-bit rollout

4. Validate on MedMemory workloads, not paper proxies.
   - long retrieved medical contexts
   - structured answer generation
   - patient-friendly chat
   - clinician summarization
   - streaming generation behavior
   - long conversation continuation
   - compare against the full-precision baseline on the same MacBook

5. Compare at multiple operating points.
   - baseline
   - around `3.5 bits/channel`
   - around `2.5 bits/channel`
   - mixed outlier/non-outlier channel allocations where relevant
   - `TurboQuantmse` versus `TurboQuantprod` where attention fidelity is a concern

6. Confirm the backend shape is production-safe.
   - startup initialization cost is acceptable
   - no per-request asset recomputation
   - quantization remains vectorized
   - FastAPI concurrency behavior remains stable
   - outlier and non-outlier paths both behave correctly in streaming mode

### Deliverable

A go/no-go decision based on measured tradeoffs, not paper optimism.

Expected artifacts:

- prototype benchmark report for `TurboQuantmse`
- memory and latency comparison against baseline
- quality drift summary for `3.5-bit`
- recommendation on whether `TurboQuantprod` is needed next

### Sprint 3: Productization decision

### Ship only if all are true

- meaningful memory reduction is reproduced
- long-context latency improves materially
- grounded quality regression is negligible at the selected bit-width
- operational complexity remains manageable for MedMemory deployments

### If those conditions hold

Ship TurboQuant as:

- an opt-in runtime mode first
- then default it only on validated hardware/runtime combinations
- keep the HTTP API unchanged while runtime internals vary by deployment profile

### Sprint 3 deliverables

- decision memo for `TurboQuantmse` vs `TurboQuantprod`
- final profile recommendation for `3.5-bit`
- explicit statement that `2.5-bit` remains experimental unless it clears the same gates

## Architecture Fit for MedMemory

### Best initial insertion point

The best first insertion point is the MedGemma generation runtime, not the retrieval engine.

Why:

- current app pain comes from long grounded prompts and generation state
- existing repo already has MedGemma runtime abstraction points
- weight quantization is already present, so KV quantization is the next meaningful systems lever
- FastAPI startup already gives a clean place to load static TurboQuant assets

### Not the best initial insertion point

Applying TurboQuant directly to the current pgvector retrieval path is not the best first move.

Why:

- MedMemory's retrieval quality issues are currently more about benchmark/data quality and ranking than index compression
- current retrieval stack is grounded around standard embedding + DB search flows
- replacing that early would add complexity before proving value

## Expected Improvement Table

| Area | Expected effect | Confidence |
|---|---|---|
| Long-context MedGemma inference | Lower KV memory, longer usable context, likely `4.5x+` KV compression target | High |
| Local demo stability | Fewer long-context failures | High |
| Response latency on long prompts | Moderate to strong improvement if memory traffic is the bottleneck | Medium |
| Medical answer accuracy | No direct gain | High |
| Grounding quality | Indirect gain only if more evidence fits, with best odds near `3.5-bit` operation | Medium |
| Retrieval relevance | No direct gain in Phase 1 | High |
| Embedding/index footprint | Possible later gain, with attractive online indexing characteristics | Medium |

## Risk Register

### 1. Paper-to-product gap

TurboQuant results were not reported on MedGemma or MedMemory-specific tasks.

Implication:

Do not commit to the paper's quality-neutral claim, `4.5x+` compression target, or "identical long-context performance" claim until local evidence confirms it on MedGemma.

### 2. Runtime compatibility gap

MedMemory supports Apple Silicon and MLX, while many quantization experiments are easier on CUDA/Transformers first.

Implication:

The working assumption here is:

- local MacBook evaluation should target `MLX` first
- other runtimes remain useful for comparison, but not as the primary local decision basis
- CUDA/Transformers results may still be useful as research comparisons, but they are not the main local acceptance gate

The concrete risk inside that statement is:

- whether the chosen local runtime allows clean KV-cache interception or substitution

If cache writes and reads cannot be controlled cleanly, then:

- the TurboQuant math may still be valid
- but the implementation path for MedMemory on the MacBook is not yet shippable

### 3. MedGemma-specific behavior

The MedGemma model card already warns that MedGemma is sensitive to prompting and not optimized for multi-turn behavior.

Implication:

TurboQuant must be tested on:

- multi-turn chat
- citation-heavy prompts
- refusal paths
- clinician structured outputs

### 4. Quality drift at aggressive bit-widths

The paper's `2.5-bit` regime may still be too aggressive for some grounded medical generation tasks.

Implication:

The likely product-safe path is:

- evaluate `3.5-bit` first
- only use more aggressive compression where benchmarks stay clean

### 5. Integration complexity inside Transformers generation

The paper describes the quantization algorithm, but not how to hook it into the Hugging Face generation/cache stack used by MedMemory.

Implication:

- cache interception is a separate engineering task
- the first proof-of-concept may need a narrow experimental path
- the design should avoid brittle invasive patching where possible

### 6. Startup asset correctness

If codebooks, rotations, or dimension assumptions are wrong, the quantization path will be invalid.

Implication:

- assets should be deterministic and versioned
- supported tensor dimensions must be explicit
- runtime assertions should fail closed on dimension mismatch

### 7. Outlier policy ambiguity

The high-level outlier treatment strategy is clear, but the exact outlier-selection method for MedGemma is not fully specified by the paper excerpt.

Implication:

- MedMemory must choose an explicit policy and document it
- that policy should be benchmarked like any other runtime parameter
- non-integer bit profiles should not be treated as complete until this policy is stable

## Validation Criteria

TurboQuant should be considered successful for MedMemory only if it shows:

1. KV-cache compression that approaches the paper's practical range, ideally around `4.5x` or better on target workloads
2. a meaningful increase in stable usable context window on local target hardware
3. no material regression in grounded medical answer quality at the chosen operating point
4. no meaningful increase in unsupported or hallucinated output
5. no degradation of clinician-facing structured summaries beyond agreed thresholds
6. best-case validation at `3.5-bit`, and only conditional rollout consideration at `2.5-bit`
7. FastAPI startup and generation remain operationally simple enough for local and production deployment
8. the chosen default variant is justified by benchmark evidence, not only by implementation simplicity

## Recommendation

The right implementation order is:

1. benchmark first
2. prototype KV-cache quantization only
3. validate on real MedMemory prompts
4. ship only after quality stays stable
5. consider retrieval/index compression later as a separate project

From a backend architecture perspective, the right concrete pattern is:

1. preload static TurboQuant assets in FastAPI lifespan
2. expose them through a dedicated quantization runtime service
3. intercept KV-cache writes inside `LLMService`
4. keep API contracts unchanged
5. validate `3.5-bit` first before considering more aggressive profiles

This is the pragmatic expectation:

- TurboQuant can make MedGemma **cheaper, longer-context, and faster under memory pressure**
- TurboQuant will **not** make MedGemma smarter by itself
- the real user-facing value comes from fitting more grounded medical context into the same runtime budget

## Bottom Line

For MedMemory, TurboQuant is most promising as a **KV-cache efficiency upgrade** for MedGemma, not as a direct reasoning upgrade.

If validated locally, the main gains should be:

- longer grounded context
- lower memory pressure
- better latency under large prompts
- more reliable local and single-node deployment
- potentially `4.5x` or greater KV-cache compression with minimal visible quality loss at safe operating points

The improvement to MedGemma is therefore best described as:

**better runtime efficiency and context capacity, potentially with near-neutral quality at around `3.5 bits/channel`, not a direct increase in clinical intelligence.**
