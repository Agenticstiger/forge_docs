# `fluid ai`

Configure the AI / LLM provider used by Forge Copilot, test that it works, and inspect the current AI configuration.

## Syntax

```bash
fluid ai setup [--provider NAME] [--clear] [--quiet]
fluid ai setup --source CATALOG --name NAME
fluid ai status [--quiet]
fluid ai test [--provider NAME] [--model ID] [--endpoint URL] [--timeout-seconds N] [--json]
fluid ai models [--json]
```

Running `fluid ai` with no subcommand falls through to `status`.

## Examples

```bash
# Save two providers, then pick one per forge run
fluid ai setup --provider openai
fluid ai setup --provider gemini
fluid forge --llm-provider gemini

# Check that the configured provider answers
fluid ai test
fluid ai test --provider ollama --timeout-seconds 5 --json

# Remove one provider, or everything
fluid ai setup --clear --provider openai
fluid ai setup --clear

# See what each provider's models are used for
fluid ai models
fluid ai models --json
```

## Key options

### `ai setup`

| Option | Description |
| --- | --- |
| `--provider {gemini,openai,anthropic,claude,ollama}` | Configure this one provider and skip the picker. It is saved and made the default **without erasing** the other saved providers, so run it once per provider. Select one at forge time with `fluid forge --llm-provider <name>`. |
| `--clear` | Clear saved AI config and any API keys stored in the system keychain. With `--provider`, remove only that provider and report which are still configured. |
| `--source CATALOG` | Configure a metadata-source catalog instead of an LLM provider (see below). |
| `--name NAME` | Saved name. For a source it defaults to `<source>-prod`; the saved name is the `--credential-id` for `fluid forge data-model from-source`. |
| `--quiet`, `-q` | Suppress the v2-preview banner. Also honours `FLUID_QUIET` and `FLUID_NONINTERACTIVE`. |

`fluid ai setup --source CATALOG --name NAME` configures source-catalog credentials for `fluid forge data-model from-source` and MCP `forge_from_source` calls. `--source` is the catalog type (`snowflake`, `unity`, `bigquery`, `dataplex`, `glue`, `datahub`, or `datamesh_manager`). It walks you through the auth method, saves the credential to the OS keyring and `~/.fluid/sources.yaml`, and tests the connection.

### `ai status`

Prints whether AI is configured and shows the active provider and model, plus any configured source catalogs. With nothing configured:

```text
╭───────────────────────────── AI Copilot Status ──────────────────────────────╮
│ No LLM provider configured. Run 'fluid ai setup' or set an API key env var.  │
...
i No metadata-source catalogs configured yet. Run: fluid ai setup --source 
<snowflake | unity | bigquery | dataplex | glue | datahub | datamesh_manager>
```

### `ai test`

Sends a small request to the configured provider and reports whether it answered. Use it before a long forge run, or in CI to check a key.

| Option | Description |
| --- | --- |
| `--provider {gemini,openai,anthropic,claude,ollama}` | Test this provider instead of the configured one. |
| `--model ID` | Override the model for this test. |
| `--endpoint URL` | Override the endpoint. A cloud endpoint must be HTTPS, so an API key is never sent in plaintext. |
| `--timeout-seconds N` | HTTP timeout for the request. |
| `--json` | Print a stable JSON report instead of the table. |

The report has these keys: `schema_version`, `timestamp`, `ok`, `exit_code`, `provider`, `model`, `endpoint`, `model_availability`, `live_call`, `usage`, `output_cap`, `latency_ms` and `error`. A failed run against an unreachable local Ollama:

```bash
fluid ai test --provider ollama --endpoint http://127.0.0.1:9 --timeout-seconds 3 --json
```

```json
{
  "schema_version": 1,
  "timestamp": "2026-10-05T00:16:21.208988Z",
  "ok": false,
  "exit_code": 5,
  "provider": "ollama",
  "model": "gemma4:latest",
  "endpoint": "http://127.0.0.1:9",
  "model_availability": null,
  "live_call": null,
  "usage": null,
  "output_cap": "8 tokens",
  "latency_ms": null,
  "error": {
    "code": "ai_test_network_error",
    "message": "AI test network error for ollama (ConnectError).",
    "suggestions": [
      "Check network connectivity",
      "For Ollama, start the local Ollama server"
    ]
  }
}
```

The process exit code equals `exit_code`:

| Code | Meaning |
| --- | --- |
| `0` | The provider answered. |
| `2` | No usable configuration, or a cloud endpoint that is not HTTPS. |
| `3` | The provider rejected the credentials. |
| `4` | The request failed in another way, for example an unknown model. |
| `5` | A network failure, a `429` or a `5xx`. |

::: warning `fluid ai test` crashes with no provider configured
As of 0.18.1, on a machine with no provider configured and no key in the environment, `fluid ai test` and `fluid ai test --json` stop with `Unexpected error: name 'detect_ollama_available' is not defined` and exit `2`, instead of the JSON report with `ai_test_no_provider`. Run `fluid ai setup` first, or pass `--provider` with a configured provider.
:::

### `ai models`

Shows each provider's primary, routing and tier models, and the stage plan: which stages use a model and which are deterministic. It reads the bundled model catalog, so it needs no API key.

```bash
fluid ai models --json
```

The JSON has one top-level key per provider (`anthropic`, `gemini`, `ollama`, `openai`), each with `provider`, `primary_model`, `routing_model`, `tier_models`, `tiered`, `stages` and `policy`. Filter it with `jq`:

```bash
fluid ai models --json | jq '.gemini.tier_models'
```

::: warning `fluid ai models --provider` is rejected
`fluid ai models` accepts `--provider`, but as of 0.18.1 the CLI checks that value against the infrastructure providers before the command runs. `fluid ai models --provider gemini` therefore exits `2` with `Unknown provider 'gemini' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake`. Use `fluid ai models --json` and filter by key. `fluid ai test --provider` and `fluid ai setup --provider` are not affected.
:::

## Notes

- `setup` is interactive and requires a TTY with `rich` installed. It walks through provider choice (Google Gemini, OpenAI, Anthropic, Ollama, or skip), validates the API key with a lightweight call, and persists settings.
- Provider config is written to `~/.fluid/ai_config.json` (chmod 600). API keys are stored in the OS keyring when available and are not written to the JSON file by default.
- If no keyring backend is available, the API key is kept only for the current process. Set `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1` only when you deliberately want plaintext local persistence.
- `OLLAMA_HOST` is restricted to localhost addresses for SSRF protection; non-local hosts are ignored and replaced with `http://localhost:11434`.
- The same setup flow is invoked inline on first use of [`fluid forge`](./forge.md) when no provider is configured.
- Provider environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.) are respected as a fallback.
- For strict provider validation, run `fluid forge data-model from-intent ... --require-llm` so provider failures do not silently fall back to heuristics.
- For tiered per-stage model selection, pass `--tiered` on the forge command. Tiering stays within the active provider and collapses to single-model mode when the provider has no distinct tier catalog.
- Use [`fluid doctor`](./doctor.md) to see AI status as part of a broader environment check.
- Full AI and model-first journeys are documented in [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md).

See [LLM Providers](../advanced/llm-providers.md) for provider defaults, tiering, strict mode, and Ollama notes.
