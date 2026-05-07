---
title: "Recipe — add a quality rule"
description: Block deploys when a column has nulls, stale data, or fails any of the 8 supported rule types.
---

# Recipe: add a quality rule

**Time:** 2 minutes · **Audience:** anyone with an existing contract

## Problem

You have a working contract but no enforcement against silent data issues — null `customer_id`, stale freshness, duplicate primary keys.

## Solution

Add a `dq.rules` block under the `expose.contract`. Each rule has 5 keys; the four below cover ~80 % of real-world cases.

## Add this to `exposes[].contract`

```yaml
exposes:
  - exposeId: customer_orders
    contract:
      schema:
        - name: order_id
          type: STRING
          required: true
        - name: customer_id
          type: STRING
          required: true
        - name: total
          type: NUMERIC
          required: true
        - name: order_ts
          type: TIMESTAMP
          required: true

      dq:
        rules:
          # 1. Block deploys with null customer_id (any null = error)
          - id: customer_id_complete
            type: completeness
            selector: customer_id
            threshold: 1.0
            operator: ">="
            severity: error

          # 2. Block on duplicate order_id (must be unique)
          - id: order_id_unique
            type: uniqueness
            selector: order_id
            threshold: 1.0
            operator: ">="
            severity: error

          # 3. Warn (don't block) if data is more than 1 hour old
          - id: orders_freshness
            type: freshness
            window: PT1H
            severity: warn

          # 4. Block if total has any negative values
          - id: total_positive
            type: valid_values
            selector: total
            threshold: 1.0
            operator: ">="
            severity: error
```

## Test it

```bash
fluid validate contract.fluid.yaml      # ← passes if rule syntax is well-formed
fluid test contract.fluid.yaml          # ← runs the rules against live data
fluid apply contract.fluid.yaml --yes   # ← aborts on any rule with severity: error
```

## Severity levels

| Severity | Behavior |
|----------|----------|
| `error` | `fluid apply` aborts. Hard guarantee. |
| `warn` | Deploy proceeds; warning emitted to stdout + test report. |
| `info` | Recorded only. Useful for tracking metrics over time. |

## See also

- All 8 rule types: [Concepts → Quality, SLAs & Lineage](/concepts/quality-sla-lineage.html#data-quality-rules-dq-rules)
- Live data testing: [`fluid test --output json`](/cli/)
