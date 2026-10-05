# Walkthrough: Snowflake Team Collaboration

**Time:** 15 minutes | **Difficulty:** Intermediate | **Prerequisites:** Snowflake account, Python 3.10+, git

<CliCast
  src="/forge_docs/demos/snowflake-real.svg"
  title="validate → plan → apply --mode dry-run → policy-apply --mode check"
  caption="The flow at full fidelity: live env credentials sourced, validate --strict, plan against the live account, apply --mode dry-run rendering DDL without firing it, and policy-apply --mode check over the compiled bindings. No DDL fires, no RBAC mutates — exactly what you'd run in a PR review before approving the merge. (As of 0.18.1 policy-apply has no Snowflake applier; see Step 4.)"
  width="920"
  insight="The PR pre-flight you wish you had — every reviewer sees the deployed-state diff before merge, not after. | DDL rendered, RBAC bindings dry-checked, drift detected — zero side effects on the live account. | Drop this 4-command chain into your PR-merge GitHub Action and incidents shift left of merge."
/>

---

## Overview

This walkthrough shows how three engineers collaborate on one Fluid Forge project from first draft to approved pull request:

- one repo
- one `contract.fluid.yaml`
- one reviewable `fluid plan`
- one PR that everybody can reason about

The scenario is a Snowflake BI/reporting data product called `customer_orders_weekly_revenue`. The team wants a clean analytics mart for finance dashboards without exposing unnecessary PII.

If you want the first successful Snowflake deployment rather than the review workflow, start with the [Snowflake quickstart](/forge_docs/getting-started/snowflake). This walkthrough assumes the team already has Snowflake access and is reviewing a contract in a normal PR process.

For shared environments, assume the team is using explicit environment-specific warehouse, database, schema, and role settings, plus secure authentication for automation. In practice that means key-pair or OAuth in CI, with browser SSO reserved for interactive local work.

### Roles

- **Data engineer** uses `fluid forge` to scaffold the first draft from local SQL, sample data, and a short README.
- **Platform engineer** reviews Snowflake-specific deployment choices, RBAC, retention, and policy outputs.
- **Reviewer** signs off on the business shape and the deployment impact using the contract diff plus plan output.

::: warning Syntax note
This walkthrough now treats `fluid forge` as the public entry point. Older `fluid forge --mode copilot` examples are historical only.
:::

---

## Step 1: Starting Repo

Assume the repo already contains a few useful artifacts before anyone writes a FLUID contract:

```text
customer-orders/
├── data/
│   ├── raw_orders.parquet
│   └── customers.csv
├── sql/
│   └── weekly_revenue.sql
└── README.md
```

Those files are enough for `fluid forge` to infer table names, column types, Snowflake hints, and business vocabulary before generation.

---

## Step 2: Data Engineer Drafts The Project

The data engineer starts with discovery-enabled `fluid forge`:

```bash
fluid forge \
  --provider snowflake \
  --discovery-path ./data \
  --llm-provider openai \
  --llm-model gpt-4.1-mini

fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
```

### What Copilot Contributes

- reads metadata from `raw_orders.parquet`, `customers.csv`, `weekly_revenue.sql`, and `README.md`
- scaffolds the first `contract.fluid.yaml`
- gives the data engineer a contract they can refine before opening a PR

The important handoff is not the chat transcript. It is the validated contract plus the generated plan.

---

## Step 3: Mock PR Opened By The Data Engineer

### PR Title

```text
feat: add Snowflake weekly revenue data product
```

### PR Body

```md
This PR adds the first FLUID contract for the Snowflake weekly revenue mart used by finance reporting.

I used `fluid forge` with local discovery against the repo's SQL and sample data, then tightened the generated contract by hand.

Changes in this PR:
- add `contract.fluid.yaml`
- target the Snowflake provider for the first deployment
- add Snowflake RBAC grants for analytics readers and engineering writers
- expose weekly revenue metrics for downstream BI dashboards

Commands run:
- `fluid validate contract.fluid.yaml`
- `fluid plan contract.fluid.yaml --out runtime/plan.json`

Main review asks:
- should `customer_email` remain in the exposed table if it is masked? (The contract marks it `sensitivity: pii`, which is what flags this column for review.)
- are `ANALYTICS` and `SHARED_MARTS` acceptable defaults for the first rollout?
- is the warehouse sizing reasonable for this build?

The CI version of this review flow should run with key-pair or OAuth credentials rather than password auth, and it should fail on `validate`, `plan`, or `verify --strict` drift before merge.
```

