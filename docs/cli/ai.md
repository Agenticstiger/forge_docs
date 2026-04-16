# `fluid ai`

Configure the AI / LLM provider used by Forge Copilot and inspect the current AI configuration.

## Syntax

```bash
fluid ai setup [--clear]
fluid ai status
```

Running `fluid ai` with no subcommand falls through to `status`.

## Key options

### `ai setup`

| Option | Description |
| --- | --- |
| `--clear` | Clear saved AI config and any API keys stored in the system keychain. |

### `ai status`

No options. Prints whether AI is configured and shows the active provider and model.

## Examples

```bash
fluid ai setup
fluid ai setup --clear
fluid ai status
fluid ai
```

## Notes

- `setup` is interactive and requires a TTY with `rich` installed. It walks through provider choice (Google Gemini, OpenAI, Anthropic, Ollama, or skip), validates the API key with a lightweight call, and persists settings.
- Provider config is written to `~/.fluid/ai_config.json` (chmod 600). API keys are also mirrored to the OS keyring when available.
- `OLLAMA_HOST` is restricted to localhost addresses for SSRF protection; non-local hosts are ignored and replaced with `http://localhost:11434`.
- The same setup flow is invoked inline on first use of [`fluid forge`](./forge.md) when no provider is configured.
- Provider environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.) are respected as a fallback.
- Use [`fluid doctor`](./doctor.md) to see AI status as part of a broader environment check.
