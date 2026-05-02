# Capability Warnings

When you start a `fluid forge data-model from-intent` run, the CLI checks the (provider, model) combo you picked against a capability catalog. If the combo is missing something the run needs (tool use, structured-output enforcement, prompt caching, extended thinking), or the combo isn't catalogued at all, you see a one-paragraph warning at the top of stdout and the run continues with degraded behaviour.

This page tells you what those warnings mean, what to do about them, and which (provider, model) combos are catalogued.

## What the banner looks like

A typical run on a degraded combo prints something like this just after the v2-preview banner:

```
⚠ openai/o1-mini does not reliably support tool use — agent runs may produce degraded output.
⚠ Note for openai/o1-mini: o1 reasoning models do not support tool use or streaming.
  Multi-turn tool loops will degrade to single-shot prompts.
capability_warnings_count=2 provider=openai model=o1-mini
```

The first lines are user-facing warnings (printed via the standard CLI console — also fed through the secret-redaction filter so they're safe to share in bug reports). The trailing `capability_warnings_count=…` is a structured log line for telemetry.

## When the banner fires

### Missing required capability

The "what's required" set depends on the **usage profile** of the run:

- **`agent_loop`** — the multi-turn tool-driven loop (`fluid forge --agent-loop`) requires both `tool_use` AND `structured_output`. If either is missing, you'll get a warning per gap.
- **`staged_pipeline`** — the default `fluid forge data-model from-intent` pipeline requires `structured_output` only (each stage is one LLM call; no tools). Tool-use gaps don't warn here.

Concretely:
- `gpt-3.5` on the staged pipeline → warns (no strict structured output).
- `o1-mini` on the agent loop → warns twice (no tool use, no streaming).
- `gemma2:9b` on the agent loop → warns (predates Ollama's tool-calling support).
- `claude-sonnet-4-6` on either → silent (full support).

### Unknown (provider, model)

If your model isn't in the catalog, you always get an "is not in the capability catalog" warning. The run still proceeds with the conservative `_FALLBACK_CAPABILITIES` (streaming on, tool_use off, structured_output off) so you get something — but if your model actually supports more than that, see [Adding a model to the catalog](#adding-a-model-to-the-catalog).

### Operational notes

Even when a combo *passes* the requirements check, the catalog may still surface a `note` field as a warning. Examples:

- `claude-opus-4-7` — "Temperature is deprecated on Opus 4.7 — providers drop it automatically."
- `gemma4` — "gemma4 is the project's default Ollama model. Tool-use accuracy is acceptable for the staged pipeline; the multi-turn agent loop may need more iterations to converge than on hosted providers."
- Any Ollama llama3.1 — "Tool-use accuracy on Ollama-served llama3.1 is lower than on hosted Anthropic / OpenAI / Gemini models. Expect more tool-call validation errors."

Notes are informational — they don't block the run.

## Silencing the banner

The warnings are useful by default, but two opt-outs exist:

```bash
# Per-run silence
FLUID_QUIET=1 fluid forge data-model from-intent intent.yaml ...

# Same effect — alternative env var name some CI systems prefer
FLUID_NONINTERACTIVE=1 fluid forge data-model from-intent intent.yaml ...
```

The warnings are still recorded to telemetry (`capability_warnings_count=…` log line) so silencing the print doesn't lose the signal — useful for CI runs where stdout is consumed by another tool.

## Model coverage matrix

The catalog lives at `fluid_build.copilot.agents.capability_catalog.CAPABILITY_CATALOG`. Resolution is by **longest-prefix match** within a provider — `claude-3-5-sonnet-20241022` resolves to the `claude-3-5-sonnet` row, etc.

### Anthropic

| Prefix | tool_use | structured_output | streaming | prompt_caching | extended_thinking | Notes |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `claude-opus-4-7` | ✅ | ✅ | ✅ | ✅ | ✅ | Temperature is deprecated; providers drop it automatically |
| `claude-sonnet-4-7` | ✅ | ✅ | ✅ | ✅ | ✅ | |
| `claude-sonnet-4-6` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-sonnet-4-5` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-haiku-4-5` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-3-5-sonnet` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-3-5-haiku` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-3-opus` | ✅ | ✅ | ✅ | ✅ |  | |
| `claude-3` (catch-all) | ✅ | ✅ | ✅ |  |  | |

### OpenAI

| Prefix | tool_use | structured_output | streaming | extended_thinking | Notes |
|---|:-:|:-:|:-:|:-:|---|
| `o1` | ❌ | ✅ | ❌ | ✅ | o1 reasoning models do not support tool use or streaming. Multi-turn tool loops will degrade to single-shot prompts. |
| `o3` | ✅ | ✅ | ✅ | ✅ | |
| `o4` | ✅ | ✅ | ✅ | ✅ | |
| `gpt-4.1` | ✅ | ✅ | ✅ |  | |
| `gpt-4.1-mini` | ✅ | ✅ | ✅ |  | |
| `gpt-4.1-nano` | ✅ | ✅ | ✅ |  | |
| `gpt-4o` | ✅ | ✅ | ✅ |  | |
| `gpt-4-turbo` | ✅ | ✅ | ✅ |  | |
| `gpt-4` (pre-4o) | ✅ | ❌ | ✅ |  | Lacks strict JSON-Schema response format. Schema validation may fail on edge cases. |
| `gpt-3.5` | ✅ | ❌ | ✅ |  | Should not be used for stage agent runs — the staged outputs require strict schema enforcement. |

### Google Gemini

| Prefix | tool_use | structured_output | streaming | Notes |
|---|:-:|:-:|:-:|---|
| `gemini-2.5` | ✅ | ✅ | ✅ | |
| `gemini-2.0` | ✅ | ✅ | ✅ | |
| `gemini-1.5` | ✅ | ✅ | ✅ | `responseSchema` budget is small; very large schemas may still fail |

### Ollama

Ollama is a runtime, not a model — capabilities depend on the model loaded. The catalog covers what the project's default `llm_models.json` exposes plus the most common community models.

| Prefix | tool_use | structured_output | streaming | Notes |
|---|:-:|:-:|:-:|---|
| `llama3.2` | ✅ | ❌ | ✅ | |
| `llama3.1` | ✅ | ❌ | ✅ | Tool-use accuracy on Ollama-served llama3.1 is lower than on hosted models. Expect more tool-call validation errors. |
| `qwen3-coder` | ✅ | ❌ | ✅ | Tuned for code generation; tool-use latency is higher than llama3.x but accuracy on structured args is better |
| `qwen3` | ✅ | ❌ | ✅ | |
| `qwen` (catch-all) | ✅ | ❌ | ✅ | |
| `gemma4` | ✅ | ❌ | ✅ | The project's default Ollama model. Acceptable for the staged pipeline; multi-turn agent loop may need more iterations to converge |
| `gemma3` | ✅ | ❌ | ✅ | |
| `gemma2` | ❌ | ❌ | ✅ | Predates Ollama's tool-calling support. Use `gemma3+` for the agent loop. |
| `gemma` (1.x) | ❌ | ❌ | ✅ | Predates tool calling |
| `mistral` | ✅ | ❌ | ✅ | |
| `mixtral` | ✅ | ❌ | ✅ | |
| `deepseek` | ✅ | ❌ | ✅ | |
| `phi` | ❌ | ❌ | ✅ | Phi-family models are too small for reliable tool calling. Use them for completion-style prompts only. |

::: tip Ollama context windows
The token-budget catalog at `fluid_build.copilot.agents.token_budget.DEFAULT_CONTEXT_WINDOWS` covers per-model windows: `llama3.1`/`3.2`/`3.3` 128K, `qwen3-coder` 256K, `qwen3`/`qwen2.5`/`gemma4`/`gemma3` 128K, `gemma2`/`gemma`/`llama3` 8K, `mistral`/`mixtral`/`deepseek` 32K, `phi-4` 16K, `phi-3` 4K, `phi` 2K. Override via `capability_matrix["context_window"]` if you've configured a custom context window on your local server.
:::

## Adding a model to the catalog

Catalog entries are tiny dataclass instances. To add a model the project doesn't yet know about:

```python
# fluid_build/copilot/agents/capability_catalog.py — append to CAPABILITY_CATALOG
ProviderCapabilities(
    provider="ollama",
    model_prefix="my-fancy-model",
    tool_use=True,
    structured_output=False,
    streaming=True,
    notes=("Operational caveat goes here.",),
),
```

And bump the context-window catalog at `fluid_build/copilot/agents/token_budget.py::DEFAULT_CONTEXT_WINDOWS`:

```python
"my-fancy-model": 128_000,
```

A test in `tests/copilot/test_capability_catalog.py` and `tests/copilot/test_token_budget.py` for the new entry pins the change against future regressions.

## See also

- [LLM Providers → Run-start capability warnings](llm-providers.md#run-start-capability-warnings) — where this fits in the provider config flow
- [Typed Errors](typed-errors.md) — when a degraded run fails, you'll see one of the seven typed errors
- [Agentic primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-preflight-and-compaction) — how the token-budget catalog (paired with this one) prevents context-overflow failures
