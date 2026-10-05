# Governance & Compliance

FLUID puts governance in the data product contract: who can read a product, which columns are sensitive, where the data may live, and what checks it must pass. This page covers the commands that check and apply those declarations, the contract shapes they read, and how sovereignty is enforced. The concepts behind them are in [Governance policy](../concepts/governance-policy.md) and [Sovereignty](../concepts/sovereignty.md).

## Example: a governed product

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: gold.customer_profiles
name: Customer Profiles
domain: customer
metadata:
  layer: Gold
  owner:
    team: data-platform
    email: data-platform@acme.example.com

sovereignty:                       # where the data may live
  jurisdiction: EU
  allowedRegions: [europe-west1]
  enforcementMode: strict

accessPolicy:                      # who may read and write, at the top level
  grants:
    - principal: group:analysts@acme.example.com
      permissions: [read]
    - principal: serviceAccount:etl@my-project-id.iam.gserviceaccount.com
      permissions: [write]

builds:
  - id: load_profiles
    pattern: embedded-logic
    engine: sql
    properties:
      sql: SELECT 1 AS customer_id, 'a@example.com' AS email, 'DE' AS country
    outputs: [customer_table]

exposes:
  - exposeId: customer_table
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project-id
        dataset: customers
        table: customer_profiles
        region: europe-west1       # required once a sovereignty block exists
    lifecycle:
      retention: P90D
    policy:
      privacy:
        masking:
          - column: email
            strategy: hash
    contract:
      schema:                      # an array of columns
        - { name: customer_id, type: INTEGER, required: true, sensitivity: internal }
        - { name: email, type: STRING, sensitivity: pii }
        - { name: country, type: STRING, sensitivity: none }
      quality:                     # each rule needs rule, expression and severity
        - rule: email_not_null
          expression: email IS NOT NULL
          severity: error
```

The shapes that trip people up:

| Declaration | Where it goes | What fails |
|---|---|---|
| Who can access | `accessPolicy.grants[]` at the top level of the contract, each with `principal` and `permissions` | `accessPolicy` under an expose, or `role` and `members` keys, fail validation |
| Columns | `exposes[].contract.schema`, an array of `{name, type, ...}` | A `schema.fields` object fails validation |
| Sensitivity | `sensitivity` on a column, one of `none`, `internal`, `confidential`, `restricted`, `pii`, `phi`, `cleartext`, `treated`, `anonymized`, `pseudonymized`, `tokenized`, `encrypted` | Capitalised values such as `PII` or `Financial` fail validation |
| Quality rules | `exposes[].contract.quality[]` with `rule`, `expression`, `severity` (`error`, `warning`, `info`) | An item with `field` and `rule: not_null` is missing `expression` |
| Retention | `retention` under an expose's `lifecycle` | |
| Masking | `policy.privacy.masking[]` on the expose | |

## Governance commands

### `fluid policy-check`

Checks a contract against the schema-driven policy engine. It reads only the contract; nothing is deployed.

```bash
fluid policy-check contract.fluid.yaml --format text
```

For the contract above without the `masking` and `lifecycle` blocks, the report is:

```text
❌ Sensitivity (1 issues)
  CRITICAL: Field marked as pii but no privacy protection configured
    💡 Add masking strategy for 'email' in policy.privacy.masking

✅ Access Control

✅ Data Quality

❌ Lifecycle (1 issues)
  WARNING: Sensitive data should have explicit retention policy
    💡 Add lifecycle.retention (e.g., 'P90D' for 90 days)

✅ Schema Evolution

============================================================
Checks Passed: 2
Checks Failed: 1
Advisory Issues: 1
Total Violations: 2
Blocking Issues: 1
Policy Score: 75/100

