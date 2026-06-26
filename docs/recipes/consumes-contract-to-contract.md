---
title: Write a contract that consumes another contract
description: Wire a downstream data product to an upstream one using consumes[].
---

# Consume one contract from another

**Time:** 2 min · **Skill:** familiarity with the contract YAML shape

A Gold (CDP) or Silver (ADP) data product almost always builds on upstream products rather than raw sources. The `consumes[]` block on the downstream contract names the upstream by ID and lets the planner resolve the bindings — your contract never re-types schemas or transformation logic that already lives in the upstream.

## The pattern

Two contracts in the same workspace: an upstream `bronze.crm_orders` (already running) and a new downstream `silver.orders_enriched` that joins it with `bronze.crm_customers`.

### Upstream — `bronze.crm_orders.fluid.yaml` (already exists)

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.crm_orders
metadata:
  layer: Bronze
  productType: SDP
exposes:
  - name: orders
    schema:
      - { name: order_id,   type: string }
      - { name: customer_id, type: string }
      - { name: amount_cents, type: int64 }
      - { name: created_at, type: timestamp }
```

### Downstream — `silver.orders_enriched.fluid.yaml` (new)

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.orders_enriched
metadata:
  layer: Silver
  productType: ADP

consumes:
  - product: bronze.crm_orders
    expose: orders
    alias: orders
  - product: bronze.crm_customers
    expose: customers
    alias: customers

builds:
  - name: enrich
    engine: sql
    sql: |
      SELECT
        o.order_id,
        o.amount_cents,
        c.region,
        c.segment
      FROM {{ orders }} o
      LEFT JOIN {{ customers }} c USING (customer_id)

exposes:
  - name: orders_enriched
    schema:
      - { name: order_id, type: string }
      - { name: amount_cents, type: int64 }
      - { name: region, type: string }
      - { name: segment, type: string }
```

Run it:

```bash
fluid validate silver.orders_enriched.fluid.yaml
fluid plan     silver.orders_enriched.fluid.yaml
fluid apply    silver.orders_enriched.fluid.yaml --yes
```

## What the planner does

- Resolves each `consumes[].product` against the workspace registry (loads the upstream contract).
- Checks the named `expose` exists and validates the projected schema against the SQL template's `{{ alias }}` placeholders.
- **Refuses ADP / CDP contracts from depending on a non-existent product.** No "broken pointer" gets past `fluid plan`.
- **Refuses SDP (Bronze / source-aligned) products from declaring `consumes[]`.** SDPs are leaves. See [Product Types → Composition rules](/forge_docs/data-products/product-type.html#composition-rules).
- Wires the bindings so the build runs in dependency order, no matter what order you put the contracts on the CLI.

## Forge a downstream contract that already wires `consumes`

If you'd rather not author the YAML by hand, `fluid forge --from-product` pre-fills the `consumes[]` block from an existing product:

```bash
fluid forge --from-product bronze.crm_orders --from-product bronze.crm_customers
```

The picker runs the same composition-rule validation up-front, so you can't pre-fill a structurally invalid downstream.

## See also

- [Product Types → Composition rules](/forge_docs/data-products/product-type.html#composition-rules) — what can consume what
- [`fluid forge --from-product`](../cli/forge.md#--from-product--composition) — pre-fill `consumes[]` from existing products
- [Builds, Exposes, Bindings](../concepts/builds-exposes-bindings.md) — the canonical contract surface
