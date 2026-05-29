---
home: true
heroText: Fluid Forge
tagline: Contract-first data products, from local DuckDB to multi-cloud delivery.
actions:
  - text: Get Started →
    link: /getting-started/
    type: primary
  - text: See it run
    link: /see-it-run
    type: secondary
  - text: CLI Reference
    link: /cli/
    type: secondary

features:
  - title: Local First
    details: Install the CLI, scaffold a project, validate it, and run it locally before you touch cloud credentials.
  - title: Contract-Driven
    details: Use one FLUID contract to describe the data product, then plan, test, verify, and publish from the same source of truth.
  - title: Promoted CLI Surface
    details: These docs track the current "fluid --help" experience so new users are not sent down stale or deprecated command paths.
  - title: AI-Optional
    details: Start with "fluid init" for a quickstart or use "fluid forge" when you want AI-assisted scaffolding and discovery.
  - title: Multi-Target Delivery
    details: Build locally with DuckDB, then target GCP, AWS, Snowflake, or standards/export flows when you are ready.
  - title: Compatibility Aware
    details: Legacy commands still exist in the docs where they matter, but primary pages lead with the current recommended workflow.

footer: Apache 2.0 Licensed | Documentation for the Fluid Forge CLI
---

> **Fluid Forge is for data engineers who want to write a data product contract once and deploy it anywhere.** Build and test locally with DuckDB, then push the same contract to BigQuery, Athena, or Snowflake — no pipeline glue code to maintain.

## What you don't need to do

Fluid Forge replaces the four-tool stack most data teams currently maintain. With one `contract.fluid.yaml`:

- **No Airflow DAG to write or maintain.** `fluid generate schedule --scheduler airflow|dagster|prefect` emits the right artifact.
- **No JVM heap tuning.** `engine: duckdb` runs embedded for dev; swap to `dlt` / `meltano` / `airbyte` / `kafka-connect` / `debezium` only when you need them.
- **No Snowflake permission sprawl.** `accessPolicy.grants` compiles to native `GRANT` statements.
- **No Terraform for data-product IAM.** `policy-apply` emits BigQuery IAM bindings, Snowflake roles, S3 bucket policies — same source.
- **No 27 questions before you ship.** `fluid forge` infers from your local files; you answer 4.
- **No dbt project layout decisions.** Forge wraps dbt; you write the contract, dbt does what it does best.
- **No AI access surprises.** `agentPolicy` declares which LLMs can read what, with audit logs, before any model gets a row.
- **No vendor lock.** `binding.platform: snowflake` → `binding.platform: bigquery` is the only line that moves.

→ See the comparison page: [Forge vs dbt / Dagster / Terraform / Snowpark](/forge_docs/concepts/vs-alternatives.html) for the honest breakdown of when Forge does and doesn't fit.

## See it run

A 60-second walkthrough of the core move: write one `contract.fluid.yaml`, build and test it locally on DuckDB, then ship the **same file** to BigQuery and Snowflake — the only line that changes is `binding.platform`.

<iframe
  src="/forge_docs/reels/one-contract-every-cloud.html"
  width="100%"
  height="680"
  style="border: 1px solid var(--vp-c-border); border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Fluid Forge — one contract, every cloud">
</iframe>

Use ←/→ to step scenes, space to pause, r to restart. **[See all reels →](/forge_docs/see-it-run.html)** — quickstart, source-aligned Bronze, guided forge UX, day-2 ops, and more.

## Start with the current workflow

```bash
pip install data-product-forge
fluid version
fluid doctor
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

This docs site currently tracks:

- CLI release `0.8.6`
- Scaffolded contract examples using `fluidVersion: 0.7.4` (older `0.7.3` / `0.7.2` contracts remain valid)

`fluid version` and `fluidVersion` are different things. The first is the CLI release you installed. The second is the schema version inside a contract.

## Optional AI-assisted scaffolding

```bash
fluid forge
fluid forge --domain retail
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
```

Use `fluid forge` when you want discovery, memory, and LLM-guided scaffolding. Use `fluid init` when you want the fastest deterministic quickstart.

For model-first work, forge from a business intent file and then generate dbt:

```bash
fluid forge data-model from-intent --example retail > intent.yaml
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

For every AI and data-model journey, including hosted provider strict mode, Ollama, DDL, source catalogs, review/diff/learn, and scheduling, see [AI Forge And Data-Model Journeys](/forge_docs/walkthrough/ai-forge-data-model.html).

## Promoted command groups

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `forge data-model`, `validate`, `plan`, `apply`, `ship` |
| Generate | `generate transformation`, `generate dbt-tests`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import` |
| Quality & Governance | `policy-check`, `diff`, `test`, `verify`, `contract` |
| Day-2 Ops | `runs`, `retention`, `secrets`, `stats` |
| Utilities | `config`, `split`, `bundle`, `auth`, `doctor`, `providers`, `memory`, `mcp`, `version` |

::: tip Current release — `0.8.6`, schema **0.7.4** GA
`0.8.6` ships the **MCP output-port gateway** with runtime `agentPolicy` enforcement at the gateway (schema **0.7.4**), JWT-bearer + mTLS gateway identity, BigQuery row-access-policy + AWS Lake Formation IAM compilers, PostgreSQL + AWS Athena drivers, and PII/PHI value redaction — see [`fluid mcp`](/forge_docs/cli/mcp.html). It builds on the **SDP / ADP / CDP** Data Mesh vocabulary alongside the medallion `Bronze / Silver / Gold` layers, **six ingestion engines** (`duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium`), the guided `fluid forge` UX (mode picker, welcome scan, slash commands, preview panel), **three plugin extension points** (`fluid_build.commands` / `fluid_build.extension_validators` / `fluid_build.apply_hooks`), and a companion **SDK** (`data-product-forge-sdk`). See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Product Types](/forge_docs/data-products/product-type.html), and [SDK & Plugins](/forge_docs/sdk-and-plugins/) for the full picture.
:::

## Where to go next

- [Getting Started](/forge_docs/getting-started/) for the local-first path
- [SDK & Plugins](/forge_docs/sdk-and-plugins/) — extend the CLI with your own scaffolds, validators, and apply-hooks
- [Forge Data Model](/forge_docs/forge-data-model.html) for intent, DDL, and catalog-driven model generation
- [AI Forge And Data-Model Journeys](/forge_docs/walkthrough/ai-forge-data-model.html) for end-to-end AI-assisted and deterministic flows
- [CLI Reference](/forge_docs/cli/) for the promoted command surface
- [Providers](/forge_docs/providers/) for platform-specific guidance
- [Walkthroughs](/forge_docs/walkthrough/local) for end-to-end examples

Compatibility note:
`fluid generate-airflow` is still available, but primary docs now lead with `fluid generate schedule --scheduler airflow`.

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions) — we read every one.
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues) with what you ran and what you saw.
- **Want to contribute?** See [the contributing guide](./contributing.md) — we welcome doc fixes, examples, and providers.