### Sample Contract Excerpt In The PR

This is the kind of first draft the data engineer might propose. It declares `fluidVersion: "0.7.5"`, the latest stable schema:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: finance.customer_orders_weekly_revenue
name: Customer Orders Weekly Revenue
description: Weekly customer revenue mart for finance dashboards in Snowflake.
domain: finance

metadata:
  layer: Gold
  owner:
    team: revenue-analytics
    email: revenue-analytics@example.com

accessPolicy:
  grants:
    - principal: "role:FINANCE_ANALYST"
      permissions: [read, select, query]
    - principal: "role:ANALYST_READWRITE"
      permissions: [read, select, insert, update]
    - principal: "role:DATA_ENGINEER"
      permissions: [read, select, insert, update, delete, create]

builds:
  - id: weekly_revenue
    description: Aggregate customer orders into a weekly Snowflake mart
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          DATE_TRUNC('WEEK', order_ts) AS revenue_week,
          SUM(order_amount) AS weekly_revenue,
          ANY_VALUE(customer_email) AS customer_email
        FROM raw_orders
        GROUP BY 1, 2
    execution:
      runtime:
        platform: snowflake
        resources:
          warehouse: "ANALYTICS_WH"
          warehouse_size: "MEDIUM"
    outputs:
      - weekly_revenue_table

exposes:
  - exposeId: weekly_revenue_table
    kind: table
    title: Weekly Revenue Mart
    version: "1.0.0"
    binding:
      platform: snowflake
      format: snowflake_table
      location:
        account: "{{ env.SNOWFLAKE_ACCOUNT }}"
        database: "ANALYTICS"
        schema: "SHARED_MARTS"
        table: "CUSTOMER_ORDERS_WEEKLY_REVENUE"
      properties:
        cluster_by: ["revenue_week", "customer_id"]
        table_type: "STANDARD"
        data_retention_time_in_days: 7
        change_tracking: true
    policy:
      classification: Internal
      authn: custom
      authz:
        readers:
          - role:FINANCE_ANALYST
          - role:ANALYST_READWRITE
        writers:
          - role:DATA_ENGINEER
      privacy:
        masking:
          - column: "customer_email"
            strategy: "hash"
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: revenue_week
          type: DATE
          required: true
        - name: weekly_revenue
          type: NUMBER(18,2)
          required: true
        - name: customer_email
          type: STRING
          required: false
          sensitivity: pii
```

This draft is good enough to start a review, but it still contains exactly the kind of issues a team review should catch. It passes the schema:

```text
✅ Valid FLUID contract (schema v0.7.5)
```

and `fluid plan contract.fluid.yaml --out runtime/plan.json` lists two actions:

```text
Contract: Customer Orders Weekly Revenue
Version: 0.7.5
Total Actions: 2

1. provision_weekly_revenue_table (provisionDataset)
2. schedule_weekly_revenue (scheduleTask)
```

---

## Step 4: Platform Engineer Reviews The Snowflake Details

The platform engineer pulls the branch and runs the standard checks:

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
fluid policy-check contract.fluid.yaml
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
```

`fluid policy-check` passes the draft with one advisory, which points at the `customer_email` column:

```text
💡 🔄 Lifecycle Management (ADVISORY)
└── ⚠️ WARNING (1)
    └── Sensitive data should have explicit retention policy
        ├── 📍 weekly_revenue_table
        └── 💡 Remediation: Add lifecycle.retention (e.g., 'P90D' for 90 days)
```

`fluid policy-compile` writes `runtime/policy/bindings.json`, one binding per principal. For the draft it contains:

