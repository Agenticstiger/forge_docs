---
title: Advanced
description: Index of the pages in the advanced folder - operations, governance and security, AI and agents, runtime reference and architecture - with the question each one answers.
---

# Advanced

The pages in this folder cover the mechanism underneath the everyday commands: running Forge unattended in CI, the security boundaries, the AI authoring stack, and the runtime reference. The sidebar shows them under **Operations & advanced** and **Contract & runtime reference**; this page lists them in the same groups, with the question each one answers.

None of it is required reading. Start at [Concepts](../concepts/README.md) for the model and [CLI reference](../cli/README.md) for a command, and come here when you need the detail.

## Operate & deploy

| Page | The question it answers |
|---|---|
| [Operating in CI](./operating-in-ci.md) | How do I run the Jenkins pipeline unattended, and which stage gates what? |
| [Production troubleshooting](./production-troubleshooting.md) | A run failed in production: what do I run first, and what does this symptom mean? |
| [Airflow integration](./airflow.md) | How do I turn a contract into an Airflow DAG instead of hand-writing one? |
| [Blueprints](./blueprints.md) | Is there a template for this shape of data product, so I do not start from an empty file? |
| [Source-aligned acquisition](./source-aligned-acquisition.md) | How do I declare an ingestion from a source system rather than writing the pipeline that does it? |
| [DuckDB sandbox](./duckdb-sandbox.md) | What may SQL inside a contract read and write on the local engine, and how do I grant more? |

## Govern & secure

| Page | The question it answers |
|---|---|
| [Governance and compliance](./governance.md) | How do I declare access policy, classification and data residency in the contract, and what does the engine do when a binding contradicts them? |
| [Network safety](./network-safety.md) | Which outbound fetches are allowed by default, and how do I allow a host I trust? |
| [Credential resolver](./credential-resolver.md) | Where do catalog credentials live when an agent calls a tool, and what happens when none resolve? |

The sidebar puts one more page in this group, [Governance, compliance and the business case](../governance-compliance-roi.md), which lives outside this folder.

## AI & agents

| Page | The question it answers |
|---|---|
| [MCP server](./mcp.md) | How do I let an editor's AI author contracts, and how do I serve one expose of a published contract to an agent read-only? |
| [Built-in and custom Forge guidance](./custom-llm-agents.md) | What does `fluid forge --domain` already know, and where does deeper agent customisation fit? |
| [Forge discovery](./forge-copilot-discovery.md) | What does `fluid forge` look at in my workspace before it scaffolds, and how do I point it somewhere else or switch it off? |
| [Forge memory](./forge-copilot-memory.md) | Where does Forge keep what it remembers between runs, and how do I inspect, search or clear it? |
| [Authoring Forge tools](./forge-tools.md) | How do I add a new tool the agent loop can call? |
| [Guided `fluid forge` UX](./guided-forge-ux.md) | What happens between typing `fluid forge` and a file being written? |
| [LLM providers](./llm-providers.md) | Which providers can a forge data-model run use, and how do I select one? |
| [LiteLLM backend](./litellm-backend.md) | What does `--llm-provider <name>` resolve to, and what is the routing layer doing underneath? |
| [Capability warnings](./capability-warnings.md) | Why is the CLI warning me that my model does not support tool use, and what should I do about it? |
| [Cost tracking](./cost-tracking.md) | What did that run cost, and how do I override the price table for my org? |
| [ChatGPT contract-GPT packet](./chatgpt-forge-contract-gpt/README.md) | I am building a custom GPT that drafts FLUID contracts: which files do I upload to it? |
| [Agentic primitives](./agentic-primitives.md) | What are the reusable parts of the staged pipeline, and which one do I hook to watch a run? |

The sidebar also lists [Forge data model](../forge-data-model.md) here, which lives outside this folder.

## Runtime reference

| Page | The question it answers |
|---|---|
| [Environment variables](./environment-variables.md) | Which `FLUID_*` variable controls this, and which values does it accept? |
| [Error codes](./error-codes.md) | What are the parts of a catalogued failure (event name, `ERR_` code, suggestions, docs link), and which events have curated suggestions? |
| [Typed CLI errors](./typed-cli-errors.md) | What shape does a CLI error take, and can my CI parse it without a regex? |
| [Forge agent errors](./typed-errors.md) | A forge run raised `RateLimitError` or `ContextOverflowError`: is it retryable, and what do I change? |
| [API stability](./api-stability.md) | Which imports are safe to build a plugin on, and what notice do I get before one changes? |
| [Contract loading API](./contract-loading-api.md) | How does my Python code load a contract exactly as `fluid plan` sees it, with `fluid_build.api.load_contract`? |

The contract schema itself is in the [contract reference](../reference/README.md).

## Architecture

| Page | The question it answers |
|---|---|
| [Catalog integration: architecture](./v1.5-architecture.md) | Why is the catalog integration shaped the way it is, and where does a new adapter plug in? |
| [Catalog integration: release notes](./v1.5-release-notes.md) | What did the catalog-integration and cost-tracking work add, and in which release did it first ship? |
