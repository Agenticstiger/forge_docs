---
title: What is a contract?
description: The data structure at the heart of every Fluid Forge data product.
---

# What is a Contract?

A **Fluid Forge contract** is a single YAML file that fully describes a data product — its identity, who owns it, how it's built, what it exposes, and who's allowed to read it. The CLI (`fluid validate`, `fluid plan`, `fluid apply`) reads the contract, compiles it for your target cloud, and ships it. Nothing else is the source of truth.

## The 5 required top-level fields

Every contract must declare:

| Field | Purpose |
|-------|---------|
| `fluidVersion` | Schema version — pinned per file. Today `"0.7.2"` is the latest; the CLI accepts `0.4.0`, `0.5.7`, `0.7.1`, and `0.7.2` for backward compatibility. |
| `kind` | Always `DataProduct` for now. Future kinds (e.g., `DataProductGroup`) are reserved. |
| `id` | Globally unique product identifier in dotted form: `gold.crypto.bitcoin_tracker_v1`. Used in lineage, catalogs, and IAM principal naming. |
| `name` | Human-readable name, shown in catalogs and dashboards. |
| `metadata` | Owner team + email + (optionally) layer, domain, tags, business context. |
| `exposes` | At least one output (table / view / file / topic). See [Builds, Exposes, Bindings](./builds-exposes-bindings.md). |

::: tip Schema vs CLI version
`fluidVersion` is the **contract schema** version (currently `0.7.2`). The CLI version is separate — at the time of writing the CLI ships at `0.8.0`. A v0.8.x CLI happily reads contracts with `fluidVersion: "0.7.1"` or older.
:::

## Minimal valid contract

```yaml
fluidVersion: "0.7.2"
kind: DataProduct
id: example.hello_world_v1
name: Hello World
domain: example

metadata:
  layer: Bronze
  owner:
    team: learning-team
    email: team@example.com

exposes:
  - exposeId: hello_output
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./runtime/out/hello.csv
    contract:
      schema:
        - name: message
          type: STRING
        - name: created_at
          type: TIMESTAMP
```

That's the smallest contract Fluid Forge will accept. Save it as `contract.fluid.yaml`, run `fluid validate`, and you'll get ✅ — even though there's no `builds` block. Validation passes; `apply` will then prompt you to point at real data.

## Why a contract — and not separate dbt / Terraform / Airflow / OPA files?

The four-tool stack drifts. The dbt model says one thing about the schema; the Terraform that provisions the table says another; the Airflow DAG declares its own SLA; the OPA policy guards a slightly different field list. Every drift is an incident waiting to happen.

The contract is the single file all four tools agree on. When you change the schema in `exposes[].contract.schema`, every downstream artifact (the IAM bindings, the orchestration job, the policy, the agentPolicy) recomputes from the same source. There is no "where do I update this?" question.

## Layered structure: what goes in the contract, in priority

| Block | What it answers | Required? |
|---|---|---|
| `fluidVersion`, `kind`, `id`, `name`, `metadata` | "What is this?" | Always |
| `exposes[]` | "What does this product produce?" (table / view / file / topic) | At least one |
| `builds[]` | "How is it computed?" (SQL / Python / dbt / external code) | When the product is computed (not for raw exposes) |
| `accessPolicy.grants[]` | "Who's allowed to read or write it?" | When you have human or service principals to gate |
| `agentPolicy` | "Which AI / LLM agents can use it, for what?" | When agents read this product |
| `dq.rules[]` | "What does 'correct' mean for this product?" (completeness, freshness, drift, valid_values) | Strongly recommended for production |
| `slas[]` | "How fresh / how available?" (response time, freshness window) | When you publish to consumers |
| `sovereignty` | "Where can this data physically live? Under which regulations?" | When jurisdiction matters (GDPR, HIPAA, sovereignty laws) |
| `lineage` | "What does this product depend on?" | Auto-emitted; override only for cross-system lineage |

You don't need every block. A local-only Bronze contract often has just `fluidVersion + kind + id + name + metadata + exposes`. A Gold-layer customer-360 contract used by the AI team probably has all 9 blocks.

## Versioning: schema evolution without breaking consumers

The contract has its own version (`fluidVersion`) separate from the data product's version (`exposes[].version`). They evolve independently:

- **`fluidVersion`** is the **contract schema** version. Today: `0.7.2`. Pinned per file so older contracts keep working under newer CLI releases. The CLI accepts `0.4.0`, `0.5.7`, `0.7.1`, and `0.7.2` for backward compatibility.
- **`exposes[].version`** is the **data product** version. Bump it when the product's contract changes in a way consumers care about. Use semver: `1.0.0` → `1.1.0` adds an optional column; `1.0.0` → `2.0.0` removes or renames one.

`fluid plan` flags breaking changes between contract versions before `apply` runs. The CLI refuses to silently break consumers — you have to acknowledge the bump explicitly.

## Common patterns

### Bronze: source-aligned, minimal contract
The first contract you write when bringing a new data source online. Often produced by `fluid init --discover postgres://…` — auto-emits an `exposes[]` per source table, no `builds`. Schema-as-contract; nothing computed.

### Silver: cleaned + conformed
Adds `builds[]` (typically `engine: sql` or `engine: dbt`) that joins/cleans Bronze sources. Adds `dq.rules` to enforce cleanliness. Still uses Internal classification; rarely has `agentPolicy`.

### Gold: business-facing, governed
Adds `accessPolicy.grants` (RBAC), often `agentPolicy` (gate AI access), `sovereignty` (regulatory framework), `slas` (response time / freshness commitments). The contract is the public face of the product.

### Multi-tenant: same product, different audiences
Use multiple `exposes[]` entries on one contract — one per audience — each with its own `binding` and `policy.authz`. The `builds` are shared so the underlying compute happens once.

## Where to look next

- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — the three core blocks that turn a stub into a real product.
- [Governance & Policy](./governance-policy.md) — how `accessPolicy`, `agentPolicy`, and `sovereignty` work together.
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) — how `dq.rules`, `slas`, and lineage emit artifacts.
- [Local walkthrough](/forge_docs/walkthrough/local) — build a Netflix analytics contract from scratch.
- [Validate command](/forge_docs/cli/validate) — what schema rules are checked, and what error messages mean.
