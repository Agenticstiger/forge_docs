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

## Where to look next

- [Builds, Exposes, Bindings](./builds-exposes-bindings.md) — the three core blocks that turn a stub into a real product.
- [Local walkthrough](/walkthrough/local) — build a Netflix analytics contract from scratch.
- [Validate command](/cli/validate) — what schema rules are checked, and what error messages mean.

---

::: warning This page is a stub
The full conceptual treatment (versioning policy, contract evolution, multi-tenant patterns) is tracked in [docs-content #concepts-contract](https://github.com/Agentics-Rising/forge_docs/issues?q=is%3Aopen+label%3Adocs-content). Contributions welcome.
:::
