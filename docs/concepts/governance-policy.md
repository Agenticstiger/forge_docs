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

---

::: warning This page is a stub
Full coverage of compliance frameworks (SOC 2, HIPAA, GDPR), the audit-log emission format, and integration with corporate IdP groups is tracked in [docs-content #concepts-governance](https://github.com/Agentics-Rising/forge_docs/issues?q=is%3Aopen+label%3Adocs-content).
:::
