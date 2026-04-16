# FLUID Forge Contract GPT Few-Shot Pack

These examples teach the GPT how to ask, draft, and review without inventing governance.

## Strong Example 1: Local Draft

User:

`Generate a FLUID 0.7.2 contract for a local pipeline that reads examples/orders.csv, keeps order_id, customer_id, order_date, and amount, filters out null customer_id values, and writes runtime/out/orders-clean-v1.csv.`

Assistant:

```text
Draft status: Draft
```

```yaml
fluidVersion: "0.7.2"
kind: "DataProduct"
id: "bronze.sales.orders_clean_v1"
name: "Orders Clean"
description: "Local cleanup of raw orders into a validated CSV output."
domain: "sales"
metadata:
  layer: "Bronze"
  owner:
    team: "sales-data"
    email: "sales-data@example.com"
builds:
  - id: "clean_orders"
    pattern: "embedded-logic"
    engine: "sql"
    properties:
      sql: |
        SELECT
          order_id,
          customer_id,
          order_date,
          amount
        FROM orders_raw
        WHERE customer_id IS NOT NULL
exposes:
  - exposeId: "orders_clean"
    kind: "table"
    binding:
      platform: "local"
      format: "csv"
      location:
        path: "runtime/out/orders-clean-v1.csv"
    contract:
      schema:
        - name: "order_id"
          type: "string"
          required: true
        - name: "customer_id"
          type: "string"
          required: true
        - name: "order_date"
          type: "date"
        - name: "amount"
          type: "number"
```

Assumptions:

- Input alias `orders_raw` will be wired by the implementer
- No governance or sovereignty constraints were provided

Open questions:

- Should this remain local-only, or should it target a cloud provider later

Validation next steps:

- `fluid validate contract.fluid.yaml --strict`
- `fluid plan contract.fluid.yaml --provider local --json`

## Strong Example 2: GCP Governed Draft With Semantics

User:

`Generate a GCP FLUID 0.7.2 contract for a customer metrics table in project customer-prod, dataset gold_customer, table customer_metrics_v1. Keep data in EU only, classify it Confidential, allow AI only for analysis and qa, never for training, and add semantic definitions for customer_count and monthly_revenue.`

Assistant:

```text
Draft status: Draft
```

```yaml
fluidVersion: "0.7.2"
kind: "DataProduct"
id: "gold.customer.customer_metrics_v1"
name: "Customer Metrics"
description: "Governed customer metrics table for analytics and support use."
domain: "customer"
metadata:
  layer: "Gold"
  owner:
    team: "customer-analytics"
    email: "customer-analytics@example.com"
sovereignty:
  jurisdiction: "EU"
  allowedRegions:
    - "europe-west1"
    - "europe-west4"
  dataResidency: true
  crossBorderTransfer: false
  regulatoryFramework:
    - "GDPR"
  enforcementMode: "strict"
  validationRequired: true
exposes:
  - exposeId: "customer_metrics"
    kind: "table"
    binding:
      platform: "gcp"
      format: "bigquery_table"
      location:
        project: "customer-prod"
        dataset: "gold_customer"
        table: "customer_metrics_v1"
    contract:
      schema:
        - name: "customer_id"
          type: "STRING"
          required: true
        - name: "metric_month"
          type: "DATE"
          required: true
        - name: "monthly_revenue"
          type: "NUMERIC"
        - name: "segment"
          type: "STRING"
      dq:
        rules:
          - id: "customer_id_not_null"
            type: "completeness"
            selector: "customer_id"
            threshold: 1.0
            operator: ">="
            severity: "error"
    policy:
      classification: "Confidential"
      agentPolicy:
        allowedUseCases:
          - "analysis"
          - "qa"
        deniedUseCases:
          - "training"
          - "fine_tuning"
        canStore: false
        canReason: true
        auditRequired: true
        retentionPolicy:
          maxRetentionDays: 0
          requireDeletion: true
        purposeLimitation: "Internal analytics and support use only"
    semantics:
      name: "customer_metrics"
      description: "Customer revenue and count metrics for internal analytics."
      defaultAggTimeDimension: "metric_month"
      entities:
        - name: "customer"
          type: "primary"
          expr: "customer_id"
      measures:
        - name: "monthly_revenue"
          agg: "sum"
          expr: "monthly_revenue"
        - name: "customer_count"
          agg: "count_distinct"
          expr: "customer_id"
          createMetric: true
      dimensions:
        - name: "metric_month"
          type: "time"
          typeParams:
            timeGranularity: "month"
        - name: "segment"
          type: "categorical"
      metrics:
        - name: "monthly_revenue"
          type: "simple"
          measure: "monthly_revenue"
          owner: "customer-analytics@example.com"
```

Assumptions:

- EU residency implies BigQuery resources should resolve to EU-approved regions

Open questions:

- Which exact BigQuery region should be used for deployment

Validation next steps:

- `fluid validate contract.fluid.yaml --strict`
- `fluid plan contract.fluid.yaml --provider gcp --json`

## Strong Example 3: Review Before Rewrite

User:

`Review this contract and tell me what will fail validation:`  
`binding.provider: gcp`  
`schema:`  
`  customer_id: STRING`

Assistant:

- `FAIL`: `binding.provider` should be `binding.platform`
- `FAIL`: tabular exposes should use `contract.schema` as an array of columns
- `FAIL`: the contract is missing required top-level fields such as `fluidVersion`, `kind`, `id`, `name`, `metadata`, and `exposes`
- `QUESTION`: no project, dataset, or table details were provided for the GCP binding

Corrected minimal pattern:

```yaml
fluidVersion: "0.7.2"
kind: "DataProduct"
id: "gold.customer.sample_v1"
name: "Customer Sample"
metadata:
  layer: "Gold"
  owner:
    team: "customer-data"
    email: "customer-data@example.com"
exposes:
  - exposeId: "customer_sample"
    kind: "table"
    binding:
      platform: "gcp"
      format: "bigquery_table"
      location:
        project: "REPLACE_ME"
        dataset: "REPLACE_ME"
        table: "REPLACE_ME"
    contract:
      schema:
        - name: "customer_id"
          type: "STRING"
          required: true
```

## Bad Draft To Corrected Draft Pair 1

Bad draft:

```yaml
binding:
  provider: gcp
schema:
  order_id: STRING
```

Corrected draft:

```yaml
binding:
  platform: gcp
  format: bigquery_table
  location:
    project: REPLACE_ME
    dataset: REPLACE_ME
    table: REPLACE_ME
contract:
  schema:
    - name: order_id
      type: STRING
      required: true
```

Reason:

- Use `binding.platform`
- Keep schema under `contract.schema`
- Make provider-specific location fields explicit

## Bad Draft To Corrected Draft Pair 2

Bad draft behavior:

- Added `GDPR`, `HIPAA`, IAM roles, and 7-year retention even though the user never mentioned regulation, privacy class, or access rules

Corrected behavior:

- Omit those fields from YAML
- Put them under `Open questions`

Example correction:

```text
Open questions
- Do you need any regulatory framework declared, such as GDPR or HIPAA
- Should this expose include privacy controls or AI usage restrictions
- Which principals or teams should receive access
```
