# `fluid ai`

Configure the AI / LLM provider used by Forge Copilot and inspect the current AI configuration.

## Syntax

```bash
fluid ai setup [--clear]
fluid ai setup --source CATALOG --name NAME
fluid ai status
fluid ai models [--provider PROVIDER] [--json]
```

Running `fluid ai` with no subcommand falls through to `status`.

## Key options

### `ai setup`

| Option | Description |
| --- | --- |
| `--clear` | Clear saved AI config and any API keys stored in the system keychain. |

`fluid ai setup --source CATALOG --name NAME` configures source-catalog credentials for `fluid forge data-model from-source` and MCP `forge_from_source` calls. `--source` is the catalog type (`snowflake`, `unity`, `bigquery`, `dataplex`, `glue`, `datahub`, or `datamesh_manager`); `--name` is the saved credential id.

### `ai status`

No options. Prints whether AI is configured and shows the active provider and model.

### `ai models`

Shows provider defaults, routing model, and tiered model plan. It does not require an API key because it reads the bundled model catalog.

## Examples

```bash
fluid ai setup
fluid ai setup --source snowflake --name snowflake-prod
fluid ai setup --clear
fluid ai status
fluid ai
fluid ai models
fluid ai models --provider gemini
fluid ai models --provider openai --json
```

## Notes

- `setup` is interactive and requires a TTY with `rich` installed. It walks through provider choice (Google Gemini, OpenAI, Anthropic, Ollama, or skip), validates the API key with a lightweight call, and persists settings.
- `setup --source` configures source-catalog credentials separately from LLM provider selection.
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