❌ Contract has policy violations
Policy compliance check FAILED
```

With both blocks present, all five categories pass and the score is `100/100`. The command exits 1 when a violation is blocking (`CRITICAL` or `ERROR`). Warnings and info lower the score and do not fail the command, unless you pass `--strict`.

| Option | Description | Default |
|--------|-------------|---------|
| `--env <name>` | Environment overlay (`dev`, `staging`, `prod`) | none |
| `--strict` | Fail on any violation, warnings included | `false` |
| `--category <name>` | Check one category: `sensitivity`, `access_control`, `data_quality`, `lifecycle`, `schema_evolution` | all |
| `--output`, `-o` | Also write the report as JSON to this file | none |
| `--format` | `rich`, `text` or `json` | `rich` |
| `--show-passed` | List the checks that passed | `false` |

`fluid policy check`, `fluid policy compile` and `fluid policy apply` are the same commands under one `fluid policy` entry point.

| Category | What it checks, with the rule that fires |
|----------|------------------------------------------|
| `sensitivity` | A `pii` column with no entry in `policy.privacy.masking`; a column marked `encrypted` whose binding has no encryption; a sensitive column left at `cleartext` |
| `access_control` | A column restriction that names a column that does not exist; a `Public` classification over sensitive columns; a `Restricted` classification with no readers; an unknown masking strategy |
| `data_quality` | A critical `dq` rule with monitoring off; a freshness rule with no threshold; a completeness threshold outside 0 to 1 |
| `lifecycle` | A deprecated product with no replacement or notice period; sensitive data with no `lifecycle.retention` on the expose |
| `schema_evolution` | A breaking-change policy with no approvers or no approval requirement; a very short change window |

### `fluid policy-compile`

Compiles the top-level `accessPolicy.grants` into provider IAM bindings. The provider and project come from each expose's `binding`.

```bash
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
```

```json
{
  "bindings": [
    {
      "provider": "gcp",
      "resource_type": "bigquery.dataset",
      "resource_id": "my-project-id.customers",
      "project": "my-project-id",
      "dataset": "customers",
      "principal": "group:analysts@acme.example.com",
      "roles": ["roles/bigquery.dataViewer"]
    },
    {
      "provider": "gcp",
      "resource_type": "bigquery.dataset",
      "resource_id": "my-project-id.customers",
      "project": "my-project-id",
      "dataset": "customers",
      "principal": "serviceAccount:etl@my-project-id.iam.gserviceaccount.com",
      "roles": ["roles/bigquery.dataOwner"]
    }
  ],
  "warnings": []
}
```

`read`-style permissions map to a viewer role and `write`, `insert`, `update` or `delete` to an owner role. A contract with no grants compiles to an empty list and a `No grants found in accessPolicy` warning.

| Option | Description | Default |
|--------|-------------|---------|
| `--env <name>` | Environment overlay | none |
| `--out <path>` | Where to write the bindings | `runtime/policy/bindings.json` |

### `fluid policy-apply`

Hands the compiled bindings to the provider. It takes the provider and project from the bindings file, so it needs no provider flag. As of 0.18.1 it changes no cloud permissions on any provider, in either mode:

```bash
fluid policy-apply runtime/policy/bindings.json --mode check     # the default
fluid policy-apply runtime/policy/bindings.json --mode enforce   # same effect in 0.18.1
```

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | `check` or `enforce`. Neither changes what a provider does in 0.18.1 | `check` |

On GCP the command reports the compiled bindings and returns `applied: 0`. A provider with no standalone policy applier prints that no bindings were enforced and exits 0. An empty bindings file is a no-op that exits 0. GCP access is provisioned by `fluid apply`, which writes the dataset IAM from `accessPolicy.grants` and the policy tags for column restrictions. See [`fluid policy apply`](../cli/policy-apply.md#what-each-provider-does) for each provider.

## Governance workflow

```bash
# 1. Check the contract
fluid policy-check contract.fluid.yaml --strict

# 2. Compile grants to provider IAM bindings, for review
fluid policy-compile contract.fluid.yaml

# 3. Hand the bindings to the provider (reports them; changes nothing in 0.18.1)
fluid policy-apply runtime/policy/bindings.json --mode check

