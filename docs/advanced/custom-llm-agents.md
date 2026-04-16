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

Built-in LLM providers include:

- OpenAI
- Anthropic
- Gemini
- Ollama

## Key Forge flags

```bash
fluid forge \
  --llm-provider openai \
  --llm-model gpt-4o-mini \
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
- `--non-interactive`

## What changed

Older docs sometimes described:

- `fluid forge --mode copilot`
- `fluid forge --mode agent --agent <name>`

Those are no longer the public, primary docs path. Current docs lead with `fluid forge` plus `--domain` when you want built-in domain guidance.

## Built-in domain guidance

The built-in domains are still backed by declarative specs inside `forge-cli`, but users interact with them through `--domain`.

Current built-in domains:

- `finance`
- `healthcare`
- `retail`
- `telco`

## When custom agent work still matters

Contributor-level customization can still matter if you are extending `forge-cli` itself and want to:

- add a new built-in domain
- change domain-specific prompts or defaults
- alter how domain guidance is sourced from internal specs

That work is implementation detail for CLI contributors, not the primary docs path for day-to-day users.

## Related guides

- [Forge discovery guide](./forge-copilot-discovery.md)
- [Forge memory guide](./forge-copilot-memory.md)
- [`fluid forge` CLI reference](/cli/forge.md)
