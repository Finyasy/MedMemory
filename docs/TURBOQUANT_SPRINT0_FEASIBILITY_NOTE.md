# TurboQuant Sprint 0 Feasibility Note

## Status

Initial repo inspection complete

## Decision Summary

Sprint 0 does **not** support a pure no-go conclusion for `MLX`.

It supports this narrower conclusion:

- `MLX` remains the preferred first prototype runtime
- MedMemory's **current** MLX integration is too high-level for TurboQuant work
- the installed `mlx_lm` runtime exposes lower-level cache hooks that appear sufficient for a bounded prototype
- the local MLX runtime is not yet proven stable in this environment, so `Transformers on MPS` must remain a live fallback

So the practical decision is:

- proceed `MLX`-first only through a **custom cache-aware generation path**
- do **not** try to bolt TurboQuant onto the current `mlx_lm.generate(...)` wrapper call in place
- keep an explicit pivot path to `Transformers on MPS` if MLX import/runtime stability is not resolved quickly

## What Was Inspected

### MedMemory runtime integration

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/model.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/config.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/medgemma-1.5-4b-it/config.json`

### Installed MLX runtime surfaces

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/generate.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/cache_prompt.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/cache.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/gemma3.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/gemma3_text.py`

## Key Findings

### 1. Current MedMemory MLX integration is too thin for TurboQuant

The current app-level MLX path in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/model.py` does this:

- lazy-load `mlx_lm.load(...)`
- call `mlx_lm.generate(...)`
- return a completed string

That means the current MedMemory integration:

- does not expose a prompt cache object
- does not expose per-token cache writes
- does not expose cache reads
- does not expose a hook for custom cache substitution

This is the core reason the current app path is insufficient.

### 2. The MLX library itself does expose cache primitives

The installed `mlx_lm` package is materially more capable than the current app integration.

Evidence:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/generate.py`
  - exposes `generate_step(...)`
  - accepts `prompt_cache`
  - accepts `kv_bits`, `kv_group_size`, and `quantized_kv_start`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/cache.py`
  - exposes `make_prompt_cache(...)`
  - defines `KVCache`, `RotatingKVCache`, and `QuantizedKVCache`
  - each cache object owns `update_and_fetch(...)`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/gemma3_text.py`
  - Gemma3 attention calls `cache.update_and_fetch(keys, values)`
  - model-specific `make_cache()` exists

This means MLX cache behavior is not fully opaque. There is a credible interception surface if MedMemory moves off the one-call `generate(...)` wrapper and onto a narrower generation path using explicit cache objects.

### 3. MedGemma text cache shape is now known

From `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/medgemma-1.5-4b-it/config.json` and the MLX Gemma3 model implementation:

- text hidden layers: `34`
- attention heads: `8`
- key/value heads: `4`
- per-head dimension: `256`
- max positions: `131072`
- sliding window: `1024`
- sliding window pattern: `6`

In the MLX Gemma3 text path:

- keys are shaped as `[B, n_kv_heads, seq, head_dim]`
- values are shaped as `[B, n_kv_heads, seq, head_dim]`
- for this model that means `[B, 4, seq, 256]`
- per-token append shape is effectively `[B, 4, 1, 256]`

This is enough to freeze the first asset-target assumption:

- the first TurboQuant cache profile should target the **per-head K/V width of `256`**, not the full hidden size of `2560`

### 4. Gemma3 cache policy is mixed, not uniform

The MLX Gemma3 text model does not use one cache type for every layer.

From `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.venv/lib/python3.12/site-packages/mlx_lm/models/gemma3_text.py`:

- every 6th layer uses full-attention `KVCache()`
- the other layers use `RotatingKVCache(max_size=1024)`

For MedGemma's `34` text layers, that means:

- global/full-attention cache layers: `6, 12, 18, 24, 30, 34`
- sliding-window rotating cache layers: all other text layers

Implication:

