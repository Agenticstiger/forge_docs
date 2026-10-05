# LLM Providers

Forge data-model runs use one active LLM provider per run. The provider is selected from the CLI flag, environment, or saved AI config:

```bash
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider gemini
```

```bash
FLUID_LLM_PROVIDER=ollama \
FLUID_LLM_MODEL=gemma4:latest \
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
```

## Supported providers

| Provider | `--llm-provider` | Default model | Notes |
| --- | --- | --- | --- |
| Anthropic | `anthropic` (alias `claude`) | `claude-sonnet-4-6` | Tool-forced structured output and provider-native prompt caching. Streamed runs report token usage in cost summaries. |
| OpenAI | `openai` | `gpt-4.1-mini` | Strict JSON Schema output where available. Tiered runs use `gpt-4.1` for deep logical modeling. Set `FLUID_OPENAI_STRICT_SCHEMA=1` to harden the response-format schema for `gpt-4o`, `gpt-4.1` and o-series models that reject permissive nested objects. |
| Gemini | `gemini` | `gemini-2.5-pro` | Uses Gemini response schema where suitable and validator repair when needed. |
| Ollama | `ollama` | `gemma4:latest` | Local-only; JSON mode is model-gated. The capability and token-budget catalogs cover `gemma` 1 to 4, `qwen3-coder`, `qwen3`, `qwen2.5`, `llama3.1`, `llama3.2`, `llama3.3`, `mistral`, `mixtral`, `deepseek` and `phi`. See [Capability Warnings](capability-warnings.md) for tool-use accuracy notes per family. |
| MCP sampling | `mcp-sampling` | none | No key of its own. When forge runs inside an MCP client, the model request goes back through the connection and the client's own LLM answers it. |
| Local agent CLIs | `claude-code`, `codex`, `cursor`, `kiro` | the agent's own | Forge shells out to a coding-agent CLI you already have installed. Claude Code uses your subscription login; the others reuse `CODEX_API_KEY`, `CURSOR_API_KEY` and `KIRO_API_KEY`. |

Those are the values `fluid forge --llm-provider` and `fluid forge data-model ... --llm-provider` accept. Other names LiteLLM understands, such as `bedrock`, `vertex` and `azure`, are rejected by the argument parser as of 0.18.1:

```text
fluid forge: error: argument --llm-provider: invalid choice: 'bedrock' (choose from 'openai', 'anthropic', 'claude', 'gemini', 'ollama', 'mcp-sampling', 'claude-code', 'codex', 'cursor', 'kiro')
```

Two flags apply only to some providers. `--forge-agent-mode envelope|agentic` chooses how a local agent CLI (`claude-code`, `codex`, `cursor`, `kiro`) hands the contract back: as JSON on stdout, or by writing `contract.fluid.yaml` into the workspace. `--llm-routing-model` and `--llm-routing-endpoint` name a cheaper model for interview clarification and self-evaluation. Their reference is [AI config](../cli/forge.md#ai-config) on the `fluid forge` page; setup, status and tests are under [`fluid ai`](../cli/ai.md).

Inspect the active catalog with:

```bash
fluid ai models          # a table of each provider's primary, routing and tier models
fluid ai models --json   # the same plan as JSON, one object per provider
```

`fluid ai models` prints one plan per provider and cannot be narrowed to one. As of 0.18.1 its `--provider` flag does not work: `fluid ai models --provider gemini` exits 2 with `Unknown provider 'gemini' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake`, because the CLI checks the value against the infrastructure providers. Filter the JSON instead, for example with `jq .gemini`. `fluid ai test` and `fluid ai setup` take `--provider` and are not affected.

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

`--deterministic` turns the staged cache and tiering off and records the run as deterministic in its audit metadata. The LiteLLM request uses a temperature of `0.0` unless the configuration sets another value. The CLI does not set a seed, so wording can still vary between runs of the same prompt.

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

### Agent-loop tuning

| Env var | Purpose |
| --- | --- |
| `FLUID_AGENT_COMPACT_AFTER` | Iteration count after which the multi-turn agent loop compacts older tool results to stay under the model's context window. Default `6`. Set to a higher number for long-context Anthropic / Gemini runs; lower for tight-context Ollama models. |
| `FLUID_COMPACTION_STRATEGY` | `truncate` (default — char/token-aware truncation), `summarize` (LLM-backed; calls your provider's fast tier once per compaction trigger), or `hybrid` (truncate first, then summarize the rest if still over budget). See [Agentic primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-pre-flight-compaction). |
| `FLUID_TOKEN_COUNTER` | Internal — selects the token-counting backend. Default is the pure-Python char-based heuristic; the CLI does not require an external tokenizer. |
| `FLUID_OPENAI_STRICT_SCHEMA` | `1` to enable the recursive strict-schema walker for OpenAI's `response_format = json_schema` mode. Closes the "Invalid schema for response_format 'ForgeContract'" 400 some `gpt-4o`/`gpt-4.1`/o-series deployments return when nested objects are free-form. Free-form fields are rewritten to JSON-encoded strings under strict mode. |
| `FLUID_QUIET` / `FLUID_NONINTERACTIVE` | `1` to silence capability-degradation warnings. The warnings are still recorded to telemetry. |

Use `fluid ai setup` for interactive setup and key storage. Provider and model choices are saved in `~/.fluid/ai_config.json`; API keys go to the OS keyring by default. Plaintext API-key persistence requires explicit opt-in with `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1`.

## Run-start capability warnings

`fluid forge data-model` checks the (provider, model) pair against the capability catalog before the run, only when you pass `--llm-provider`, `--llm-model` or `--llm-endpoint`. The check uses the `staged_pipeline` profile, and a pair that lacks structured output, or is not in the catalog, prints a warning and the run continues with degraded behaviour. See [Capability Warnings](capability-warnings.md) for the matrix and the exact output.

## Operator-facing errors

When a provider call fails, the CLI raises a typed exception that distinguishes rate limits, context-overflow, auth failures, transient server errors, and schema-validation failures so retries honor `Retry-After` and the agent loop can route corrective feedback to the LLM. See [Typed Errors](typed-errors.md) for the full reference.

For complete command journeys, see [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md).
