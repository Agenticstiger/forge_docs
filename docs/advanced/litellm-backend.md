# LiteLLM Backend (opt-in)

The `feat/source-aligned-acquisition` branch ships an opt-in `LiteLLMProvider` that routes every LLM call through [LiteLLM](https://github.com/BerriAI/litellm) instead of Forge's native per-provider HTTP shapes. Enable it for unified routing, accurate per-call cost attribution, and access to LiteLLM's broader provider catalog.

::: tip Where this fits
LiteLLM is a routing-layer alternative to the native provider stack documented at [LLM Providers](/forge_docs/advanced/llm-providers.html). Both stacks share the same `LlmProvider` base class — switching between them is a one-env-var flip.
:::

## Enabling

```bash
pip install 'data-product-forge[litellm]'

export FLUID_LLM_BACKEND=litellm
fluid forge --domain retail
```

That's it. The dispatcher in `cli/forge_copilot_llm_providers.py::get_llm_provider` short-circuits to `LiteLLMProvider` when the env var is set; `call_llm` and `call_llm_streaming` route through it transparently.

## What changes

| Aspect | Native stack | LiteLLM stack |
|---|---|---|
| Provider list | Anthropic / OpenAI / Gemini / Azure / Ollama (5 hand-rolled) | 100+ providers via LiteLLM's catalog |
| Cost attribution | Heuristic estimator (token counts × price/token table) | LiteLLM's per-call `usage.cost` field — accurate to the cent |
| Streaming | Native SSE per provider | LiteLLM's unified streaming wrapper |
| Tool use | Native per-provider tool-use shapes | LiteLLM's unified `tools` parameter |
| Prompt caching | Native (Anthropic only) | Whatever LiteLLM passes through |
| Token-usage capture | SSE wire decoder per provider | LiteLLM's `usage` callback |

## Configuration

| Env var | Purpose |
|---|---|
| `FLUID_LLM_BACKEND=litellm` | Activate the LiteLLM stack |
| `FLUID_LLM_MODEL` | Model name. Use LiteLLM's model-name conventions (e.g. `claude-3-5-sonnet-20241022`, `gpt-4.1-mini`, `gemini/gemini-2.5-pro`). |
| `FLUID_LITELLM_MODEL_PREFIX` | Override the prefix LiteLLM uses for niche providers — e.g. `azure/`, `bedrock/`. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Provider keys, same as the native stack. |
| `LITELLM_*` | Any LiteLLM-specific env var (LiteLLM reads these directly; Forge doesn't filter them). |

## Cost attribution

The native stack estimates cost from input/output token counts via an internal price table that gets stale every time providers change pricing. LiteLLM's `usage.cost` field is the authoritative per-call cost the LLM API itself reports, so:

```python
# Internal — RunCostTracker.record_call signature gained usd_override
tracker.record_call(
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    input_tokens=8420,
    output_tokens=1800,
    usd_override=0.0286,   # passed in from LiteLLM's reported cost
)
```

`fluid stats` ([page](/forge_docs/cli/stats.html)) and the per-run `cost.json` show the LiteLLM-reported figure when `FLUID_LLM_BACKEND=litellm`. Older runs (or runs on the native stack) keep using the heuristic estimate.

## Capability warnings

The capability catalog at `fluid_build/copilot/agents/capability_catalog.py` covers the native-stack provider/model combinations. When you switch to LiteLLM, the catalog still applies (LiteLLM is just a router) but the warnings reflect the underlying model — `litellm + claude-sonnet-4-6` warns identically to `anthropic + claude-sonnet-4-6`.

If you point LiteLLM at a model not in the catalog, the run-start banner says "model X is not in the capability catalog" and the run continues with conservative defaults. See [Capability Warnings](/forge_docs/advanced/capability-warnings.html#unknown-provider-model).

## When to use LiteLLM vs. native

| Use LiteLLM when | Use native when |
|---|---|
| You need a provider not in the native 5 (Bedrock, Vertex direct, Cohere, Mistral cloud, etc.) | You're on Anthropic / OpenAI / Gemini / Ollama and want fewest dependencies |
| You want per-call cost accurate to the cent (LiteLLM passes through provider billing) | You're cost-budgeting at the run level — heuristic is good enough |
| You're already running LiteLLM as a routing proxy in production and want Forge to use the same path | You want zero new runtime deps |
| You want to A/B test models without code changes | — |

The two stacks coexist safely — you can flip `FLUID_LLM_BACKEND` per run without touching contracts or config.

## Caveats

- LiteLLM is an extra at install time (`pip install 'data-product-forge[litellm]'`). Without it, setting `FLUID_LLM_BACKEND=litellm` raises `MissingExtraError` at run start.
- Tool-use behaviour matches LiteLLM's wrapper, not the native shape. If you've been depending on Anthropic's exact tool-use response shape (rare), switching to LiteLLM may surface differences.
- The agent-layer typed errors (`RateLimitError`, `ContextOverflowError`, etc. — see [Typed Errors](/forge_docs/advanced/typed-errors.html)) still fire under LiteLLM; the classifier handles both wire shapes.

## See also

- [LLM Providers](/forge_docs/advanced/llm-providers.html) — the native stack
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — what the capability catalog enforces under both stacks
- [Cost Tracking](/forge_docs/advanced/cost-tracking.html) — how cost figures land in `.fluid/agents/<run-id>/cost.json`
- [`fluid stats`](/forge_docs/cli/stats.html) — aggregating cost across runs
