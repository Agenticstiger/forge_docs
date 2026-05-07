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

---

::: warning These pages are stubs
Each concept page in this folder ships with:
- a one-paragraph definition
- a tiny example
- pointers to the canonical existing content (walkthroughs, CLI reference, schema files)

Full long-form treatments are tracked in [GitHub issues](https://github.com/Agentics-Rising/forge_docs/issues?q=is%3Aopen+label%3Adocs-content) — a great place to contribute. Pick a stub, write it up, open a PR.
:::
