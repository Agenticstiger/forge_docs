---
title: Concepts
description: The conceptual model behind Fluid Forge — learn-once reference for everything in a contract.
---

# 📒 Concepts

Everything in this section is **learn-once reference**. If you've already shipped a contract, you can skip ahead to the [CLI Reference](/forge_docs/cli/) or [Walkthroughs](/forge_docs/walkthrough/local). If you're new, read these in order — each builds on the last.

## In this section

| Page | What you'll learn |
|------|-------------------|
| [What is a Contract](./contract.md) | The 5 required fields, the schema versioning model, and how Fluid Forge thinks about a "data product." |
| [Builds, Exposes, Bindings](./builds-exposes-bindings.md) | The three core blocks of every contract — how data is *produced*, what it *exposes*, and where it *lands*. |
| [Providers vs Platforms](./providers-vs-platforms.md) | The difference between a `binding.platform` value and the provider plugin that handles it. Why `local` runs everywhere. |
| [Quality, SLAs & Lineage](./quality-sla-lineage.md) | `dq.rules`, `qos`, and how `lineage` is auto-derived. Block bad deploys before they happen. |
| [Governance & Policy](./governance-policy.md) | `accessPolicy.grants`, sovereignty constraints, and how Fluid Forge compiles to native cloud IAM. |
| [Agent Policies (LLM/AI)](./agent-policy.md) | New in v0.7.1 — declarative boundaries on which AI models can read which fields. |
| [vs alternatives](./vs-alternatives.md) | Honest comparisons against dbt, Terraform, Airflow, OPA, and Snowpark. |

::: tip In a hurry?
The single most important concept is **the contract is the source of truth**. Everything Fluid Forge does — schema validation, IAM compilation, SLA checks, lineage extraction — is derived from one YAML file you control. Everything else is mechanism.
:::

## What's next

- **First time here?** Read [What is a Contract](./contract.md) → [Builds, Exposes, Bindings](./builds-exposes-bindings.md) in order. ~15 minutes.
- **Comparing tools?** Skip to [Forge vs dbt / Dagster / Terraform / Snowpark](./vs-alternatives.md) for the honest breakdown.
- **Ready to build?** Drop into [Get Started](/forge_docs/getting-started/) and ship a real product locally in 30 seconds.
