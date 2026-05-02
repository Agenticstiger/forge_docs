# LLM Providers

Forge data-model runs use one active LLM provider per run. The provider is selected from the CLI flag, environment, or saved AI config:

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider gemini
```

```bash
FLUID_LLM_PROVIDER=ollama \
FLUID_OLLAMA_MODEL=gemma4:latest \
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
```

## Supported providers

| Provider | Default / common model | Notes |
| --- | --- | --- |
| Anthropic | `claude-sonnet-4-6` | Tool-forced structured output and provider-native prompt caching. Streamed runs report accurate token usage in cost summaries (was previously "missing usage" on every streamed call). |
| OpenAI | `gpt-4.1-mini` | Strict JSON Schema output where available; seed support. Tiered runs use `gpt-4.1` for deep logical modeling. Set `FLUID_OPENAI_STRICT_SCHEMA=1` to harden the response-format schema for `gpt-4o`/`gpt-4.1`/o-series models that reject permissive nested objects. |
| Gemini | `gemini-2.5-pro` | Uses Gemini response schema where suitable and validator repair when needed |
| Ollama | `FLUID_OLLAMA_MODEL` such as `gemma4:latest` | Local-only; JSON mode is model-gated. Capability + token-budget catalogs cover `gemma` 1–4, `qwen3-coder`, `qwen3`, `qwen2.5`, `llama3.1`/`3.2`/`3.3`, `mistral`, `mixtral`, `deepseek`, `phi`. See [Capability Warnings](capability-warnings.md) for tool-use accuracy notes per family. |
| Azure OpenAI | `FLUID_AZURE_DEPLOYMENT` | OpenAI-compatible wire shape with deployment names |

Inspect the active catalog with:

```bash
fluid ai models
fluid ai models --provider gemini --json
```

## Tiered mode

`--tiered` chooses different models within the same provider, never across providers. A typical layout is:

| Tier | Role |
| --- | --- |
| deep | hardest reasoning and planning |
| balanced | main model-building execution |
| fast | routing, clarification, and light evaluation |

If a provider has no distinct tier models configured, the CLI collapses tiered mode to a single-model run and emits a one-line warning. Ollama commonly runs this way unless the local model catalog is configured with separate fast, balanced, and deep models.

The deterministic stages stay deterministic even in tiered mode:

| Stage | Model use |
| --- | --- |
| Interview | Fast routing model |
| Logical modeler | Deep model |
| Contract forge | No model, deterministic |
| Transformation | No model, deterministic from `.model.json` |
| Validator | No model, deterministic |
| Self-evaluation | Fast routing model |

## Strict provider testing

For normal user experience, forge can fall back to deterministic heuristics if an LLM call fails. For provider certification and E2E testing, use:

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider anthropic \
  --require-llm
```

`--require-llm` fails loudly if the provider cannot run. This prevents a green-looking smoke test that actually used heuristics.

## Deterministic runs

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --deterministic
```

`--deterministic` disables cache and tiering for replayable output. Providers pin `temperature=0`; OpenAI, Ollama, and Azure OpenAI also pin seed where supported.

## Environment variables

### Provider + credentials

| Env var | Purpose |
| --- | --- |
| `FLUID_LLM_PROVIDER` | Active provider for the run |
| `FLUID_LLM_MODEL` | Specific model override |
| `FLUID_LLM_TIMEOUT_SECONDS` | Provider HTTP timeout |
| `OPENAI_API_KEY` | OpenAI key |
| `ANTHROPIC_API_KEY` | Anthropic key |
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Gemini key |
| `OLLAMA_HOST` | Ollama endpoint; local addresses only |
| `FLUID_OLLAMA_MODEL` | Ollama model name |

### Agent-loop tuning

| Env var | Purpose |
| --- | --- |
| `FLUID_AGENT_COMPACT_AFTER` | Iteration count after which the multi-turn agent loop compacts older tool results to stay under the model's context window. Default `6`. Set to a higher number for long-context Anthropic / Gemini runs; lower for tight-context Ollama models. |
| `FLUID_COMPACTION_STRATEGY` | `truncate` (default — char/token-aware truncation), `summarize` (LLM-backed; calls your provider's fast tier once per compaction trigger), or `hybrid` (truncate first, then summarize the rest if still over budget). See [Agentic primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-preflight-and-compaction). |
| `FLUID_TOKEN_COUNTER` | Internal — selects the token-counting backend. Default is the pure-Python char-based heuristic; the CLI does not require an external tokenizer. |
| `FLUID_OPENAI_STRICT_SCHEMA` | `1` to enable the recursive strict-schema walker for OpenAI's `response_format = json_schema` mode. Closes the "Invalid schema for response_format 'ForgeContract'" 400 some `gpt-4o`/`gpt-4.1`/o-series deployments return when nested objects are free-form. Free-form fields are rewritten to JSON-encoded strings under strict mode. |
| `FLUID_QUIET` / `FLUID_NONINTERACTIVE` | `1` to silence the v2-preview banner and capability-degradation warnings. The warnings are still recorded to telemetry. |

Use `fluid ai setup` for interactive setup and key storage. Provider and model choices are saved in `~/.fluid/ai_config.json`; API keys go to the OS keyring by default. Plaintext API-key persistence requires explicit opt-in with `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1`.

## Run-start capability warnings

When you pick a provider/model whose declared capabilities don't satisfy what the run needs (e.g. `gpt-3.5` in agent-loop mode, an Ollama model with no tool-use support, or a model not yet in the capability catalog), the CLI prints a one-paragraph warning at the start of `fluid forge data-model from-intent` and continues with degraded behaviour. See [Capability Warnings](capability-warnings.md) for the full matrix and the exact banner shape.

## Operator-facing errors

When a provider call fails, the CLI raises a typed exception that distinguishes rate limits, context-overflow, auth failures, transient server errors, and schema-validation failures so retries honor `Retry-After` and the agent loop can route corrective feedback to the LLM. See [Typed Errors](typed-errors.md) for the full reference.

For complete command journeys, see [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md).