- a first TurboQuant prototype must account for **two cache behaviors**
- global layers and rotating layers may need separate handling or a shared wrapper that respects both contracts

### 5. Current MLX runtime stability is still a real risk

The local backend virtualenv contains `mlx_lm`, but importing it under direct Python inspection in this environment produced a native abort rather than a clean import.

That does **not** prove MLX is unusable in the app.

It does prove this:

- MLX runtime stability is not yet a solved assumption on this machine
- the first engineering task cannot be only “build TurboQuant hooks”
- it must also include “prove the MLX runtime path is stable enough to work against”

So the risk has moved from:

- "does MLX expose enough cache structure?"

to:

- "can we use those cache structures reliably in this local environment?"

### 6. Transformers on MPS remains the fallback, not the preferred first design

The current Transformers path in `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/llm/model.py` also uses high-level `self.model.generate(...)`.

So the repo does **not** currently expose `past_key_values` cleanly there either.

However, as a fallback, `Transformers on MPS` still matters because:

- it is a known and conventional generation stack
- a custom generation loop can be built around model forward calls if MLX proves unstable
- it gives a second path if Apple-side MLX runtime issues dominate Sprint 0

This keeps the conclusion disciplined:

- `MLX` looks better for cache modeling
- `MPS` remains safer as an architectural contingency

## Practical Interpretation

The main architectural risk was originally stated as:

- can MLX KV-cache writes and reads be intercepted cleanly enough to implement TurboQuant?

After inspection, that question can now be refined:

- **yes, likely at the library level**
- **no, not through MedMemory's current top-level MLX wrapper path**

That is an important reduction in uncertainty.

The risk is now mostly:

1. can MedMemory adopt a custom MLX generation path without destabilizing the backend?
2. can the local MLX runtime be made stable enough for that work?

## Recommended Sprint 0 Outcome

### Runtime choice

Keep `MLX` as the preferred first prototype target.

### Integration strategy

Do not modify the default `LLMService._generate_with_mlx()` path directly as the first step.

Instead:

- add a narrow experimental MLX generation path
- use explicit `prompt_cache`
- target `generate_step(...)` or `stream_generate(...)`
- keep the default user path unchanged until feasibility is proven

### Pivot condition

Pivot the first working prototype to `Transformers on MPS` if either becomes true:

- MLX import/runtime stability remains unreliable after a bounded stabilization pass
- the custom MLX cache-aware path requires invasive runtime surgery beyond a contained experiment

## Cache Interception Map

### Current app path

1. MedMemory calls `LLMService._generate_with_mlx(...)`
2. That calls `mlx_lm.generate(...)`
3. Response text returns as a completed string

Result:

- too high-level for TurboQuant cache interception

### Candidate MLX prototype path

1. MedMemory builds tokenized prompt
2. MedMemory creates `prompt_cache = make_prompt_cache(model)`
3. MedMemory generates through `generate_step(...)` or `stream_generate(...)`
4. Gemma3 attention updates cache via `cache.update_and_fetch(keys, values)`
5. custom cache logic or wrapper applies compression at the cache boundary

Result:

- bounded interception candidate
- aligns with actual MLX cache abstractions

## Recommendation For Sprint 1

Sprint 1 should begin with a bounded runtime spike, not full TurboQuant implementation.

The next concrete tasks should be:

1. prove MLX runtime stability inside the actual backend execution path
2. build a tiny experimental MLX text path using explicit `prompt_cache`
3. confirm cache objects are inspectable layer by layer for MedGemma text generation
4. only then define the exact TurboQuant wrapper or replacement strategy

## Final Go / No-Go Statement

### Go

Go forward with `MLX` as the first prototype target **only** through an explicit cache-aware generation path.

### Not approved

Do **not** proceed by trying to "drop TurboQuant into" the current one-line `mlx_lm.generate(...)` integration.

### Fallback retained

Retain `Transformers on MPS` as the first fallback if MLX runtime stability or maintainability fails the next bounded spike.
