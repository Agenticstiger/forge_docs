---
title: Governance & Policy
description: Access policy, sovereignty, and how Fluid Forge compiles to native cloud IAM.
---

# Governance & Policy

Three pieces, all declarative, all enforced before deploy:

1. **`accessPolicy.grants[]`** — who can do what (the schema's `permissions` enum supports `read`, `select`, `query`, `write`, `insert`, `update`, `delete`, `admin`, and more). Top-level field.
2. **Column-level `sensitivity`** — tag fields as `pii`, `phi`, etc. Triggers auto-masking on platforms that support it (BigQuery dynamic data masking, Snowflake masking policies).
3. **`sovereignty`** — jurisdiction + region constraints. Top-level field.

All three round-trip through `fluid policy-check` → `fluid policy-apply` (see CLI reference for the exact options each command supports).

## `accessPolicy.grants[]`

```yaml
accessPolicy:
  grants:
    - principal: "group:analysts@company.com"
      permissions: ["read"]
    - principal: "group:data-engineering@company.com"
      permissions: ["read", "write", "admin"]
    - principal: "serviceAccount:bi-tool@my-project.iam.gserviceaccount.com"
      permissions: ["read"]
```

Principal format follows cloud IAM conventions: `user:`, `group:`, `serviceAccount:`, `role:` (Snowflake).

## Column-level sensitivity

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii        # ← BigQuery dynamic masking, Snowflake masking policy
        - name: ssn
          type: STRING
          sensitivity: phi        # ← stricter masking + audit logging
```

## Sovereignty

Verified shape from `fluid-schema-0.7.2.json`:

```yaml
sovereignty:
  jurisdiction: EU                  # enum: EU, US, UK, CA, AU, JP, CN, IN, BR, Global, Multi-Region
  allowedRegions: ["europe-west3", "europe-west4"]
  deniedRegions: ["us-central1"]
  dataResidency: true
  crossBorderTransfer: false
  transferMechanisms: ["SCC"]       # array of approved transfer mechanisms
  regulatoryFramework: ["GDPR"]
  enforcementMode: strict           # enum: strict, advisory, audit
  validationRequired: true
```

Compile-time check: with `sovereignty.jurisdiction: EU` + `enforcementMode: strict`, a `binding.location.region: us-central1` is rejected by `fluid policy-check` before any cloud call is made.

## The compile pipeline

```text
contract.fluid.yaml
        │
        ▼
fluid policy-check       → Lint policies + sovereignty before deploy.
        │
        ▼
fluid policy-apply       → Map principals + permissions → native IAM.
                          (--mode is documented in `fluid policy-apply -h`.)
```

::: tip You don't have to be a cloud IAM expert
The whole point of `accessPolicy.grants` is that you write it once in human-readable form and Fluid Forge produces correct, audit-ready IAM artifacts for whichever cloud you're deploying to. No more hand-editing trust policies.
:::

## What gets emitted per cloud

`fluid policy-apply` translates the same `accessPolicy.grants` block into the cloud's native primitives:

| Cloud | Native primitive | Example |
|---|---|---|
| **GCP / BigQuery** | `IAM_BINDINGS` on the dataset (`roles/bigquery.dataViewer`, `roles/bigquery.dataEditor`) plus row-level security policies for column restrictions | `gcloud projects add-iam-policy-binding ...` |
| **AWS** | S3 bucket policies + Glue resource policies + Athena workgroup permissions | `aws s3api put-bucket-policy ...` |
| **Snowflake** | `GRANT SELECT/INSERT/...` on tables + role-based access (`ANALYST_ROLE`, etc.) + masking policies for `sensitivity: pii` columns | `GRANT SELECT ON TABLE ... TO ROLE ANALYST_ROLE` |
| **Local DuckDB** | No-op (single-user, no IAM model) — but `policy-check` still validates the grants for correctness | — |

You can inspect what would be emitted before `apply` runs with `fluid policy-apply --mode check` (the canonical pre-flight) — it returns the bindings as JSON without touching the cloud.

## Compliance frameworks

`sovereignty.regulatoryFramework` accepts an array of framework codes. Each one activates additional validation rules:

| Code | What activates |
|---|---|
| `GDPR` | Cross-border-transfer rules; DPA-required field tagging; right-to-erasure compatibility check on Bronze → Silver builds |
| `HIPAA` | `sensitivity: phi` columns must use stricter masking; audit logging mandatory; encryption-at-rest validation |
| `SOX` | Change-management trail required (every `apply` writes a signed audit record); no destructive operations without a documented `--reason` |
| `SOC2` | Activity logging on every read; service principal rotation reminders; SLA breach alerts to a designated audit principal |
| `CCPA` | Similar to GDPR for California residents; consumer-rights compatibility |

Multiple frameworks compose. A contract with `regulatoryFramework: ['GDPR', 'SOX']` activates both rule sets. Conflicts (rare) surface as `policy-check` warnings.

## Agent governance

`agentPolicy` is a separate top-level field that gates AI/LLM access at read-time. Not in the same block as `accessPolicy`, by design — human/service principals have different semantics from agents (agents have token budgets, denied use-cases, retention policies). See [Agent Policy](./agent-policy.md) for the full treatment.

```yaml
accessPolicy:
  grants:
    - principal: "group:analysts@company.com"
      permissions: ["read"]

agentPolicy:                         # ← separate, complementary
  allowedModels: ["gpt-4", "claude-3-opus"]
  deniedUseCases: ["training", "fine-tuning"]
  canStore: false
  auditRequired: true
```

A request to read this product passes only if BOTH apply: the principal is in `accessPolicy.grants` AND (when the principal is an agent) the agent's identity matches `agentPolicy.allowedModels` and the use-case is not in `deniedUseCases`.

## Audit trail

Every `apply`, `policy-apply`, and (when `auditRequired: true`) every read produces an audit record. Format:

```json
{
  "ts": "2026-04-12T14:23:01Z",
  "actor": "serviceAccount:airflow@prod.iam",
  "action": "read",
  "product": "gold.finance.customer_360_v1",
  "expose": "customer_360_table",
  "rows_returned": 12408,
  "use_case": "analysis",
  "model": "claude-3-opus",
  "audit_id": "aud_8f2c4..."
}
```

Records ship to whichever sink your platform uses by default — BigQuery audit log on GCP, CloudTrail on AWS, Snowflake's `ACCESS_HISTORY` view on Snowflake. The format is unified so cross-cloud queries work.

## Where to look next

- [Agent Policy](./agent-policy.md) — declarative LLM/agent access boundaries
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) — the rule sets `dq.rules` enforces alongside policy
- [`fluid policy-check`](/forge_docs/cli/policy-check) — pre-deploy linting
- [`fluid policy-apply`](/forge_docs/cli/policy-apply) — emit + apply IAM bindings
