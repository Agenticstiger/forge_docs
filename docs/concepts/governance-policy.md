---
title: Governance & Policy
description: Access grants, column restrictions, masking, sovereignty and agent policy, which command enforces each one, and what each becomes on AWS, GCP and Snowflake.
---

# Governance & Policy

A contract declares its governance in fields that name no cloud: who may read it, which columns some readers may not see, which values must be treated before they land, where the data may live, and which AI models may read it. This page shows each field, then says which command enforces it and what it becomes on each platform.

> **Why it matters**
> A policy only protects data if something enforces it. Several of these fields are enforced natively on one cloud and not read at all on another. The [per-cloud table](#what-gets-emitted-per-cloud) below says which is which, so you can tell a control from a declaration.

## A governed expose

```yaml
fluidVersion: 0.7.5
# ... id, name, domain, metadata ...
accessPolicy:
  grants:
    - principal: group:analysts@northwind.com
      permissions: [read]
    - principal: group:stewards@northwind.com
      permissions: [read]
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: northwind-prod
        dataset: crm
        table: customers
        region: europe-west1
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@northwind.com
            columns: [email]
            access: deny
      privacy:
        masking:
          - column: email
            strategy: hash
            params: {saltEnv: FLUID_PII_HASH_SECRET}
    contract:
      schema:
        - name: customer_id
          type: STRING
        - name: email
          type: STRING
          sensitivity: pii
```

`fluid generate iac` on this contract writes seven OpenTofu resources on 0.18.1: the dataset and table, a `google_bigquery_dataset_iam_member` per reader, a Data Catalog taxonomy with fine-grained access control, a policy tag on `email`, and `roles/datacatalog.categoryFineGrainedReader` on that tag for `group:stewards@northwind.com` only. The analysts can query the table and get an access error on `email`.

## Which command does what

| Command | What it does with governance | Touches the cloud? |
|---|---|---|
| `fluid validate` | Schema checks, the [sovereignty](./sovereignty.md) gate, and refusals of policies a binding cannot apply (see below) | No |
| `fluid policy-check` | Lints sensitivity, access control, data quality, lifecycle and schema evolution. A column tagged `pii` or `phi` with no `policy.privacy.masking` entry is a critical finding, and the command exits 1 | No |
| `fluid generate iac` / `fluid apply` | Emit (and, for `apply`, provision) the native resources in the [per-cloud table](#what-gets-emitted-per-cloud). On AWS and GCP they also refuse an out-of-policy region | `apply` only |
| `fluid verify` | Checks the live platform against what apply derived: column restrictions, and on 0.7.6 retention and encryption; masked columns hold treated values | Reads only |
| `fluid policy-compile` | Writes `accessPolicy.grants` as provider-shaped bindings JSON, for review | No |
| `fluid policy-apply` | Enforces nothing on any provider as of 0.18.1 (see [below](#fluid-policy-apply-enforces-nothing)) | No |

## `accessPolicy.grants[]`

```yaml
accessPolicy:
  grants:
    - principal: group:analysts@northwind.com
      permissions: [read]
    - principal: group:data-eng@northwind.com
      permissions: [read, write]
    - principal: serviceAccount:bi-tool@northwind-prod.iam.gserviceaccount.com
      permissions: [read]
```

`accessPolicy` is a top-level field. The `permissions` enum is `read`, `select`, `query`, `write`, `insert`, `update`, `delete`, `create`, `admin` and `manage`. Write principals in the target cloud's IAM member form: `user:`, `group:`, `serviceAccount:` on GCP. On AWS, column restrictions need IAM ARNs (or a [`binding.principals`](#one-contract-two-clouds-binding-principals) mapping to them).

On a GCP binding, `fluid validate` refuses a placeholder principal in any `fluidVersion`: a reserved top-level domain (`.example`, `.test`, `.invalid`, `.localhost`), or a value that is not an IAM member at all (`group:data-platform` with no domain, a bare `analysts`, an unknown prefix such as `role:analyst`, an unfilled `<<YOUR_PROJECT_HERE>>`):

```bash
fluid validate contract.fluid.yaml
#  1. exposes accessPolicy: principal 'group:analysts@northwind.example' resolves
#  to 'group:analysts@northwind.example', a placeholder: .example is a reserved
#  top-level domain (RFC 2606), so no real identity has it, and BigQuery refuses an
#  access entry for an identity that does not exist. Map the logical principal in
#  this environment's binding.principals to the real group or service account it
#  stands for, ...
# exit 1
```

The message suggests `binding.principals`, which exists only in fluid-schema 0.7.6 (preview). On a 0.7.5 contract, either write the real identity (a real domain; `example.com` is accepted), or move the contract to `fluidVersion: "0.7.6"` and map it as shown [below](#one-contract-two-clouds-binding-principals). Adding `binding.principals` to a 0.7.5 contract fails with `Additional properties are not allowed ('principals' was unexpected)`.

## Column restrictions: `policy.authz.columnRestrictions`

```yaml
exposes:
  - exposeId: customers
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@northwind.com
            columns: [email]
            access: deny          # deny | allow
```

The field is in fluid-schema 0.7.5, and `fluid apply` enforces it at 0.7.5:

- A column named in any restriction is restricted. `deny` keeps the named principal off those columns; `allow` makes them readable only by the principals an `allow` names.
- A deny beats an allow, and a restriction never grants access. The readers are the expose's readers: on GCP the `accessPolicy` read grantees plus the expose's `policy.authz.readers`, on AWS the Lake Formation `SELECT` grantees.
- A restriction on an expose with no reader is refused: on GCP as `column-restriction-no-readers`, on AWS when the binding has no Lake Formation grants (`column-restriction-unenforceable`). A policy tag with no reader would lock the columns for everyone.

On AWS, `fluid validate` refuses the restriction when the binding declares no Lake Formation grants:

```bash
fluid validate contract.fluid.yaml
#  1. exposes.policy.authz.columnRestrictions restricts columns, but this aws
#  binding declares no governance.lakeFormation.grants, the only column-level
#  control the AWS emitter writes. Nothing would enforce the restriction. ...
# exit 1
```

On GCP a denied principal gets an access error on the restricted columns, and `SELECT * EXCEPT (email)` still works for it.

## Masking: `policy.privacy.masking`

```yaml
policy:
  privacy:
    masking:
      - column: email
        strategy: hash
        params: {saltEnv: FLUID_PII_HASH_SECRET}
      - column: msisdn
        strategy: mask
        params: {keepFirst: 0, keepLast: 4}
```

Masking is applied to the data as it lands, not by the warehouse at query time. The DuckDB acquisition runner rewrites each masked column inside its `COPY`, after the quality gates, so the local file, the S3 object, the file a BigQuery load job reads, and the DLQ all hold treated values (since 0.16.5).

| `strategy` | What lands | `params` | Secret (environment variable) |
|---|---|---|---|
| `hash` | 64 lowercase hex characters: SHA-256 of salt and value. Deterministic, so joins on it work | `saltEnv` | `FLUID_PII_HASH_SECRET` by default, at least 16 bytes |
| `mask` | Every character but the first `keepFirst` and last `keepLast` replaced by `*`, length kept: `+46701234567` becomes `********4567` | `keepFirst` (default 0), `keepLast` (default 4) | none |
| `tokenize` | 32 lowercase hex characters: HMAC-SHA256 of the value | `keyEnv` | `FLUID_PII_TOKENIZATION_KEY` by default, at least 32 bytes |
| `encrypt` | `aesgcm:v1:` and base64url of nonce, ciphertext and tag. Reversible with the key, not deterministic | `keyEnv` | `FLUID_PII_ENCRYPTION_SECRET_KEY` by default: base64 of a 16, 24 or 32-byte key (`openssl rand -base64 32`) |
| `k_anonymity` | Refused at landing: it is a property of a whole table, not a per-value transformation | — | — |

The build is refused, rather than landing cleartext, when a secret is unset or too short, when `params` holds a literal `salt` or `key` or any key not listed above, or when a masked column is not declared with a string type (a treated value always lands as a string). `fluid validate` rejects any other `strategy` value, such as `partial`. The `params` keys are typed in fluid-schema 0.7.6 and accepted untyped on 0.7.5.

Two other paths behave differently:

- An embedded-SQL build on DuckDB whose landed expose declares masking fails before landing with `MaskingNotAppliedError` ("the embedded-SQL landing path does not apply yet"). Land the expose through an engine that applies masking, or write the masking into `properties.sql` and declare the columns as they then land.
- No warehouse masking object is emitted from this field on any cloud: no BigQuery data policy, no Snowflake masking policy, nothing on Lake Formation (which controls access and does not mask values).

Since 0.17.0, `fluid verify` fails (CRITICAL) a masked column whose landed values lack the strategy's shape, on local files, S3 with Glue, and BigQuery, whichever path wrote them.

## Column-level `sensitivity`

```yaml
contract:
  schema:
    - name: email
      type: STRING
      sensitivity: pii
```

The tag does two things. `fluid policy-check` requires a matching `policy.privacy.masking` entry and reports a critical finding when there is none:

```bash
fluid policy-check contract.fluid.yaml
# 🚨 🔒 Data Sensitivity & Privacy (CRITICAL)
# └── 🚨 CRITICAL (1)
#     └── Field marked as pii but no privacy protection configured
#         ├── 📍 customers → email
#         └── 💡 Remediation: Add masking strategy for 'email' in
#             policy.privacy.masking
# ...
# Policy compliance check FAILED
# exit 1
```

And the [MCP output port](./agent-policy.md) replaces tagged column values with a redaction token in every governed query result. The tag provisions nothing on any platform by itself.

## Sovereignty

```yaml
sovereignty:
  jurisdiction: EU                  # EU, US, UK, CA, AU, JP, CN, IN, BR, Global, Multi-Region
  allowedRegions: [europe-west3, europe-west4]
  deniedRegions: [us-central1]
  dataResidency: true
  crossBorderTransfer: false
  transferMechanisms: [SCCs]        # SCCs, BCRs, Adequacy, DPF, Consent, Derogation
  regulatoryFramework: [GDPR]
  enforcementMode: strict           # strict, advisory, audit
  validationRequired: true
```

With `jurisdiction: EU` and `enforcementMode: strict`, a binding in `us-central1` fails `fluid validate`, and an AWS or GCP binding that names no region fails too. `fluid generate iac` and `fluid apply` refuse the same placements on AWS and GCP. The rules, the exit codes and the query-time gate are on [Sovereignty](./sovereignty.md).

## What gets emitted per cloud

What `fluid apply` and `fluid generate iac` write for each field on 0.18.1. Cells marked 0.7.6 need `fluidVersion: "0.7.6"` (preview); 0.7.5 is the stable schema.

| Contract field | AWS | GCP / BigQuery | Snowflake |
|---|---|---|---|
| `accessPolicy.grants` | Not emitted. Access on AWS is the binding's `governance.lakeFormation.grants`; `fluid validate` warns for an aws binding with no Lake Formation grants | One non-authoritative `google_bigquery_dataset_iam_member` per role and member: `read`/`select`/`query` → `roles/bigquery.dataViewer`, `write`/`insert`/`update`/`delete` → `roles/bigquery.dataEditor`, `admin` → `roles/bigquery.dataOwner` | Not emitted. Snowflake grants are written only from a top-level `security:` block, which the schema rejects |
| `policy.authz.columnRestrictions` | Each Lake Formation `SELECT` grant excludes the restricted columns its principal may not read | Data Catalog taxonomy per product and dataset, a policy tag per set of restricted columns, `categoryFineGrainedReader` for exactly the allowed readers | Not read |
| `policy.privacy.masking` | Applied at landing by the DuckDB runner; no Lake Formation object | Applied at landing by the DuckDB runner; no BigQuery data policy | Not read |
| Row-level security | `binding.governance.lakeFormation` data cells filters | Not emitted | Not read from contract fields |
| `lifecycle {retention, expire: true}` (0.7.6) | S3 lifecycle rule on the binding's prefix | Daily partitions that expire `retention` after their day | Not read |
| `binding.encryption.kms` (0.7.6) | SSE-KMS with a product key, an alias or an ARN | Cloud KMS key ring and key per dataset, 90-day rotation | Not read |

`fluid verify` checks column restrictions, retention and encryption on the live platform for AWS and GCP. As of 0.18.1 it does not check dataset grants.

Since 0.17.0, GCP dataset grants are member resources rather than the dataset's authoritative `access` list, so a grant made outside the contract is no longer removed. The first `fluid apply` after upgrading, on a dataset whose state still holds the old list, revokes once the entries no member resource covers, and prints them.

Prerequisites on GCP: the Data Catalog API (and the Cloud KMS API for keys) enabled, and `roles/datacatalog.categoryAdmin` (and `roles/cloudkms.admin` for keys) for the identity running `fluid apply`.

### One contract, two clouds: `binding.principals`

With fluid-schema 0.7.6, the base contract names principals the way the business knows them, and each environment's overlay maps them to that cloud's identities:

```yaml
# overlays/gcp.yaml
exposes:
  - binding:
      platform: gcp
      principals:
        group:analysts@northwind.example: group:analysts@northwind.com
        group:stewards@northwind.example: group:stewards@northwind.com

# overlays/aws.yaml
exposes:
  - binding:
      platform: aws
      principals:
        group:analysts@northwind.example: arn:aws:iam::123456789012:role/analyst
```

A value is one identity, a list, or `[]` for "no identity on this cloud" (nothing is granted to it there). With the block present, every principal the expose names must be mapped; an unmapped one is refused (`principal-unmapped`). Overlays are applied with `--env`; see [Per-environment overlays](../recipes/per-environment-overlays.md).

### `fluid policy-apply` enforces nothing

As of 0.18.1, `fluid policy-apply` provisions no binding on any provider, in either `--mode`:

- **GCP:** reports the compiled bindings and applies none; `fluid apply` provisions GCP IAM.
- **AWS and Snowflake:** prints a warning and exits 0:

```bash
fluid policy-apply runtime/policy/bindings.json --mode enforce
# ⚠️  No policy bindings were enforced — the 'aws' provider has no standalone
# policy applier. For cloud providers, IAM/GRANT, masking and row-access policies
# are emitted and applied during `fluid apply` (stage 7), so `fluid policy-apply`
# is a no-op for this provider.
```

For acquisition contracts it still registers retention, alerting and cost policies under `.fluid/policies/<contract-id>/` for the acquisition runtime. `fluid policy-compile` maps `write` to `roles/bigquery.dataOwner` in its GCP bindings JSON, while `fluid apply` grants `roles/bigquery.dataEditor`; the table above is what apply provisions.

### When `policy-compile` or `policy-apply` fails

`policy_compile_failed` and `policy_apply_failed` link to [Sovereignty](./sovereignty.md#when-policy-compile-or-policy-apply-fails), which covers both.

## Compliance frameworks

`sovereignty.regulatoryFramework` accepts an array of framework codes from a fixed enum: `GDPR`, `CCPA`, `CPRA`, `HIPAA`, `PIPEDA`, `LGPD`, `PDPA`, `POPIA`, `DPA`, `APPI`. `fluid validate` rejects anything outside it, `SOX` and `SOC2` included. The codes are declarative: they record which regimes govern the product. No code activates a validation rule of its own, so `policy-check` output is identical whether the field is present or absent. The enforced checks act on `sensitivity`, masking, grants and sovereignty, not on the framework code.

| Code | Regime it records |
|---|---|
| `GDPR` | EU General Data Protection Regulation. Pair it with `sovereignty.jurisdiction`, `allowedRegions` / `deniedRegions` and `crossBorderTransfer`, which `fluid validate` does enforce |
| `CCPA` | California Consumer Privacy Act |
| `CPRA` | California Privacy Rights Act; extends CCPA with sensitive-personal-information categories |
| `HIPAA` | US health data. Declare it and tag the affected columns `sensitivity: phi`, so the `policy-check` sensitivity rules cover them |
| `PIPEDA` | Canada's federal private-sector privacy law |
| `LGPD` | Brazil's Lei Geral de Proteção de Dados |
| `PDPA` | Personal Data Protection Act, the name shared by the Singapore, Thailand and Malaysia statutes |
| `POPIA` | South Africa's Protection of Personal Information Act |
| `DPA` | UK Data Protection Act |
| `APPI` | Japan's Act on the Protection of Personal Information |

Multiple codes may be listed; `uniqueItems` is enforced.

## Agent governance

`agentPolicy` gates AI and LLM reads at the MCP output port. It is a per-expose field at `exposes[].policy.agentPolicy`, not a top-level one; a contract with `agentPolicy` at the root fails `fluid validate`.

```yaml
exposes:
  - exposeId: customers
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@northwind.com
            columns: [email]
            access: deny
      agentPolicy:
        allowedModels: [claude-sonnet-4-6]
        deniedUseCases: [training, fine_tuning]
        canStore: false
        auditRequired: true
```

The two gates are separate. Cloud IAM (`accessPolicy`, column restrictions) governs principals that query the platform directly. `agentPolicy` governs callers of `fluid mcp output-port serve`, which checks the model and use case on every tool call. See [Agent Policy](./agent-policy.md).

## Audit trail

No command writes a unified audit record across clouds, and nothing is shipped to BigQuery audit logs, CloudTrail or Snowflake `ACCESS_HISTORY` by forge-cli. What exists:

- **Agent reads:** `fluid mcp output-port serve` writes a `data_access` event for every allow and deny decision to `~/.fluid/store/audit/` (or `FLUID_AUDIT_ROOT`), and can forward it to `FLUID_MCP_AUDIT_WEBHOOK_URL`. The record is shown on [Agent Policy](./agent-policy.md#audit-event-schema).
- **Applies:** `fluid apply` emits structured log events; an apply through OpenTofu (aws, gcp, snowflake) sends OpenLineage run events when `OPENLINEAGE_URL` is set; and since 0.17.0 reports each run to a Command Center deployment when the publish config is present (`FLUID_COMMAND_CENTER_ENABLED=false` turns it off).
- **Platform logs:** the reads themselves land in each cloud's own audit log as usual, under the identities that made them.

## Where to look next

- [Sovereignty](./sovereignty.md) — residency rules, the provision-time and query-time gates
- [Agent Policy](./agent-policy.md) — declarative LLM and agent access boundaries
- [Quality, SLAs & Lineage](./quality-sla-lineage.md) — the rule sets `dq.rules` enforces alongside policy
- [`fluid policy-check`](../cli/policy-check.md) — pre-deploy linting
- [`fluid policy-apply`](../cli/policy-apply.md) — the stage-8 command and what it does today
