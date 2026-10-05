# Capability Warnings

When a `fluid forge data-model` run is given an explicit `--llm-provider`, `--llm-model` or `--llm-endpoint`, the CLI checks that (provider, model) pair against a capability catalog before the run starts. If the pair lacks something the run needs (structured-output enforcement), or is not in the catalog at all, you see a warning and the run continues with degraded behaviour. Without any of those three flags, no check runs.

This page tells you what the warnings mean, what to do about them, and which (provider, model) combinations are catalogued.

::: tip Warning or error?
A capability warning is not a failure. If a run does fail, the error is in [Forge Agent Errors](./typed-errors.md) (LLM provider and output errors) or [Typed CLI Errors](./typed-cli-errors.md). Two typed errors link to this page because the CLI's route table sends them here: `CapabilityMismatchError`, raised when a build asks a runner for a capability it does not declare (such as `exactly_once`), is covered under [Capability negotiation](./typed-cli-errors.md#capability-negotiation) and has nothing to do with the LLM catalog below.
:::

## What the warning looks like

This is real output for a model that cannot enforce structured output:

```bash
fluid forge data-model from-intent intent.yaml --output out.fluid.yaml \
  --llm-provider ollama --llm-model gemma2:9b --dry-run
```

```text
⚠️  ollama/gemma2:9b does not reliably support structured output — agent runs 
may produce degraded output.
⚠️  Note for ollama/gemma2:9b: gemma2 does not support tool calling. Use gemma3+
if you need the multi-turn agent loop on Ollama.
capability_warnings_count=2 provider=ollama model=gemma2:9b
```

The first lines are user-facing warnings, printed through the standard CLI console, which also applies the secret-redaction filter, so they are safe to share in bug reports. The `capability_warnings_count=...` line is a structured log line.

## When the warning fires

### Missing required capability

The "what is required" set depends on the usage profile of the run. The catalog defines two:

- **`staged_pipeline`**: each stage is one LLM call, so it requires `structured_output` only. This is the profile `fluid forge data-model` passes.
- **`agent_loop`**: the multi-turn tool-driven loop requires `tool_use` and `structured_output`. As of 0.18.1, no CLI command passes this profile, so the catalog's `tool_use` column matters only through the catalog's notes and through the Python API.

Concretely, on `fluid forge data-model`:

- `gpt-3.5` warns: it has no strict structured output.
- `gemma2:9b` warns: no structured output on Ollama models (the example above).
- `claude-sonnet-4-6` is silent: full support.

### Unknown (provider, model)

