# Built-in And Custom Forge Guidance

This page explains the public `fluid forge` domain-guidance flow and where deeper agent customization now fits.

## Public user workflow

For end users, the current public entry point is:

```bash
fluid forge
fluid forge --domain finance
fluid forge --domain healthcare
fluid forge --domain retail
fluid forge --domain telco
```

`--llm-provider` accepts `openai`, `anthropic`, `gemini` and `ollama`, plus the keyless `mcp-sampling`, `claude-code`, `codex`, `cursor` and `kiro`. See [LLM Providers](./llm-providers.md).

## Key Forge flags

```bash
fluid forge \
  --llm-provider openai \
  --llm-model gpt-4.1-mini \
  --discovery-path ./data \
  --context ./forge-context.json
```

Useful flags:

- `--domain`
- `--llm-provider`
- `--llm-model`
- `--llm-endpoint`
- `--discovery-path`
- `--context`
- `--memory` / `--no-memory`
- `--save-memory`
- `--prompt-profile` and `--prompt-overlay`
- `--non-interactive`

## What changed

Older docs sometimes described:

- `fluid forge --mode copilot`
- `fluid forge --mode agent --agent <name>`

Those are no longer the public, primary docs path. Current docs lead with `fluid forge` plus `--domain` when you want built-in domain guidance.

## Built-in domain guidance

The built-in domains are backed by declarative specs inside `forge-cli`, and users interact with them through `--domain`. The CLI's own help names `finance`, `healthcare`, `retail` and `telco`. The 0.18.1 package also ships specs named `education`, `energy`, `government`, `insurance`, `logistics`, `manufacturing`, `media` and `pharma`.

Two prompt profiles ship as well, `ai-lab-permissive` and `eu-gdpr-strict`, and two overlays, `pii-lockdown` and `strict-json-reinforce`. Select them with `--prompt-profile` and `--prompt-overlay`. A profile replaces the default agent-policy guidance the model is given. `eu-gdpr-strict`, for example, tells it to attach a restrictive `policy.agentPolicy` to every expose that may carry personal data.

## When custom agent work still matters

Contributor-level customization can still matter if you are extending `forge-cli` itself and want to:

- add a new built-in domain
- change domain-specific prompts or defaults
- alter how domain guidance is sourced from internal specs

That work is implementation detail for CLI contributors, not the primary docs path for day-to-day users.

## Related guides

- [Forge discovery guide](./forge-copilot-discovery.md)
- [Forge memory guide](./forge-copilot-memory.md)
- [`fluid forge` CLI reference](../cli/forge.md)
