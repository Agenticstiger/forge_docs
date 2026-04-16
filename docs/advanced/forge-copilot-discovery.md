# Forge Discovery Guide

This guide explains how the current `fluid forge` flow discovers local context before it scaffolds a project.

## Current public entry point

Use `fluid forge`, not the older `fluid forge --mode copilot` examples that may still appear in archived material.

Examples:

```bash
fluid forge
fluid forge --discovery-path ./data
fluid forge --discovery-path ../shared-schemas
fluid forge --no-discover
```

## What discovery is for

Discovery gives Forge grounded local context so it can:

- ask fewer follow-up questions
- infer useful provider or domain hints
- summarize local schemas without sending raw rows
- generate a stronger first contract draft

## What Forge scans

Forge may inspect local:

- SQL files
- dbt projects
- Terraform files
- existing FLUID contracts
- README headings
- sample CSV, JSON, JSONL, Parquet, and Avro files

## Optional helpers

If you want richer Parquet and Avro schema inspection, install the optional discovery helpers:

```bash
pip install "fluid-forge[copilot]"
```

That adds local readers such as `pyarrow` and `fastavro`. Without them, Forge can still discover files, but schema extraction is more limited.

## Privacy boundary

Discovery is metadata-first.

Forge sends distilled summaries such as:

- column names
- inferred scalar types
- referenced tables
- provider hints
- existing contract ids and expose ids

Forge does not send:

- raw sample rows
- full file contents
- secrets
- API keys
- passwords

## How discovery affects generation

Discovery is combined with:

- CLI flags
- current-run answers
- optional project memory
- built-in defaults

That combined context shapes the contract draft and any follow-up prompts.

## Related guides

- [Forge memory guide](./forge-copilot-memory.md)
- [CLI reference for `fluid forge`](/cli/forge.md)
