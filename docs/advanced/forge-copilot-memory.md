# Forge Memory Guide

This guide explains how project-scoped memory works in the current `fluid forge` flow.

## Current public entry point

Use `fluid forge`, not the older `fluid forge --mode copilot` syntax from archived examples.

Examples:

```bash
fluid forge --llm-provider openai --llm-model gpt-4o-mini
fluid forge --no-memory
fluid forge --show-memory
fluid forge --reset-memory
```

## Memory file location

Project-scoped memory lives at:

```text
runtime/.state/copilot-memory.json
```

It is:

- repo-local
- bounded
- advisory
- separate from validation

## What memory does

When present, memory helps Forge remember stable project conventions such as:

- preferred provider
- preferred template or scaffold shape
- domain hints
- prior build engines
- binding conventions
- bounded schema summaries

## Precedence

Forge treats memory as a soft preference.

The effective precedence is:

1. explicit CLI flags and context input
2. current-run answers
3. current discovery
4. saved project memory
5. built-in defaults

## What is not stored

Memory is not a raw session dump. It does not store:

- API keys
- tokens
- raw sample rows
- full SQL
- full README text
- full contract bodies

## Saving and bypassing memory

- Use `--no-memory` to ignore saved memory for a run
- Use `--save-memory` to persist memory in non-interactive automation
- Use `--show-memory` to inspect the remembered summary
- Use `--reset-memory` to clear the saved file

## Related guides

- [Forge discovery guide](./forge-copilot-discovery.md)
- [CLI reference for `fluid forge`](../cli/forge.md)
