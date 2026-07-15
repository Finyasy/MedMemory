# TurboQuant Runtime Hooks Notes

## Status

Working notes

## Purpose

Capture the runtime integration surfaces that matter for a TurboQuant KV-cache prototype in MedMemory.

This is not code. It is a map of where implementation work is likely to happen and what questions need to be answered first.

## Primary Integration Surface

The most important runtime surface is:

- `backend/app/services/llm/model.py`

Why:

- it is the MedGemma service boundary in this repo
- it already centralizes local generation behavior
- text, multimodal, and streaming flows all converge there

## Startup Integration Surface

The startup integration surface is:

- `backend/app/main.py`

Why:

- it already has a FastAPI lifespan hook
- TurboQuant assets should be loaded at startup, not request time

## Local Runtime Paths To Evaluate

### Path A: MLX

This is the preferred local target on the MacBook.

Questions to answer:

- where is cache state created?
- is cache management explicit enough to intercept?
- can compressed payloads replace raw tensors?
- can attention-time reconstruction be inserted cleanly?

This path is preferred only if those answers are good enough to keep the prototype bounded.

### Path B: Transformers on MPS

This is the fallback/comparison path.

Questions to answer:

- does this path expose `past_key_values` or equivalent structures more clearly?
- is cache wrapping easier here than in MLX?
- would it reduce implementation risk for the first working prototype?

## Hooking Goals

Any viable runtime path must support these four capabilities:

1. observe K/V tensors at creation time
2. store compressed payloads instead of raw cache tensors
3. recover values or scores during attention
4. keep the change contained enough to maintain

## Candidate Hooking Strategies

### Strategy 1: Cache wrapper

Wrap the runtime's cache representation with a structure that:

- compresses on write
- reconstructs or serves data on read

Best case:

- minimal changes to generation orchestration

Risk:

- runtime may not expose cache boundaries cleanly enough

### Strategy 2: Narrow experimental generation path

Introduce a separate experimental generation path for the prototype.

Best case:

- easier to reason about correctness
- reduced risk of contaminating the default path

Risk:

- code duplication
- more maintenance overhead

### Strategy 3: Attention-side score computation from compressed payloads

Instead of fully reconstructing tensors everywhere, compute what attention needs from compressed payloads directly.

Best case:

- lower long-term overhead

Risk:

- too complex for the first prototype
- harder to debug on the MacBook

## Recommended Hooking Order

1. Map the current cache lifecycle.
2. Try to identify a bounded cache wrapper path.
3. If wrappering is unclear, use a narrow experimental generation path.
4. Delay any optimized direct-score path until after correctness is proven.

## MacBook-Specific Guidance

For the first local prototype on Apple Silicon:

- prefer correctness over maximum performance
- prefer explicit reconstruction over opaque cleverness
- keep the instrumentation strong enough to explain drift

This is especially important because:

- unified memory pressure is a real constraint
- local benchmarking must be interpretable
- runtime-specific debugging cost on MLX can be high if the path is too clever too early

## Notes On What The Paper Does Not Give You

The paper gives:

- quantization math
- distortion guarantees
- reconstruction logic
- the two-stage `TurboQuantprod` idea

The paper does not give:

- an MLX integration pattern
- a Hugging Face/MLX cache API
- a FastAPI app structure
- a MedGemma runtime hook implementation

So this document exists to keep that gap explicit.

## Decision Use

This notes document should feed directly into:

- `docs/TURBOQUANT_SPRINT0_FEASIBILITY_SPEC.md`
- `docs/TURBOQUANT_ADR.md`

## Exit Condition

These notes have served their purpose when the team can point to:

- the first prototype runtime target
- the interception strategy
- the cache-shape contract
- the startup asset-loading boundary
