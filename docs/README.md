---
home: true
heroText: Fluid Forge
tagline: Contract-first data products — from local DuckDB to any cloud, trusted by your team and safe for your AI agents.
actions:
  - text: Get Started →
    link: /getting-started/
    type: primary
  - text: Why Fluid Forge
    link: /why
    type: secondary
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
  - title: Sovereignty Enforced
    details: Pin a jurisdiction in the contract and the engine blocks a mismatched binding. An EU contract on us-east-1 fails "fluid validate" with exit 1, and strict is the default.
  - title: AI-Optional
    details: Start with "fluid init" for a quickstart or use "fluid forge" when you want AI-assisted scaffolding and discovery.
  - title: Multi-Target Delivery
    details: Build locally with DuckDB, then target GCP, AWS, Snowflake, or standards/export flows when you are ready.
  - title: Deterministic Plans
    details: Run "fluid plan" ten times over one unchanged contract and the plan digest comes back identical ten times. Only the generated_at timestamp moves.

footer: Apache 2.0 Licensed | Documentation for the Fluid Forge CLI
---

> **Fluid Forge is for data engineers who want to write a data product contract once and deploy it anywhere.** Build and test locally with DuckDB, then push the same contract to BigQuery, Athena, or Snowflake — no pipeline glue code to maintain.

## What you don't need to do

Fluid Forge replaces the five-tool stack most data teams currently maintain. With one `contract.fluid.yaml`:

