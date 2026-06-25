---
title: "Recipe — tag PII in your schema"
description: Get column-level masking on BigQuery / Snowflake without writing IAM JSON yourself.
---

# Recipe: tag PII in your schema

**Time:** 2 minutes · **Audience:** anyone shipping a contract with personally identifiable data

## Problem

Your data product contains `email`, `ssn`, `phone_number`, or other PII. You need:
1. The fields tagged so analysts know they're sensitive.
2. Native cloud masking (BigQuery dynamic data masking / Snowflake masking policies) applied automatically.
3. AI/LLM agents blocked from reading those columns.

## Solution

Three small additions to the contract.

## 1. Tag the column with `sensitivity: pii`

```yaml
exposes:
  - exposeId: customers
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: name
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii          # ← marks as PII
        - name: phone_number
          type: STRING
          sensitivity: pii
        - name: ssn
          type: STRING
          sensitivity: phi          # PHI = stricter than PII (HIPAA-class)
```

The schema field `sensitivity` is recognized by every provider that supports column masking (today: BigQuery, Snowflake — AWS Glue lineage tags coming).

## 2. Make it explicit at the access-policy layer

```yaml
accessPolicy:
  grants:
    - principal: "group:analysts@company.com"
      permissions: ["read"]                 # gets masked PII (asterisks for email/phone, full for everything else)
    - principal: "group:fraud-team@company.com"
      permissions: ["read", "select"]       # cleared role; sees PII unmasked (verified by audit log)
```

The actual unmasking-vs-masking behavior is determined by the platform's masking policies; `fluid policy apply` deploys the policy attached to each principal.

## 3. Block AI agents from reading PII

```yaml
agentPolicy:
  allowedModels: ["claude-3-opus"]
  allowedUseCases: ["analysis", "summarization"]
  deniedUseCases: ["training"]
  auditRequired: true
```

The combination of `sensitivity: pii` on columns + `agentPolicy` at the contract root tells the governance pipeline to mask PII columns from any read where the principal is tagged as an agent.

## Verify before deploying

```bash
fluid policy-check contract.fluid.yaml                                  # validates the policy block
fluid plan contract.fluid.yaml                                          # shows which masks/grants will be applied
fluid policy compile contract.fluid.yaml --out runtime/policy/bindings.json  # contract → provider bindings
fluid policy apply runtime/policy/bindings.json                         # deploy the compiled IAM (dry-run; add --mode enforce)
```

## See also

- [Concepts → Governance & Policy](/forge_docs/concepts/governance-policy.html) — full sovereignty + accessPolicy schema.
- [Concepts → Agent Policy](/forge_docs/concepts/agent-policy.html) — every `agentPolicy` field.