# 4. Provision access: on GCP this is the step that creates the IAM
fluid apply contract.fluid.yaml --env <env>
```

In CI, fail the pipeline on any finding and keep the report:

```bash
fluid policy-check contract.fluid.yaml --strict --format json --output report.json
```

## Sovereignty enforcement modes (since 0.15.0)

A contract's `sovereignty` block declares where its data may live. `enforcementMode` decides what a violation does. One function maps the mode onto a severity, applied to the mode-sensitive checks on this page:

| `enforcementMode` | Severity | Effect |
|---|---|---|
| `strict` *(the schema default)* | ❌ error | [`fluid validate`](../cli/validate.md) exits 1; [`fluid plan --check-sovereignty`](../cli/plan.md#sovereignty-gate-since-0-15-0) blocks. |
| `advisory` | ⚠️ warning | Reported, does not block, though `fluid validate --strict` promotes warnings to errors. |
| `audit` | ℹ️ info | Logged only. |

The engine reads the schema's own defaults: `enforcementMode: strict`, `dataResidency: true` and `crossBorderTransfer: false`. A contract that declares a policy and relies on those defaults is evaluated under the strict settings.

Two carve-outs are deliberate:

- **`deniedRegions` is an error in every mode.** An operator naming a specific prohibition outranks a mode default, and `fluid validate` and `fluid plan` must block on the same contract, or a product passes one stage and fails the next.
- **A region with no known jurisdiction** is handled by mode (see [An unrecognised region](#an-unrecognised-region)).

### Every cloud binding names its region

Under a `sovereignty` block, an `aws`, `gcp` or `azure` binding with no `location.region` cannot be checked, because the platform would choose where the data goes. The check follows the mode: `strict` refuses, `advisory` warns, `audit` logs.

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
 1. ❌  Binding declares no region, so where its data lives cannot be checked
against the sovereignty policy (the platform would choose)
   💡 Set binding.location.region to one of: europe-west1
```

