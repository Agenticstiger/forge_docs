---
title: Vision & Roadmap
description: Why Fluid Forge exists and how the current docs align to the modern CLI.
---

# Vision & Roadmap

Fluid Forge treats data products as contracts first, execution second.

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
fluid forge --llm-provider openai --llm-model gpt-4o-mini
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

- Current CLI release baseline: `0.7.9`
- Current scaffolded contract examples: `fluidVersion: 0.7.2`

That split is intentional. The CLI release and the contract schema version move on related but different timelines.

## Roadmap

| Milestone | Notes |
| --- | --- |
| `0.7.9` docs baseline | Promoted CLI surface, local-first onboarding, `forge` refresh |
| `0.8.x` | Azure-related provider work remains on the roadmap |
| `0.9.x` | Databricks and broader platform integrations remain future work |

## Get involved

- [Getting Started](/getting-started/)
- [CLI Reference](/cli/)
- [Providers](/providers/)
- [Contributing](/contributing)

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions)
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues)
- **Want to contribute?** See [the contributing guide](/contributing)
