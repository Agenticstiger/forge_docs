---
title: What is a contract?
description: The data structure at the heart of a Fluid Forge data product - the required fields, the version, where each block lives, and what the CLI does with it.
---

# What is a Contract?

If you came here from the second line of a contract, this is the page that line points to. `fluid init --quickstart` writes this header:

```yaml
# FLUID Data Product Contract
# Docs: https://agenticstiger.github.io/forge_docs/concepts/contract.html
fluidVersion: 0.7.5
kind: DataProduct
id: gold.customer.analytics_360_v1
...
```

A **Fluid Forge contract** is a YAML document that describes a data product: its identity, who owns it, how it is built, what it exposes, and who may read it. `fluid validate`, `fluid plan` and `fluid apply` read the contract and compile it for your target. You can write the document as one file, or as a root file plus fragments joined with `$ref` (see [One contract, one file or many](#one-contract-one-file-or-many)); the commands see one resolved document either way.

> **Why it matters**
> Schema, infrastructure, policy and AI gating are declared in one place, so they do not drift apart.
> `fluid validate` checks the contract against the schema before anything ships.

## The 6 required top-level fields

A contract must declare:

| Field | Purpose |
|-------|---------|
| `fluidVersion` | The version of the FLUID contract schema the file is written against. See [Which `fluidVersion` to write](#which-fluidversion-to-write). |
| `kind` | `DataProduct` or `MLPipeline`, the two values the schema allows. |
| `id` | The product identifier, dotted, for example `gold.crypto.bitcoin_tracker_v1`. Other contracts name it in `consumes[].productId`, and catalogs index it. |
| `name` | Human-readable name, shown in catalogs and dashboards. |
| `metadata` | Must contain `owner` (team and email). Optionally `layer`, `productType`, `classification`, `tags` and business context. |
| `exposes` | At least one output (table, view, file, topic). See [Builds, Exposes, Bindings](./builds-exposes-bindings.md). |

The root of the contract accepts only the keys the schema defines; any other top-level key fails `fluid validate` with `root: Additional properties are not allowed`.

## Which `fluidVersion` to write

`fluidVersion` names a version of the open FLUID specification, which is published at [open-data-protocol.github.io/fluid](https://open-data-protocol.github.io/fluid/). The `fluid` command prints the same address on its `Spec` line, and the contract schemas it validates against are served from that site, for example [`fluid-schema-0.7.5.json`](https://open-data-protocol.github.io/fluid/schema/fluid-schema-0.7.5.json).

| `fluidVersion` | Status in the CLI |
|---|---|
| `0.7.5` | Latest stable, and the default. `fluid init --quickstart` writes it. |
| `0.7.1` to `0.7.4` | Accepted. |
| `0.7.6` | **Preview.** Accepted only when the file names it. Adds the fields listed in [Builds, Exposes, Bindings](./builds-exposes-bindings.md#fields-that-need-fluidversion-0-7-6). |
| `0.4.x` to `0.6.x` | Rejected with `ERR_CONTRACT_VERSION_UNSUPPORTED`. |

`fluid version --format json` prints the same lists under `spec_versions`. A key that belongs to a newer schema fails on an older `fluidVersion`: a `consumers:` block in a `0.7.5` file is `root: Additional properties are not allowed ('consumers' was unexpected)`.

::: tip Schema vs CLI version
`fluidVersion` is the **contract schema** version. The CLI version is separate; `fluid --version` prints it. A newer CLI keeps reading contracts written for the schema versions in the table above.
:::

Which version a scaffold writes depends on the command. As measured on 0.18.1, `fluid init --quickstart` writes `0.7.5` and `fluid init --discover` writes `0.7.3`. The file is yours to change: set `fluidVersion` to the version you want to validate against.

## Minimal valid contract

```yaml
fluidVersion: "0.7.5"
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

This is a contract with no `builds[]`. Save it as `contract.fluid.yaml` and run it:

```bash
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.007s
```

`fluid apply contract.fluid.yaml --yes` does not prompt and does not ask for data. With no build to run, the local provider logs `hello_output: materialize missing source_table`, writes a placeholder file, and reports success:

```text
✅ Data product deployed successfully
```

```bash
cat runtime/out/hello.csv
```

```text
id,value
1,materialized
```

The placeholder does not have the columns the contract declares (`message`, `created_at`). Add a `builds[]` entry before you treat an applied product as real. [Builds, Exposes, Bindings](./builds-exposes-bindings.md) shows the shapes.

## One contract, one file or many

The contract is one resolved document. You can author it as a single file, or split it into a root file plus fragment files and let the CLI join them with `$ref`:

```bash
fluid split contract.fluid.yaml --dry-run
```

`fluid validate`, `fluid plan`, `fluid apply` and `fluid bundle` resolve every `$ref` before they do anything else, so the rest of the pipeline sees the same document it would see from one file. `fluid bundle` writes the resolved result. Reasons to split are ownership (governance edits `accessPolicy`, data engineering edits `builds[]`) and smaller diffs in review.

From 0.18.0 a `$ref` may only name a file inside the contract's own directory tree. [Composing a contract with `$ref`](./contract-refs.md) covers the syntax, the ref root, and how to widen it for a monorepo. The command pages are [`fluid split`](../cli/split.md) and [`fluid bundle`](../cli/bundle.md).

## Why a contract, and not separate dbt / Terraform / Airflow / OPA files?

With four separate tools, the dbt model, the Terraform that provisions the table, the Airflow DAG and the OPA policy each describe the schema or the audience on their own, and they can disagree.

A contract is the one document those pieces are generated from. When you change the schema in `exposes[].contract.schema`, the artifacts the CLI generates from it (IAM bindings, orchestration, policy, agent policy) are regenerated from that change. You do not have to remember which file to update.

## Layered structure: what goes in the contract

Paths are written from the contract root, so a block under an expose is `exposes[]...`.

| Block | What it answers | Required? |
|---|---|---|
| `fluidVersion`, `kind`, `id`, `name`, `metadata` | "What is this?" | Always |
| `exposes[]` | "What does this product produce?" (table / view / file / topic) | At least one |
| `builds[]` | "How is it computed?" (SQL / Python / dbt / acquisition) | When the product is computed; a raw expose needs none |
| `accessPolicy.grants[]` | "Who is allowed to read or write it?" | When you have human or service principals to gate |
| `exposes[].policy.agentPolicy` | "Which AI / LLM agents can use this expose, for what?" | When agents read this product |
| `exposes[].contract.dq.rules[]` | "What does 'correct' mean for this product?" (completeness, freshness, drift, valid_values) | Recommended for production |
| `exposes[].qos` | "How fresh / how available?" (availability, freshness SLO, latency, error budget) | When you publish to consumers |
| `sovereignty` | "Where can this data physically live? Under which regulations?" | When jurisdiction matters (GDPR, HIPAA, sovereignty laws) |
| `consumes[]` | "Which other products does this one read?" | When the product builds on another product |
| `lineage` | Declared upstream lineage: `granularity` (`table_level` or `field_level`) and `upstream[]` with optional `fieldMappings` | Optional |

Two placements that do not validate: `agentPolicy` and `dq` are not top-level keys. A contract with `agentPolicy:` or `dq:` at the root fails with `root: Additional properties are not allowed`. Put them under the expose they apply to; [Agent policy](./agent-policy.md) and [Quality, SLAs & Lineage](./quality-sla-lineage.md) have the examples.

You do not need every block. A local-only Bronze contract can be `fluidVersion`, `kind`, `id`, `name`, `metadata` and `exposes`. A Gold contract used by an AI team adds the policy, quality and service-level blocks.

## Versioning: the schema and the product evolve separately

The contract has its own version (`fluidVersion`), separate from the data product's version (`exposes[].version`):

- **`fluidVersion`** is the contract schema version, described [above](#which-fluidversion-to-write). It is pinned per file, so an older contract keeps validating under a newer CLI.
- **`exposes[].version`** is the data product's version, as semver. Bump it when the expose changes in a way consumers care about: `1.0.0` to `1.1.0` for an optional column, `1.0.0` to `2.0.0` for a removed or renamed one. Nothing in the CLI bumps it for you.

`fluid plan` does not compare two versions of a contract. Removing a column from `exposes[].contract.schema` without changing `exposes[].version` plans cleanly, with no warning. `fluid diff` is the command with a contract-against-contract mode:

```bash
fluid diff v2/contract.fluid.yaml --baseline v1/contract.fluid.yaml --fail-on-breaking
```

As of 0.18.1, that mode reads each expose's columns from `exposes[].schema`, which is not where a `0.7.x` contract keeps them (`exposes[].contract.schema`). Removing a column from `exposes[].contract.schema` is reported as `No changes detected` and `--fail-on-breaking` exits 0. It does report a removed or added expose, and an expose removed from the new file exits 1:

```text
BREAKING (1)
------------
  expose_removed                   exposes[1]: expose 'second' removed (downstream consumers will fail)

Summary: 1 breaking, 0 non-breaking, 0 info
```

Review column changes yourself until that is fixed. See [`fluid diff`](../cli/diff.md#contract-version-diff) for the command.

## Common patterns

### Bronze: source-aligned

The first contract you write when bringing a new data source online. `fluid init --discover <uri>` writes one contract per stream it finds. Each has an acquisition build (`pattern: acquisition`, `engine: duckdb`, with `properties.source` and `properties.sink`) and one expose. It is not a contract without builds.

A plain `fluid apply` does not run that build: the expose gets the placeholder file described above. Data lands when you run the build:

```bash
fluid apply contract.customers.fluid.yaml --mode amend-and-build
```

See [Source-Aligned Acquisition](../advanced/source-aligned-acquisition.md).

### Silver: cleaned and conformed

Adds `builds[]` (for example `engine: sql` or `engine: dbt`) that join and clean Bronze sources, and `consumes[]` entries naming those sources. Adds `exposes[].contract.dq.rules` to check the result.

### Gold: business-facing, governed

Adds `accessPolicy.grants` (RBAC), often `exposes[].policy.agentPolicy` (gate AI access), `sovereignty` (regulatory framework), and `exposes[].qos` (availability and freshness commitments). The contract is the public face of the product.

### Multi-tenant: same product, different audiences

Use multiple `exposes[]` entries on one contract, one per audience, each with its own `binding` and `policy.authz`. See [Multi-expose products](./builds-exposes-bindings.md#multi-expose-products-one-product-many-surfaces) for what happens to `builds[]` in that case.

## Where to look next

- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) - the three core blocks that turn a stub into a real product.
- [Composing a contract with `$ref`](./contract-refs.md) - write the contract as a root plus fragments.
- [Governance & Policy](./governance-policy.md) - how `accessPolicy`, `agentPolicy`, and `sovereignty` work together.
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) - how `dq.rules`, `qos`, and lineage emit artifacts.
- [Product types](../data-products/product-type.md) - `metadata.layer` and `metadata.productType`.
- [FLUID specification](https://open-data-protocol.github.io/fluid/) - the standard the contract schema comes from, with the versioned JSON Schemas.
- [Local walkthrough](/forge_docs/walkthrough/local) - build a Netflix analytics contract from scratch.
- [Validate command](/forge_docs/cli/validate) - what schema rules are checked, and what error messages mean.