A GCP binding with no sovereignty block still validates without a region, and BigQuery then places the dataset in the `US` multi-region. Add `sovereignty` and the missing region is an error. The rule and the GCP location table are in [A cloud binding must name a region it can place](../concepts/sovereignty.md#a-cloud-binding-must-name-a-region-it-can-place).

BigQuery and Cloud Storage multi-regions are regions too. Write `region: EU` or `region: US`; each resolves to the EU or US jurisdiction. Because `allowedRegions` is compared by name, a product that lives in the `EU` multi-region lists `EU` there, next to or instead of `europe-west1`.

### An unrecognised region

A region the table below cannot place is `Unknown`. Under `strict`, a cloud binding whose region is `Unknown` is refused against a declared `jurisdiction`, unless the region is named in `allowedRegions`, which is the explicit opt-in:

```text
 1. ❌  Region 'mars-north1' not in allowed regions list
   💡 Allowed regions: europe-west1
 2. ❌  Region 'mars-north1' (jurisdiction: Unknown) does not match required 
jurisdiction: EU
   💡 Use a region in the EU jurisdiction; if 'mars-north1' is one, name it in 
sovereignty.allowedRegions
```

That output is for the governed product above with its region changed to `mars-north1`. With `allowedRegions: [mars-north1]` the contract validates with two warnings. Under `advisory` and `audit` an unrecognised region warns or logs. The separate cross-border finding, `Region 'x' has no known jurisdiction`, is a warning in every mode. This strict-mode refusal is new in 0.17.0; before it, an unmappable region stayed a warning even under `strict`.

::: warning Behavior changes
**0.15.0.** `enforcementMode` had failed in both directions at once. The jurisdiction check hardcoded warning severity, so a `strict` EU contract with every expose on `us-east-1` validated clean and now exits 1. The cross-border check hardcoded error severity, so it failed the build under `advisory`; it now warns. `jurisdiction: Multi-Region` needs no action: like `Global`, it is skipped, because no region resolves to it.

**0.17.0.** A GCP binding with no region, and a region that resolves to `Unknown`, are refused under `strict` where they used to pass. The GCP provider now enforces the policy at `fluid apply` and `fluid generate iac` (see below).
:::

### The region → jurisdiction table is derived *(since 0.15.0)*

Verdicts can change on a contract nobody edited, because the table they are computed from comes from vendor data:

- **AWS** regions resolve through botocore's shipped `endpoints.json`, the vendor's own table, including GovCloud and the EU Sovereign Cloud. New AWS regions arrive by upgrading `boto3`, not by waiting for a FLUID release.
- **GCP and Azure** regions resolve through CSVs vendored from `dgl/cloud-regions` (ODbL-1.0, recorded in `NOTICE`), with a corrections map for rows upstream ships empty.

This is identity, not adequacy. London is not in the EU: a product declaring EU-only residency and deploying to `eu-west-2` or `europe-west2` fails. The UK and Switzerland hold GDPR adequacy decisions, but a contract asking for `jurisdiction: EU` has not asked for the UK. Adequacy belongs in `transferMechanisms`, which the schema already carries.

Since 0.17.0 the table also covers:

| Location | Resolves to |
|---|---|
| `US`, `EU` (BigQuery and Cloud Storage multi-regions) | `US`, `EU` |
| Dual-regions `EUR4`, `NAM4`, `ASIA1` | `EU`, `US`, `JP` |
| GCP regions newer than the vendored CSV, for example `europe-west10`, `me-central2` | `EU`, `SA` |
| Dual-regions `EUR5`, `EUR7`, `EUR8` and the `ASIA` multi-region | `Unknown` |

A Cloud KMS key ring and a Data Catalog taxonomy are placed at their dataset's multi-region (`europe` and `eu` for an `EU` dataset), and a Pub/Sub topic's region becomes `message_storage_policy.allowed_persistence_regions`. Each is checked against the policy as a placement of its own.

### Where sovereignty is enforced

| Stage | What it does |
|---|---|
| [`fluid validate`](../cli/validate.md) | Runs the policy engine on every contract; severity follows `enforcementMode`. |
| [`fluid plan --check-sovereignty`](../cli/plan.md#sovereignty-gate-since-0-15-0) | Opt-in when you run `plan` yourself. Since 0.17.0 every pipeline that `fluid generate ci` emits runs stage 6 as `fluid plan ... --out runtime/plan.json --check-sovereignty`, so a strict violation fails before any stage reaches a cloud. A contract with no `sovereignty` block prints `NOT CHECKED` and passes. |
| [`fluid generate iac`](../cli/generate-iac.md) / [`fluid apply`](../cli/apply.md) | The AWS provider, and since 0.17.0 the GCP provider, refuse a placement outside the policy and exit 1, and **no module is written**. GCP checks every location the plan emits, including one a resource inherits by default. |
| Embedded-SQL builds on BigQuery | The read and the landing are checked against the policy too (`EmbeddedSqlSovereigntyError`). |
| [`fluid mcp output-port serve`](mcp.md#caller-jurisdiction-enforcement-since-0-15-0) | A pinned `jurisdiction` becomes a query-time gate on the **verified** caller jurisdiction, enforced by default, with the escape hatches in the contract and not in a flag. |

A GCP contract bound to `us-central1` under an EU policy is refused at the IaC step:

```text
  error: GCP placement refused by the sovereignty policy: dataset_customers:
Region 'us-central1' not in allowed regions list; dataset_customers: Region
'us-central1' (jurisdiction: US) does not match required jurisdiction: EU; ...
```

## What the platform enforces

Besides sovereignty, `fluid apply` emits, and `fluid verify` checks on the live platform, these governance fields on AWS and GCP:

| Field | AWS | GCP | Schema |
|---|---|---|---|
| `exposes[].lifecycle {retention, expire: true}` | An S3 lifecycle rule for the binding's prefix | Daily partitions with an expiration, never a table expiration | `0.7.6` (preview) |
| `binding.encryption.kms` | A KMS key per bucket, or the key you name | A Cloud KMS key ring and key per dataset, or the key you name | `0.7.6` (preview) |
| `exposes[].policy.authz.columnRestrictions` | Lake Formation grants that exclude the restricted columns | Data Catalog policy tags with fine-grained readers | `0.7.5` |
| `binding.principals` | Maps logical principals to IAM identities | Maps logical principals to IAM identities | `0.7.6` (preview) |

The `0.7.6` fields validate only with `fluidVersion: "0.7.6"`. `columnRestrictions` is in `0.7.5` and is enforced there. [Governance parity](../concepts/governance-parity.md) has the emitted resources per cloud, what `fluid verify` checks on each, and what has been measured against a real account.

On GCP, a principal on a `gcp` binding that is a placeholder is refused at `fluid validate`: a reserved top-level domain (`.example`, `.test`, `.invalid`, `.localhost`) or something that is not an IAM member at all. BigQuery and Cloud Storage refuse them at apply, so none was ever a working grant.

Platform-native dynamic masking is not emitted from `policy.privacy.masking`. For a DuckDB acquisition build, the values are treated before they land; see [Masking at landing](./source-aligned-acquisition.md#masking-at-landing).

## See also

- [Governance policy](../concepts/governance-policy.md): the concepts behind these declarations
- [Sovereignty](../concepts/sovereignty.md): jurisdiction, regions and the enforcement points
- [MCP output port](./mcp.md): runtime `agentPolicy` and caller-jurisdiction enforcement
- [GCP provider](../providers/gcp.md): IAM, policy tags, KMS
- [AWS provider](../providers/aws.md): IAM, Lake Formation, sovereignty
- [Snowflake provider](../providers/snowflake.md): RBAC and warehouse grants
- [`fluid apply`](../cli/apply.md): deploy with governance enforcement
- [CLI reference](../cli/README.md): all commands
