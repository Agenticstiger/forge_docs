# LiteLLM Backend

[LiteLLM](https://github.com/BerriAI/litellm) is the canonical LLM backend on `v0.8.6` — every LLM call from `fluid forge`, `fluid ai`, and the copilot routes through it. LiteLLM replaced ~1,300 lines of per-provider wire-format code with one unified API; no extra install step, no toggle.

::: tip Where this fits
LiteLLM is wired into core `data-product-forge` (`litellm >= 1.83.7, < 2` is a hard dependency). The historical "opt-in extra" framing from pre-`0.8.0` docs is no longer accurate — the dispatcher always goes through LiteLLM. The companion [LLM Providers](/forge_docs/advanced/llm-providers.html) page covers which provider env vars to set; this page covers the routing-layer specifics.
:::

## Built-in providers

The dispatcher resolves `--llm-provider <name>` against this provider map (`fluid_build/cli/forge_copilot_llm_litellm.py`):

| Provider key | LiteLLM provider | Default model |
|---|---|---|
| `openai` | `openai` | `gpt-4.1-mini` |
| `anthropic` | `anthropic` | `claude-haiku-4-5` |
| `claude` (alias for `anthropic`) | `anthropic` | `claude-haiku-4-5` |
| `gemini` | `gemini` | `gemini-2.5-flash` |
| `google` (alias for `gemini`) | `gemini` | `gemini-2.5-flash` |
| `bedrock` | `bedrock` | `anthropic.claude-3-5-sonnet-20240620-v1:0` |
| `vertex` / `vertex_ai` | `vertex_ai` | `gemini-2.5-flash` |
| `ollama` | `ollama` (localhost-only) | `gemma3:4b` |

Beyond these built-ins, LiteLLM exposes 100+ providers through its catalog — point `--llm-model` (or `FLUID_LLM_MODEL`) at any model the LiteLLM docs list and the dispatcher routes the call.

## Quickstart

```bash
fluid forge --domain retail                                    # uses the configured default
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider bedrock --llm-model anthropic.claude-3-5-sonnet-20240620-v1:0
fluid forge --llm-provider vertex --llm-model gemini/gemini-2.5-pro
```

Per-call cost is attributed via LiteLLM's `usage.cost` field — accurate to the cent — and folded into `.fluid/agents/<run-id>/cost.json`. See [`fluid stats`](/forge_docs/cli/stats.html) for the cross-run aggregator.

## Configuration

| Env var | Purpose |
|---|---|
| `FLUID_LLM_PROVIDER` | Provider key (`openai` / `anthropic` / `gemini` / `bedrock` / `vertex` / `ollama`, etc.). Honoured as the default when `--llm-provider` is not passed. |
| `FLUID_LLM_MODEL` | Model name. Use LiteLLM's model-name conventions (e.g. `claude-haiku-4-5`, `gpt-4.1-mini`, `gemini/gemini-2.5-pro`). |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Provider keys. LiteLLM reads the same env-var names the underlying SDKs use. |
| `AWS_*` / `AWS_PROFILE` | Bedrock auth — standard AWS-CLI env vars. |
| `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT` / `VERTEX_LOCATION` | Vertex AI auth. |
| `FLUID_OLLAMA_MODEL` | Override the default Ollama model. |
| `LITELLM_*` | Any LiteLLM-specific env var (LiteLLM reads these directly; Forge doesn't filter them). |

See the canonical [environment variables index](/forge_docs/advanced/environment-variables.html) for everything else.

## Cost attribution

LiteLLM's `usage.cost` field is the authoritative per-call cost the LLM API itself reports, so the per-run `cost.json` and [`fluid stats`](/forge_docs/cli/stats.html) reflect billing-grade figures:

```python
# Internal — RunCostTracker.record_call accepts usd_override
tracker.record_call(
    provider="anthropic",
    model="claude-haiku-4-5",
    input_tokens=8420,
    output_tokens=1800,
    usd_override=0.0286,   # passed in from LiteLLM's reported cost
)
```

Runs from older releases that pre-date the LiteLLM unification still show the heuristic estimate until they age out of `.fluid/agents/`.

## Capability warnings

The capability catalog at `fluid_build/copilot/agents/capability_catalog.py` covers the canonical provider/model combinations. The warnings reflect the underlying model regardless of LiteLLM's routing layer — `claude-sonnet-4-6` warns identically whether reached via `anthropic` direct or via Bedrock.

If you point LiteLLM at a model the catalog doesn't know, the run-start banner says "model X is not in the capability catalog" and the run continues with conservative defaults. See [Capability Warnings](/forge_docs/advanced/capability-warnings.html#unknown-provider-model).

## Caveats

- Tool-use behaviour matches LiteLLM's wrapper. If you've been depending on a specific provider's exact tool-use response shape, surface mismatches will show up at the agent-layer error classifier — but the typed errors (`RateLimitError`, `ContextOverflowError`, etc. — see [Typed Errors](/forge_docs/advanced/typed-errors.html)) handle both wire shapes.
- Ollama is restricted to `localhost` (`127.0.0.1` / `::1`) by the SSRF guard. See [network safety](/forge_docs/advanced/network-safety.html).

## See also

- [LLM Providers](/forge_docs/advanced/llm-providers.html) — provider-specific env vars and auth modes
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — what the capability catalog enforces
- [Cost Tracking](/forge_docs/advanced/cost-tracking.html) — how cost figures land in `.fluid/agents/<run-id>/cost.json`
- [`fluid stats`](/forge_docs/cli/stats.html) — aggregating cost across runs
- [Environment variables](/forge_docs/advanced/environment-variables.html) — canonical `FLUID_*` reference