- **No Airflow DAG to write or maintain.** `fluid generate schedule --scheduler airflow|dagster|prefect` emits the right artifact.
- **No JVM heap tuning.** `engine: duckdb` runs embedded for dev; swap to `dlt` / `meltano` / `airbyte` / `kafka-connect` / `debezium` only when you need them.
- **No Snowflake permission sprawl.** `accessPolicy.grants` compiles to native `GRANT` statements.
- **No Terraform for data-product IAM.** `policy-apply` emits BigQuery IAM bindings, Snowflake roles, S3 bucket policies — same source.
- **No 27 questions before you ship.** `fluid forge` infers from your local files; you answer 4.
- **No dbt project layout decisions.** Forge wraps dbt; you write the contract, dbt does what it does best.
- **No AI access surprises.** `agentPolicy` declares which LLMs can read what, with audit logs, before any model gets a row.
- **No vendor lock.** The swap is confined to the `binding` block. Measured with `diff` against the published [`sovereignty-platform-swap` example](https://github.com/Agenticstiger/forge-cli/tree/v0.15.0/examples/sovereignty-platform-swap): **11 changed lines** to move one product from AWS to GCP, **12** to move it to Snowflake, one hunk each, nothing outside `binding` touched — schema, quality rules, ownership and SLO all stay byte-identical.

→ See the comparison page: [Forge vs dbt / Dagster / Terraform / Snowpark](/forge_docs/concepts/vs-alternatives.html) for the honest breakdown of when Forge does and doesn't fit.

## See it run

A 60-second walkthrough of the core move: write one `contract.fluid.yaml`, build and test it locally on DuckDB, then ship the **same contract** to BigQuery and Snowflake — every changed line lands inside the `binding` block (11 of them for GCP, 12 for Snowflake; run the `diff` yourself in the [example](https://github.com/Agenticstiger/forge-cli/tree/v0.15.0/examples/sovereignty-platform-swap)).

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

- CLI release `0.15.0`
- Contract schema `0.7.5` as the stable default, with `0.7.6` open as an opt-in preview

Which `fluidVersion` a fresh scaffold actually writes depends on which scaffold path you took, and the quickstart is not the same as the factory. The rule, with the per-path numbers, lives in one place: [Understand the version numbers](/forge_docs/getting-started/#understand-the-version-numbers). Run `fluid version` for the authoritative list of accepted schema versions on the CLI you have installed.

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

These are the groups `fluid --help` prints on `0.15.0`. Run it yourself to confirm the table below.

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `validate`, `plan`, `apply` |
| Generate | `generate transformation`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import`, `mcp` |
| Quality & Governance | `policy-check`, `test` |
| Safety & Supply Chain | `rollback`, `verify-signature` |
| Utilities | `config`, `ai`, `split`, `auth`, `doctor`, `providers`, `exporters`, `version` |

`--help` promotes a short surface, not the whole one. Commands such as `bundle`, `diff`, `verify`, `publish`, `runs`, `stats`, `ship` and [`mission`](/forge_docs/cli/mission.html) are real and documented, and `--help` itself names the production path as `bundle` → `validate` → `generate artifacts` → `diff` → `plan` → `apply` → `verify` → `publish`. See the [CLI Reference](/forge_docs/cli/) for everything.

::: tip Current release — `0.15.0`, schema **0.7.5** stable (GA)
`0.15.0` is the current release ([release notes](/forge_docs/RELEASE_NOTES_0.15.0.html)). Its headline is **sovereignty enforcement**: data-residency controls that previously reported clean while checking nothing now actually block, with `sovereignty.enforcementMode` driving severity in both directions, engine defaults realigned to the schema's, and the region→jurisdiction table derived from vendor data. A contract that passed [`fluid validate`](/forge_docs/cli/validate.html) on `0.14.1` can fail here. Recent releases below it: [`0.14.0`](/forge_docs/RELEASE_NOTES_0.14.0.html) was the **live-verification hardening** release (the dbt Iceberg loop reaching all three cloud warehouses); [`0.13.0`](/forge_docs/RELEASE_NOTES_0.13.0.html) brought **verifiable autonomy + declarative packaging** with the new [`fluid mission`](/forge_docs/cli/mission.html) command; [`0.12.0`](/forge_docs/RELEASE_NOTES_0.12.0.html) landed **dbt integration + schema GA**, promoting contract schema `0.7.5` to stable as the default for untagged contracts and shipping the brownfield [`fluid import dbt`](/forge_docs/cli/import.html) importer, the MetricFlow bridge and `fluid verify --reconcile-lineage`; `0.11.0` brought the **AI-ready / RAG** surface (vector output port preview, semantic-drift guard, `ai_ready` agent, LocalStack-compatible AWS apply); `0.10.0` matured the **plugin platform** (operator trust boundary via `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST`, [`fluid plugins`](/forge_docs/cli/plugins.html) + [`fluid exporters`](/forge_docs/cli/exporters.html), and the `odps` / `odcs` provider→exporter reclassification); the streaming **Kafka → Iceberg sink** shipped in `0.9.0`; and the **MCP output-port gateway** — runtime `agentPolicy` enforcement with JWT-bearer + mTLS identity — arrived in `0.8.7` ([`fluid mcp`](/forge_docs/cli/mcp.html)). The platform builds on the **SDP / ADP / CDP** Data Mesh vocabulary alongside the medallion `Bronze / Silver / Gold` layers, **six ingestion engines** (`duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium`), the guided `fluid forge` UX (mode picker, welcome scan, slash commands, preview panel), and a companion **SDK** (`data-product-forge-sdk`). See [SDK & Plugins](/forge_docs/sdk-and-plugins/), [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), and [Product Types](/forge_docs/data-products/product-type.html) for the full picture.
:::

## Where to go next

- [Getting Started](/forge_docs/getting-started/) for the local-first path
- [SDK & Plugins](/forge_docs/sdk-and-plugins/) — extend the CLI with your own scaffolds, validators, and apply-hooks
- [Forge Data Model](/forge_docs/forge-data-model.html) for intent, DDL, and catalog-driven model generation
- [AI Forge And Data-Model Journeys](/forge_docs/walkthrough/ai-forge-data-model.html) for end-to-end AI-assisted and deterministic flows
- [CLI Reference](/forge_docs/cli/) for the promoted command surface
- [Governance & Sovereignty](/forge_docs/advanced/governance.html) for how `sovereignty` and `agentPolicy` are enforced, and where
- [Providers](/forge_docs/providers/) for platform-specific guidance
- [Walkthroughs](/forge_docs/walkthrough/local) for end-to-end examples

Compatibility note:
`fluid generate-airflow` is still available, but primary docs now lead with `fluid generate schedule --scheduler airflow`.

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions) — we read every one.
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues) with what you ran and what you saw.
- **Want to contribute?** See [the contributing guide](./contributing.md) — we welcome doc fixes, examples, and providers.
