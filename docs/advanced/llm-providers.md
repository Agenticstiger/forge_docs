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
| Anthropic | `claude-sonnet-4-6` | Tool-forced structured output and provider-native prompt caching |
| OpenAI | `gpt-4.1` | Strict JSON Schema output where available; seed support |
| Gemini | `gemini-2.5-pro` | Uses Gemini response schema where suitable and validator repair when needed |
| Ollama | `FLUID_OLLAMA_MODEL` such as `gemma4:latest` | Local-only; JSON mode is model-gated |
| Azure OpenAI | `FLUID_AZURE_DEPLOYMENT` | OpenAI-compatible wire shape with deployment names |

## Tiered mode

`--tiered` chooses different models within the same provider, never across providers. A typical layout is:

| Tier | Role |
| --- | --- |
| deep | hardest reasoning and planning |
| balanced | main model-building execution |
| fast | routing, clarification, and light evaluation |

If a provider has no distinct tier models configured, the CLI collapses tiered mode to a single-model run and emits a one-line warning. Ollama commonly runs this way unless the local model catalog is configured with separate fast, balanced, and deep models.

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

Use `fluid ai setup` for interactive setup and key storage. Provider and model choices are saved in `~/.fluid/ai_config.json`; API keys go to the OS keyring by default. Plaintext API-key persistence requires explicit opt-in with `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1`.