| Principal | Compiled grants |
| --- | --- |
| `role:FINANCE_ANALYST` | `SELECT` |
| `role:ANALYST_READWRITE` | `INSERT`, `UPDATE`, `DELETE`, `SELECT` |
| `role:DATA_ENGINEER` | `INSERT`, `UPDATE`, `DELETE`, `SELECT` |

::: warning Compiled bindings are not applied to Snowflake in 0.18.1
`fluid policy-compile` produces the file the platform engineer reviews. Neither `fluid policy-apply` nor `fluid apply` turns `accessPolicy.grants` into Snowflake grants as of 0.18.1: `fluid policy-apply runtime/policy/bindings.json --mode check` prints `No policy bindings were enforced — the 'snowflake' provider has no standalone policy applier`, and the OpenTofu module `fluid apply` writes for this contract holds a database, a schema and the table, with no grant resources. Apply the grants your review approved through your own Snowflake RBAC process.
:::

### What The Platform Engineer Checks

- **Warehouse sizing:** is `ANALYTICS_WH` at `MEDIUM` justified for a weekly aggregate?
- **Database and schema naming:** should `ANALYTICS.SHARED_MARTS` be environment-specific instead of hard-coded?
- **RBAC scope:** are analyst roles limited to read access, with writes reserved for engineering roles?
- **Retention and Time Travel:** is `data_retention_time_in_days: 7` correct for the team's cost and recovery requirements?
- **Change tracking:** is `change_tracking: true` needed for downstream CDC or can it be disabled?

### Exact PR Comments From The Platform Engineer

> Please do not hard-code `ANALYTICS` and `SHARED_MARTS` in the contract. We deploy separate Snowflake databases and schemas per environment, so this needs `{{ env.SNOWFLAKE_DATABASE }}` and `{{ env.SNOWFLAKE_SCHEMA }}` before merge.

> `customer_email` should not be exposed in this mart. The finance dashboard only needs weekly revenue by `customer_id`, so please remove the column from the exposed table instead of relying on masking. The `privacy.masking` block does not create a Snowflake masking policy: the module `fluid apply` writes for this draft has no masking resource, so the column would be exposed in the clear.

> `role:ANALYST_READWRITE` is broader than we allow for analytics marts. Please narrow analyst access to read-only and keep write permissions with `role:DATA_ENGINEER`.

> `ANALYTICS_WH` at `MEDIUM` looks oversized for a weekly aggregate. Please either justify it in the PR or reduce to the smallest warehouse that comfortably handles the build.

---

## Step 5: Reviewer Focuses On Plan Visibility

The reviewer does not need to reconstruct the project from scratch. They just need the contract diff and the deployment preview.

### Reviewer Commands

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
```

### Exact Reviewer Comment

> Please paste the relevant `fluid plan` summary into the PR description. I can review the YAML, but I also want to see the Snowflake objects and RBAC changes this PR will create before I approve it.

That comment is important because plan visibility is what turns the PR from "here is some YAML" into "here is the actual infrastructure and policy impact."

---

## Step 6: Data Engineer Revises The Contract

The data engineer addresses the review in one place: the contract.

### Revised Commands

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
fluid policy-check contract.fluid.yaml
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
```

With the revisions below, `fluid policy-check` reports no advisory (`Compliance Score: 100/100`), and `bindings.json` holds three bindings:

| Principal | Compiled grants |
| --- | --- |
| `role:FINANCE_ANALYST` | `SELECT` |
| `role:BI_READER` | `SELECT` |
| `role:DATA_ENGINEER` | `INSERT`, `UPDATE`, `DELETE`, `SELECT` |

`create` in `DATA_ENGINEER`'s permission list does not compile to a grant. The `{{ env.SNOWFLAKE_DATABASE }}` and `{{ env.SNOWFLAKE_SCHEMA }}` placeholders stay as written in each binding's `resource_id`; they are resolved when `fluid apply` runs.

### Revised Contract Excerpt

After review, the contract becomes safer and more portable:

