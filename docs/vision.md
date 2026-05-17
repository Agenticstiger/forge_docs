---
title: Vision & Roadmap
description: Why Fluid Forge exists, what we believe, and where we are headed.
---

# Vision & Roadmap

## Why we built this

Modern data engineering still feels like 2015 infrastructure work. You write SQL in dbt. You write IAM in Terraform. You write DAGs in Airflow. You write policies in OPA. You write masking rules in your warehouse's UI. Five tools, five languages, five ways for those four things to drift from each other. When the schema changes, **someone has to remember to update all four**, or production breaks at 3am.

Fluid Forge starts from a different premise: **a data product is a contract, not a pipeline.** A contract describes what the product is — its schema, its quality rules, its access policy, its AI gating, its sovereignty constraints — in one file. The pipeline is what falls out when a CLI compiles that contract for a target cloud.

That inversion changes how teams work. Instead of writing infrastructure code, you write the product specification. Instead of debugging four-tool drift, you change the contract and re-apply. Instead of asking *"who owns this DAG?"* you ask *"who owns this product?"* and the contract tells you.

## What we believe

These are the convictions baked into Forge. If you disagree with any of them, Forge is probably the wrong choice for your team — and that's fine.

1. **Schema, infrastructure, orchestration, policy, and AI gating belong in one file.** Splitting them across four tools is the source of most data-product incidents.
2. **Local-first development is non-negotiable.** You should be able to ship a working data product on your laptop with no cloud account, no credit card, no waiting on a platform team. `pipx install "data-product-forge[local]"` and you're three commands from a deployed product.
3. **Multi-cloud is the default state, not a migration.** Most companies are already multi-cloud (one team on Snowflake, another on BigQuery, a third on S3+Athena). Tools that pretend you're on a single cloud are lying to you.
4. **Governance is not a separate phase.** It's part of the contract from line one. Adding `accessPolicy` and `agentPolicy` after the fact is when teams discover that everything they shipped six months ago is non-compliant.
5. **AI access deserves the same gates as human access.** Agents reading your data are not a niche use case anymore — they're often the largest consumer. `agentPolicy` makes their boundaries declarative.
6. **Open source, Apache-2.0, no contributor agreement.** No vendor capture at the contract layer. The CLI is a community project; nobody can decide tomorrow that Forge is now Forge Cloud-only.
7. **Honest comparisons.** We don't pretend Forge wins everywhere. The [vs alternatives](/forge_docs/concepts/vs-alternatives.html) page tells you when **not** to use Forge — that's how a tool earns trust.

## Who this is for

- **Data engineers** at companies with two or more clouds, or compliance pressure (SOX, GDPR, HIPAA), or AI agents reading the data
- **Platform teams** building a self-service data platform — Forge is the contract layer your internal users write against
- **Data product owners** who don't want to learn five tools to ship one product
- **OSS contributors** who think the four-tool stack is broken and want to help fix it

## Who this is NOT for (yet)

- **Single-warehouse, single-team analytics shops** with no governance pressure — dbt is simpler. Adopt Forge when (or if) the cross-tool drift starts to bite.
- **Sub-second streaming workloads** — Forge's batch-and-mini-batch model fits 5-minute to 24-hour latency. For sub-second, look at Materialize / RisingWave.
- **Teams that need a hosted control plane today** — Forge is currently CLI + CI. Hosted UI is on the roadmap, not shipped.

## What problem it solves

Most teams still build data products with a pile of provider-specific scripts, IAM glue, orchestration code, and validation logic. That slows down delivery and makes cloud changes expensive.

Fluid Forge shifts that work into one contract-driven workflow:

```yaml
fluidVersion: "0.7.2"
kind: DataProduct
id: analytics.customers
name: Customer Analytics

metadata:
  owner:
    team: data-engineering

exposes:
  - exposeId: customers_table
    kind: table
    binding:
      platform: gcp
      location:
        dataset: analytics
        table: customers
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
        - name: email
          type: STRING
          sensitivity: pii
```

The contract becomes the source of truth for validation, planning, execution, verification, testing, and publishing.

## Core principles

### Declarative first

Describe the desired outcome. Let the CLI validate and execute it consistently.

### Local first

The recommended docs path starts locally:

```bash
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

### AI is optional

Use deterministic scaffolding with `fluid init`, or opt into guided generation with:

```bash
fluid forge
fluid forge --domain finance
```

### Same contract, different targets

Provider changes should not force a new mental model. The docs keep the same command language across local, GCP, AWS, and Snowflake.

## Lifecycle

### Design

```bash
fluid init my-project --quickstart
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
```

### Validate and govern

```bash
fluid validate contract.fluid.yaml
fluid policy-check contract.fluid.yaml
```

### Plan

```bash
fluid plan contract.fluid.yaml
fluid diff contract.fluid.yaml --env prod
```

### Deploy

```bash
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml
fluid generate schedule --scheduler airflow
```

### Operate

```bash
fluid test contract.fluid.yaml
fluid publish contract.fluid.yaml
fluid market --search "customer analytics"
```

## Versioning in the docs

- Current CLI release baseline: `0.8.0`
- Current scaffolded contract examples: `fluidVersion: 0.7.2`

That split is intentional. The CLI release and the contract schema version move on related but different timelines.

## Roadmap

| Milestone | Notes |
| --- | --- |
| `0.8.0` stable baseline | 11-stage production pipeline, signed bundles, rollback, DMM Access lineage, Jenkins generation defaults |
| `0.8.x` | Azure-related provider work remains on the roadmap |
| `0.9.x` | Databricks and broader platform integrations remain future work |

## Get involved

- [Getting Started](/forge_docs/getting-started/)
- [CLI Reference](/forge_docs/cli/)
- [Providers](/forge_docs/providers/)
- [Contributing](/forge_docs/contributing)

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions)
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues)
- **Want to contribute?** See [the contributing guide](/forge_docs/contributing)
