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

A run that names no provider and cannot ask a question picks one itself; see [When nothing is configured](#when-nothing-is-configured). *(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))*

## Supported providers

The `openai`, `anthropic`, `gemini` and `ollama` providers run through LiteLLM and need `pip install 'data-product-forge[litellm]'` (alias `[ai]`). *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* `mcp-sampling` works only inside `fluid mcp serve`, which needs `[mcp]`. The four local agent CLIs need neither extra; only Claude Code needs no setup of its own, since the others reuse their own CLI login or key.

| Provider | `--llm-provider` | Default model | Notes |
| --- | --- | --- | --- |
| Anthropic | `anthropic` (alias `claude`) | `claude-sonnet-4-6` | Tool-forced structured output and provider-native prompt caching. Streamed runs report token usage in cost summaries. |
| OpenAI | `openai` | `gpt-4.1-mini` | Strict JSON Schema output where available. Tiered runs use `gpt-4.1` for deep logical modeling. Set `FLUID_OPENAI_STRICT_SCHEMA=1` to harden the response-format schema for `gpt-4o`, `gpt-4.1` and o-series models that reject permissive nested objects. |
| Gemini | `gemini` | `gemini-2.5-pro` | Uses Gemini response schema where suitable and validator repair when needed. |
| Ollama | `ollama` | `gemma4:latest` | Calls go to the [Ollama endpoint](#the-ollama-endpoint). JSON mode is model-gated. The capability and token-budget catalogs cover `gemma` 1 to 4, `qwen3-coder`, `qwen3`, `qwen2.5`, `llama3.1`, `llama3.2`, `llama3.3`, `mistral`, `mixtral`, `deepseek` and `phi`. See [Capability Warnings](capability-warnings.md) for tool-use accuracy notes per family. |
| MCP sampling | `mcp-sampling` | none | No key of its own. When forge runs inside an MCP client, the model request goes back through the connection and the client's own LLM answers it. |
| Local agent CLIs | `claude-code`, `codex`, `cursor`, `kiro` | the agent's own | Forge shells out to a coding-agent CLI you already have installed. Claude Code uses your subscription login; the others reuse `CODEX_API_KEY`, `CURSOR_API_KEY` and `KIRO_API_KEY`. Forge runs `claude -p` apart from your own Claude Code setup; see [Claude Code](#claude-code). |

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

## Which provider a run uses

*(since 0.29.0, [forge-cli #854](https://github.com/Agenticstiger/forge-cli/pull/854))*

Forge takes the provider from the first of these that answers. [`fluid doctor`](../cli/doctor.md) walks the same ladder, so its Provider row names what a run uses. It reads only the environment, not a run's flags, so it picks an agent at rung 5 only without a terminal.

1. A provider you name: `--llm-provider`, `FLUID_LLM_PROVIDER` or `FLUID_FORGE_AGENT`.
2. The key variable of exactly one provider: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` or `GOOGLE_API_KEY`, or `OLLAMA_HOST`.
3. The provider `fluid ai setup` saved, with its model and its Ollama host.
4. The key of exactly one provider in the OS keyring.
5. A running Ollama, then, in a run without a terminal or with `--non-interactive` that configures nothing, the first coding-agent CLI on `PATH`; see [When nothing is configured](#when-nothing-is-configured).

A run without a terminal uses the saved choice too. Through 0.28.0, `fluid forge` with `--non-interactive` and `fluid forge data-model` skipped it. The interactive setup of `fluid forge` and `fluid init` read it, and so did `fluid doctor` and `fluid ai test`.

The saved choice fills in only what the run leaves out, and only for the saved provider:

- A named provider takes nothing from it. Without `--llm-model`, a named provider gets its catalog model.
- A saved coding agent, or `mcp-sampling`, is passed over when the run states an endpoint or a model (`--llm-endpoint`, `--llm-model` and their routing twins, or `FLUID_LLM_ENDPOINT`, `FLUID_LLM_MODEL` and theirs) or runs the agent loop. The ladder then goes on to rung 4.
- `claude` in the saved file means `anthropic`, and `claude_code` means `claude-code`.
- The saved Ollama host applies when `OLLAMA_HOST` is not set. A saved `endpoint` field is not applied.

`fluid mission run` always runs the agent loop, so it never picks a coding agent; see [`fluid mission`](../cli/mission.md).

### Which key a provider gets

*(since 0.29.0, [forge-cli #853](https://github.com/Agenticstiger/forge-cli/pull/853))*

`FLUID_LLM_API_KEY` does not say which vendor it is for, so forge sends it only to a provider named with `--llm-provider`, `FLUID_LLM_PROVIDER` or `FLUID_FORGE_AGENT`. There it wins over the provider's own key variable. A named Ollama gets it too, for ollama.com or a proxy that takes a token.

A provider forge picks itself never gets `FLUID_LLM_API_KEY`: rungs 2 to 5 above, and the provider that interactive setup finds in `fluid forge` and `fluid init`. It gets its own key variable, then its keyring key, and forge warns:

```text
FLUID_LLM_API_KEY is set but not used: it goes only to a provider named with --llm-provider or FLUID_LLM_PROVIDER, and forge picked ollama itself. Pass --llm-provider ollama to use the key with it.
```

`fluid ai test` sends the key only to the provider its `--provider` names, and `fluid doctor` counts it only when `FLUID_LLM_PROVIDER` or `FLUID_FORGE_AGENT` names the provider. Through 0.28.0 forge sent the key to whatever provider it used, so an OpenAI key could reach another vendor, such as the provider of the one key in the OS keyring.

## When nothing is configured

*(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))*

A run that cannot ask a question picks an LLM itself when nothing names one. That is a run whose stdin is not a terminal, or one with `--non-interactive`, which `fluid forge --agent` sets when it runs AI mode. Forge uses the first of these it finds:

1. A local Ollama answering on `http://localhost:11434`, so local data stays on the machine.
2. The first coding-agent CLI on `PATH`, in this order: `claude` (`claude-code`), `codex`, `cursor-agent` (`cursor`) and `kiro-cli` (`kiro`).

When it picks an agent, forge logs a warning that names it:

```text
No LLM provider is configured; using claude-code, the first coding agent found on PATH. Override with --llm-provider.
```

*(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* With neither, the run stops with `copilot_no_llm_provider` and says why; see [No LLM provider is selected](./production-troubleshooting.md#no-llm-provider-is-selected). Through 0.28.0 it fell back to `gemini`, which needs a Gemini key and the `litellm` extra, whenever no Ollama was running, even with a signed-in Claude Code on `PATH`.

Any of these configures an LLM, and then no agent is picked:

- `--llm-provider`, `FLUID_LLM_PROVIDER` or `FLUID_FORGE_AGENT`. The provider they name is used.
- `--llm-endpoint`, `--llm-model`, `--llm-routing-endpoint` or `--llm-routing-model`.
- `FLUID_LLM_API_KEY`, `FLUID_LLM_ENDPOINT`, `FLUID_LLM_MODEL`, `FLUID_LLM_ROUTING_ENDPOINT`, `FLUID_LLM_ROUTING_MODEL` or `OLLAMA_HOST`.
- A provider key: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY` or `GITHUB_API_KEY`.
- An OpenAI, Anthropic or Gemini key in the OS keyring.
- A provider saved with `fluid ai setup`. *(since 0.29.0, [forge-cli #854](https://github.com/Agenticstiger/forge-cli/pull/854))* Runs use it as rung 3 of [Which provider a run uses](#which-provider-a-run-uses), except a saved coding agent that the run passes over there. Through 0.28.0 a run with `--non-interactive` did not use it.
- The agent loop: `--agent-loop`, or `FLUID_COPILOT_AGENT_LOOP` set to `1`, `true`, `yes` or `on`. The loop needs tool use, which these agents do not offer.

*(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* Only some of these select a provider: the rungs of [Which provider a run uses](#which-provider-a-run-uses). The others, `GITHUB_API_KEY` among them, only stop forge from picking an agent: an Ollama that answers at `OLLAMA_HOST` or `localhost:11434` is still used. When nothing selects a provider and no Ollama answers, forge stops with `copilot_no_llm_provider`. So pass `--llm-provider` together with `--llm-endpoint`, `--llm-model` or `FLUID_LLM_API_KEY`.

The pick works on the base install, because the agent CLIs need no `litellm` extra. A running local Ollama still comes first there, so that run asks for the extra instead of sending the prompt to an agent.

An interactive run does not pick an agent: `fluid forge` in a terminal offers Claude Code in its inline setup instead. With nothing configured, [`fluid doctor`](../cli/doctor.md) run without a terminal reports the provider this pick chooses. When the pick finds nothing, its Provider row says `Not selected`. *(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))* `fluid doctor --verbose` then shows, in its Message row, the reason forge would stop with.

## Claude Code

*(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))*

`--llm-provider claude-code` runs `claude -p` on your machine. Forge keeps each call apart from your own Claude Code setup, as Anthropic's [Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) does:

| Flag or variable | Effect |
| --- | --- |
| `--system-prompt` | Forge's prompt replaces Claude Code's own system prompt. |
| `--tools ""` | No built-in tools. |
| `--strict-mcp-config` | No MCP servers. Forge passes no `--mcp-config`. |
| `--setting-sources=` | None of your user, project or local settings: no hooks, plugins or `CLAUDE.md`. |
| `--no-session-persistence` | The call is not saved as a session. |
| `CLAUDECODE` | Removed from the environment `claude` starts in. Claude Code sets it in the shells it starts. |

Forge passes each flag only when the installed `claude --help` lists it, so an older Claude Code still runs. Without `--system-prompt`, forge appends its prompt with `--append-system-prompt`, as it did through 0.28.0. The [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference) describes each flag.

### Signing in

A subscription login (run `claude` once and sign in) and an `ANTHROPIC_API_KEY` in the environment work as before. Authentication kept in your own Claude Code settings does not reach forge's calls: an `apiKeyHelper`, or `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` and their variables in the `env` block of `settings.json`. Export those variables in the shell that runs forge, or set `ANTHROPIC_API_KEY`. Claude Code's [authentication](https://code.claude.com/docs/en/authentication) page lists the variables each method needs.

### When the call fails

`claude -p` reports a failure as a JSON result with `is_error: true` on stdout, and leaves stderr empty. Forge reads that result. A login problem reads:

```text
claude-code is installed but not authenticated.
```

The hint under it says ``Run `claude` once and sign in (subscription), or set ANTHROPIC_API_KEY.`` Any other failure shows Claude Code's own message. A result with `is_error: true` fails the call even when `claude` exits `0`. Through 0.28.0 forge read only stderr, and showed `claude-code exited with code 1:` with no reason.

## The Ollama endpoint

*(since 0.29.0, [forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850))*

Forge's Ollama calls go to the first of these that is set:

1. `--llm-endpoint`, or `FLUID_LLM_ENDPOINT`.
2. `OLLAMA_HOST`.
3. `http://localhost:11434`, litellm's default.

Forge reads `OLLAMA_HOST` the way Ollama's own Python client does ([`_parse_host`](https://github.com/ollama/ollama-python/blob/35d9667e84ebbd9d792826868d050027f75c1cc1/ollama/_client.py)), so a value Ollama accepts works here too:

| `OLLAMA_HOST` | Calls go to |
| --- | --- |
| `gpu-box` | `http://gpu-box:11434` |
| `gpu-box:8080` | `http://gpu-box:8080` |
| `:8080` | `http://127.0.0.1:8080` |
| `http://gpu-box` | `http://gpu-box:80` |
| `https://gpu-box` | `https://gpu-box:443` |
| `https://gpu-box/ollama` | `https://gpu-box:443/ollama` |

The host can be another machine. A stated endpoint is used for the routing model's calls too, unless `--llm-routing-endpoint` or `FLUID_LLM_ROUTING_ENDPOINT` names another. A project's `.env` cannot set `OLLAMA_HOST`; see [Project dotenv trust](./project-dotenv-trust.md).

Through 0.28.0 these calls went to a `litellm://ollama/<model>` label unless an endpoint was stated, so they never reached the daemon.

### One address for every Ollama read

*(since 0.29.0, [forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852))*

Every Ollama read takes any host, as Ollama's own client does:

- With no `--llm-model`, forge asks the daemon the call goes to, and uses its largest model, else `gemma4:latest`.
- The model check that `--require-llm`, `--tiered` and `FLUID_LLM_MODEL_PREFLIGHT` turn on asks that daemon too. The model check of `fluid ai test` asks its `--endpoint`, else `OLLAMA_HOST`, else `localhost:11434`.
- Each `--tiered` stage calls a stated endpoint, as the routing model does.
- The probe that finds a running Ollama, and `fluid ai setup`, read `OLLAMA_HOST`, else `localhost:11434`. A stated endpoint does not reach them.

Forge reads `--llm-endpoint` and `FLUID_LLM_ENDPOINT` the same way as `OLLAMA_HOST`: `--llm-endpoint gpu-box` means `http://gpu-box:11434`, and the scheme may be in upper or lower case. `fluid ai test --endpoint` takes only an absolute `http` or `https` URL. A stated endpoint does not choose Ollama, so pass `--llm-provider ollama` with it. `OLLAMA_HOST` on its own does choose it.

An address may carry `user:password@`, for an Ollama behind a proxy that asks for basic auth, and forge sends it as basic auth, to the call and to the model lookups. `fluid ai test --endpoint` refuses one. `fluid doctor` and `fluid ai setup` show it as `***:***@`. `fluid ai setup` saves the address to `~/.fluid/ai_config.json` without it, as it does for API keys, unless `FLUID_ALLOW_PLAINTEXT_AI_SECRETS` is set, and logs a warning to keep the credentials in the environment. An `OLLAMA_HOST` in the environment wins over the saved address, so keep them there.

Through 0.28.0, forge's default-model pick, the probe and `fluid ai setup` looked only at `localhost`, and ignored a non-local `OLLAMA_HOST` with the warning `OLLAMA_HOST points to a non-localhost address (...), ignoring.` The model checks read `OLLAMA_HOST`, never a stated endpoint.

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
| `OLLAMA_HOST` | Ollama's address; see [The Ollama endpoint](#the-ollama-endpoint) |

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
