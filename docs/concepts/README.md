---
title: Concepts
description: The model behind Fluid Forge, in reading order - the contract, how it is split and composed, where it runs, how it is governed, and how other systems read it.
---

# Concepts

These pages explain how Fluid Forge works and why. They are explanation, not steps: to build something, start with [Getting Started](../getting-started/README.md); to look up a field or a flag, use the [contract reference](../reference/README.md) or the [CLI reference](../cli/README.md).

The one idea underneath them all: **the contract is the source of truth.** Schema validation, the plan, the cloud resources, the access rules and the checks `fluid verify` runs are all derived from one contract you control, written as one file or as a root plus fragments.

## Reading order

Each page builds on the ones before it.

### The contract

| Page | What it explains |
| --- | --- |
| [What is a contract](./contract.md) | The required top-level fields (`fluidVersion`, `kind`, `id`, `name`, `metadata`, `exposes`), how `fluidVersion` selects the schema, and what the CLI does with the document. |
| [Contract fragments](./fragments.md) | Writing one product as a root contract plus fragment files: the layout `fluid split` writes and which commands read it. |
| [Composing a contract with `$ref`](./contract-refs.md) | How a single `$ref` is resolved, and the ref root that confines which files a fragment may come from. |
| [Builds, exposes, bindings](./builds-exposes-bindings.md) | The three main blocks of a contract: how data is produced, what the product offers, and where it lands. |

### Where it runs

| Page | What it explains |
| --- | --- |
| [Providers vs platforms](./providers-vs-platforms.md) | The difference between a `binding.platform` value and the provider plugin that handles it. |
| [Workspaces](./workspaces.md) | `fluid.workspace.yaml`: how chained products find each other, which environments a product has, and what contract SQL may read. |
| [Environments and overlays](./environments-and-overlays.md) | How `--env` picks an overlay that patches the base contract for a stage (`dev`, `prod`) or a cloud (`aws`, `gcp`). |
| [OpenTofu state](./state.md) | Where `fluid apply` keeps state for a cloud contract, the per-provider key, and which commands read it. |

### Trust and governance

| Page | What it explains |
| --- | --- |
| [Quality, SLAs and lineage](./quality-sla-lineage.md) | Data-quality rules (`dq.rules`), SLAs (`qos`), and lineage declared in the contract and then checked. |
| [Governance and policy](./governance-policy.md) | `accessPolicy.grants`, column restrictions and masking, and which command does what with them. |
| [Governance parity](./governance-parity.md) | Retention, encryption, column restrictions and grants declared once and enforced on AWS and on GCP, and what `fluid verify` checks on each. |
| [Sovereignty](./sovereignty.md) | Where data may live: `enforcementMode`, and the provision-time and query-time gates. |
| [Agent policy](./agent-policy.md) | `exposes[].policy.agentPolicy`: which AI models may read an expose, and for what. |

### How others read it

| Page | What it explains |
| --- | --- |
| [The semantic layer](./semantic-layer.md) | Measures, dimensions and metrics declared in `exposes[].semantics`, and the three parts of the CLI that read them. |
| [Product types](../data-products/product-type.md) | `metadata.productType` (SDP, ADP, CDP) beside the medallion layer, and the `consumes[]` composition rules `fluid validate` checks. |
| [Consuming products from another mesh](./federation.md) | Pinning an upstream contract that lives in another repository or catalog, and what apply does when it changes. |
| [The CLI and the Command Center](./command-center.md) | What `fluid publish` and `fluid apply` send to a FLUID Command Center, and how to turn reporting off. |

### Choosing Fluid Forge

| Page | What it explains |
| --- | --- |
| [Fluid Forge vs alternatives](./vs-alternatives.md) | Where Forge overlaps with dbt, Terraform, Airflow, OPA and Snowpark, and where it does not fit. |

## What's next

- **First time here?** Read [What is a contract](./contract.md), then [Builds, exposes, bindings](./builds-exposes-bindings.md).
- **Taking a product to two clouds?** Read [Environments and overlays](./environments-and-overlays.md) and [Governance parity](./governance-parity.md), then follow [One contract, two clouds](../recipes/one-contract-two-clouds.md).
- **Looking up a field?** The [contract reference](../reference/README.md) lists the fields of schema 0.7.5 and the 0.7.6 preview.