```yaml
accessPolicy:
  grants:
    - principal: "role:FINANCE_ANALYST"
      permissions: [read, select, query]
    - principal: "role:BI_READER"
      permissions: [read, select]
    - principal: "role:DATA_ENGINEER"
      permissions: [read, select, insert, update, delete, create]

builds:
  - id: weekly_revenue
    description: Aggregate customer orders into a weekly Snowflake mart
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT
          customer_id,
          DATE_TRUNC('WEEK', order_ts) AS revenue_week,
          SUM(order_amount) AS weekly_revenue
        FROM raw_orders
        GROUP BY 1, 2
    execution:
      runtime:
        platform: snowflake
        resources:
          warehouse: "ANALYTICS_WH"
          warehouse_size: "SMALL"

exposes:
  - exposeId: weekly_revenue_table
    binding:
      platform: snowflake
      format: snowflake_table
      location:
        account: "{{ env.SNOWFLAKE_ACCOUNT }}"
        database: "{{ env.SNOWFLAKE_DATABASE }}"
        schema: "{{ env.SNOWFLAKE_SCHEMA }}"
        table: "CUSTOMER_ORDERS_WEEKLY_REVENUE"
      properties:
        cluster_by: ["revenue_week", "customer_id"]
        table_type: "STANDARD"
        data_retention_time_in_days: 7
        change_tracking: false
    policy:
      classification: Internal
      authn: custom
      authz:
        readers:
          - role:FINANCE_ANALYST
          - role:BI_READER
        writers:
          - role:DATA_ENGINEER
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: revenue_week
          type: DATE
          required: true
        - name: weekly_revenue
          type: NUMBER(18,2)
          required: true
```

### Data Engineer Reply In The PR

> Updated. I removed `customer_email` from the exposed mart, parameterized the Snowflake database and schema with environment variables, narrowed analyst grants to read-only roles, reduced the warehouse size to `SMALL`, and disabled change tracking because nothing downstream needs CDC yet.
>
> I also reran:
> - `fluid validate contract.fluid.yaml`
> - `fluid plan contract.fluid.yaml --out runtime/plan.json`
> - `fluid policy-check contract.fluid.yaml`
> - `fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json`
>
> Updated plan summary for review:
> - ensure Snowflake table `{{ env.SNOWFLAKE_DATABASE }}.{{ env.SNOWFLAKE_SCHEMA }}.CUSTOMER_ORDERS_WEEKLY_REVENUE`
> - compiled bindings: `SELECT` for `role:FINANCE_ANALYST` and `role:BI_READER`, write grants for `role:DATA_ENGINEER` only (the grants themselves are applied through our Snowflake RBAC process, not by `fluid apply`)

---

## Step 7: Final Approval

### Exact Reviewer Approval Comment

> Approved. The revised contract keeps PII out of the exposed mart, the Snowflake location is environment-safe, and the PR now includes the deployment impact I needed to review.

At this point the team can merge and continue with the standard execution flow. Preview what the Snowflake provider will create first, then apply:

```bash
fluid apply contract.fluid.yaml --dry-run
fluid apply contract.fluid.yaml --yes
```

`--dry-run` writes the OpenTofu module for Snowflake and runs `tofu plan` with the account's credentials. The module for this contract creates the database, the schema and the table, per the `location` block.

---

## Why This Works Well In Fluid Forge

In general, Fluid Forge helps collaboration because everybody reviews the same source of truth: the contract plus the plan generated from it. The data engineer does not hand off scattered SQL, ad hoc Snowflake setup notes, and separate RBAC requests. They hand off one contract that platform and reviewers can validate, plan, and discuss.

Copilot mode shortens the first-draft cycle even more. Instead of starting from a blank YAML file, the data engineer starts from a scaffold grounded in local SQL, sample data, and repo conventions. That means the team spends less time writing boilerplate and more time reviewing the parts that actually matter: schema design, Snowflake bindings, RBAC, and PII exposure.

---

## See Also

- [Snowflake Provider](/forge_docs/providers/snowflake) - Snowflake deployment reference
- [Universal Pipeline](/forge_docs/walkthrough/universal-pipeline) - Same CI/CD flow across GCP, AWS, and Snowflake
- [CLI Reference](/forge_docs/cli/) - Full command reference for `validate`, `plan`, `apply`, and policy commands