If the model is not in the catalog, you get a "not in the capability catalog" warning. The run continues with the conservative fallback capabilities (streaming on, tool use off, structured output off). If the model supports more than that, see [Adding a model to the catalog](#adding-a-model-to-the-catalog).

### Operational notes

Even when a pair passes the requirements check, the catalog may attach a note, which is printed as a warning. Examples:

- `claude-opus-4-7`: "Temperature is deprecated on Opus 4.7 — providers drop it automatically."
- `gemma4`: "gemma4 is the project's default Ollama model. Tool-use accuracy is acceptable for the staged pipeline; the multi-turn agent loop may need more iterations to converge than on hosted providers."
- Ollama `llama3.1`: "Tool-use accuracy on Ollama-served llama3.1 is lower than on hosted Anthropic / OpenAI / Gemini models. Expect more tool-call validation errors."

Notes are informational and do not block the run.

## Silencing the warning

```bash
# One run
FLUID_QUIET=1 fluid forge data-model from-intent intent.yaml --output out.fluid.yaml --llm-provider ollama --llm-model gemma2:9b

# Same effect
FLUID_NONINTERACTIVE=1 fluid forge data-model from-intent intent.yaml --output out.fluid.yaml --llm-provider ollama --llm-model gemma2:9b
```

`--quiet` does the same. Each variable counts only when its value is exactly `1`. The warnings are not printed, but the `capability_warnings_count=...` log line still is, so a CI run whose stdout another tool consumes keeps the signal.

## Model coverage matrix

The catalog is built in `fluid_build.copilot.agents.capability_catalog` from two sources: a hand-curated family overlay, which the tables below list, and entries derived from the CLI's model catalog (`llm_models.json`) for model ids the overlay does not prefix. Resolution is by **longest-prefix match** within a provider, overlay first: `claude-3-5-sonnet-20241022` resolves to the `claude-3-5-sonnet` row, and `claude-haiku-4-5-20251001` to `claude-haiku-4-5`.

### Anthropic

| Prefix | tool_use | structured_output | streaming | prompt_caching | extended_thinking | Notes |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `claude-opus-4-7` | yes | yes | yes | yes | yes | Temperature is deprecated; providers drop it automatically |
| `claude-sonnet-4-7` | yes | yes | yes | yes | yes | |
| `claude-sonnet-4-6` | yes | yes | yes | yes |  | |
| `claude-sonnet-4-5` | yes | yes | yes | yes |  | |
| `claude-haiku-4-5` | yes | yes | yes | yes |  | |
| `claude-3-5-sonnet` | yes | yes | yes | yes |  | |
| `claude-3-5-haiku` | yes | yes | yes | yes |  | |
| `claude-3-opus` | yes | yes | yes | yes |  | |
| `claude-3` (catch-all) | yes | yes | yes |  |  | |

### OpenAI

| Prefix | tool_use | structured_output | streaming | extended_thinking | Notes |
|---|:-:|:-:|:-:|:-:|---|
| `o1` | no | yes | no | yes | o1 reasoning models do not support tool use or streaming. Multi-turn tool loops will degrade to single-shot prompts. |
| `o3` | yes | yes | yes | yes | |
| `o4` | yes | yes | yes | yes | |
| `gpt-4.1` | yes | yes | yes |  | |
| `gpt-4.1-mini` | yes | yes | yes |  | |
| `gpt-4.1-nano` | yes | yes | yes |  | |
| `gpt-4o` | yes | yes | yes |  | |
| `gpt-4-turbo` | yes | yes | yes |  | |
| `gpt-4` (pre-4o) | yes | no | yes |  | Lacks strict JSON-Schema response format. Schema validation may fail on edge cases. |
| `gpt-3.5` | yes | no | yes |  | Should not be used for stage agent runs — the staged outputs require strict schema enforcement. |

### Google Gemini

| Prefix | tool_use | structured_output | streaming | Notes |
|---|:-:|:-:|:-:|---|
| `gemini-2.5` | yes | yes | yes | |
| `gemini-2.0` | yes | yes | yes | |
| `gemini-1.5` | yes | yes | yes | `responseSchema` budget is small; very large schemas may still fail |

### Ollama

Ollama is a runtime, not a model — capabilities depend on the model loaded. The catalog covers what the project's default `llm_models.json` exposes plus the most common community models.

| Prefix | tool_use | structured_output | streaming | Notes |
|---|:-:|:-:|:-:|---|
| `llama3.2` | yes | no | yes | |
| `llama3.1` | yes | no | yes | Tool-use accuracy on Ollama-served llama3.1 is lower than on hosted models. Expect more tool-call validation errors. |
| `qwen3-coder` | yes | no | yes | Tuned for code generation; tool-use latency is higher than llama3.x but accuracy on structured args is better |
| `qwen3` | yes | no | yes | |
| `qwen` (catch-all) | yes | no | yes | |
| `gemma4` | yes | no | yes | The project's default Ollama model. Acceptable for the staged pipeline; multi-turn agent loop may need more iterations to converge |
| `gemma3` | yes | no | yes | |
| `gemma2` | no | no | yes | gemma2 does not support tool calling. Use gemma3+ if you need the multi-turn agent loop on Ollama. |
| `gemma` (1.x) | no | no | yes | Original Gemma (1.x) does not support tool calling. Use gemma3+ for the agent loop. |
| `mistral` | yes | no | yes | |
| `mixtral` | yes | no | yes | |
| `deepseek` | yes | no | yes | |
| `phi` | no | no | yes | Phi-family models are too small for reliable tool calling. Use them for completion-style prompts only. |

::: tip Context windows
The offline fallback table `fluid_build.copilot.agents.token_budget.DEFAULT_CONTEXT_WINDOWS` covers Ollama-served models only: `llama3.1`, `llama3.2`, `llama3.3`, `qwen3`, `gemma4`, `gemma3` and `deepseek-r1` at 128K, `qwen3-coder` at 256K, `mistral` and `mixtral` at 32,768, and 32,000 for anything else. For cloud models the window comes from LiteLLM's model catalog. Override it per session with `capability_matrix["context_window"]` if you configured a custom context window on your local server.
:::

## Adding a model to the catalog

A model id that the model catalog (`fluid_build/cli/llm_models.json`) lists gets a derived entry automatically. For a family the project does not know yet, add an overlay entry. Entries are small dataclass instances:

```python
# fluid_build/copilot/agents/capability_catalog.py — append to _FAMILY_OVERLAY
ProviderCapabilities(
    provider="ollama",
    model_prefix="my-fancy-model",
    tool_use=True,
    structured_output=False,
    streaming=True,
    notes=("Operational caveat goes here.",),
),
```

And add the context window to `DEFAULT_CONTEXT_WINDOWS` in `fluid_build/copilot/agents/token_budget.py`:

```python
"my-fancy-model": 128_000,
```

Pin the new entry with a test in `tests/copilot/test_capability_catalog.py` and `tests/copilot/test_token_budget.py`.

## See also

- [LLM Providers → Run-start capability warnings](llm-providers.md#run-start-capability-warnings) — where this fits in the provider config flow
- [Forge Agent Errors](typed-errors.md): when a degraded run fails, the error is one of these
- [Agentic primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-pre-flight-compaction) — how the token-budget catalog (paired with this one) prevents context-overflow failures
