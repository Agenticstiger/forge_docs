# LiteLLM Backend

[LiteLLM](https://github.com/BerriAI/litellm) is the LLM backend for the `openai`, `anthropic`, `gemini` and `ollama` providers. It is a core dependency of `data-product-forge`: there is no extra to install and no toggle. The `mcp-sampling` provider and the local agent CLIs (`claude-code`, `codex`, `cursor`, `kiro`) do not go through it; see [LLM Providers](./llm-providers.md).

::: tip Where this fits
LiteLLM is a hard dependency of core `data-product-forge` (`litellm>=1.83.7,<2` on Python 3.11 and later). The `litellm` extra still exists and is empty, so `pip install "data-product-forge[litellm]"` installs nothing beyond the base package. The companion [LLM Providers](./llm-providers.md) page covers which providers `--llm-provider` accepts and which environment variables to set; this page covers the routing layer.
:::

## Which providers you can select

`fluid forge --llm-provider` accepts `openai`, `anthropic` (alias `claude`), `gemini` and `ollama` for the LiteLLM backend, plus the keyless providers described in [LLM Providers](./llm-providers.md). The backend maps each of those names to a LiteLLM model prefix and falls back to a default model when you give none:

| Provider | LiteLLM prefix | Backend fallback model |
|---|---|---|
| `openai` | `openai` | `gpt-4.1-mini` |
| `anthropic`, `claude` | `anthropic` | `claude-haiku-4-5` |
| `gemini` | `gemini` | `gemini-2.5-flash` |
| `ollama` | `ollama` (localhost only) | `gemma3:4b` |

A forge run normally gets its model from `fluid ai models`, which is `claude-sonnet-4-6` for Anthropic, `gemini-2.5-pro` for Gemini and `gemma4:latest` for Ollama; the fallback column applies only when nothing names a model.

The backend's routing table also maps `groq`, `bedrock`, `azure`, `vertex` and `vertex_ai`, `mistral`, `cohere` and `github` to LiteLLM prefixes. As of 0.18.1 the argument parser rejects those names for `--llm-provider`, and `FLUID_LLM_PROVIDER=bedrock` is refused with `Unknown LLM provider 'bedrock'`, so they cannot be selected from the CLI:

```text
fluid forge: error: argument --llm-provider: invalid choice: 'bedrock' (choose from 'openai', 'anthropic', 'claude', 'gemini', 'ollama', 'mcp-sampling', 'claude-code', 'codex', 'cursor', 'kiro')
```

## Quickstart

```bash
fluid forge --domain retail                                    # uses the configured default
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider ollama --llm-model gemma4:latest
```

LiteLLM reports the cost of each call, and Forge folds it into `.fluid/agents/<run-id>/cost.json`. See [`fluid stats`](../cli/stats.md) for the cross-run aggregator.

## Configuration

| Env var | Purpose |
|---|---|
| `FLUID_LLM_PROVIDER` | Provider key (`openai`, `anthropic`, `gemini`, `ollama`, and the keyless providers). Used when `--llm-provider` is not passed. |
| `FLUID_LLM_MODEL` | Model name. |
| `FLUID_LITELLM_MODEL_PREFIX` | Replace the LiteLLM prefix Forge puts in front of the model name (`<prefix>/<model>`). |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Provider keys. LiteLLM reads the same names the underlying SDKs use. |
| `OLLAMA_HOST` | Ollama endpoint. Local addresses only. |
| `LITELLM_*` | Any LiteLLM-specific variable. LiteLLM reads these directly; Forge does not filter them. |

See the [environment variables index](./environment-variables.md) for everything else.

## Cost attribution

LiteLLM reports a per-call cost, which Forge records in the per-run `cost.json` that [`fluid stats`](../cli/stats.md) aggregates.

Where LiteLLM reports no cost for a call, the figure comes from the price table in [Cost Tracking](./cost-tracking.md).

## Capability warnings

The capability catalog at `fluid_build/copilot/agents/capability_catalog.py` covers the provider and model combinations Forge knows. The warnings describe the model, not the route to it.

If you point LiteLLM at a model the catalog doesn't know, the run-start banner says "model X is not in the capability catalog" and the run continues with conservative defaults. See [Capability Warnings](./capability-warnings.md#unknown-provider-model).

## Caveats

- Tool-use behaviour matches LiteLLM's wrapper. Provider failures surface as the typed errors described in [Typed Errors](./typed-errors.md) (`RateLimitError`, `ContextOverflowError` and the others).
- Ollama is restricted to `localhost` (`127.0.0.1` / `::1`) by the SSRF guard. See [network safety](./network-safety.md).

## See also

- [LLM Providers](./llm-providers.md): which providers `--llm-provider` accepts and their credentials
- [Capability Warnings](./capability-warnings.md): what the capability catalog enforces
- [Cost Tracking](./cost-tracking.md): how cost figures land in `.fluid/agents/<run-id>/cost.json`
- [`fluid stats`](../cli/stats.md): aggregating cost across runs
- [Environment variables](./environment-variables.md): the `FLUID_*` reference
