---
title: "Recipe — tag PII in your schema"
description: "Tag PII columns, mask them before they land with policy.privacy.masking, restrict who reads them, and fail verification when a masked column lands in cleartext."
---

# Recipe: tag PII in your schema

**Time:** 10 minutes · **Audience:** anyone shipping a contract with personally identifiable data

**Prerequisite:** the local DuckDB engine, from `pip install "data-product-forge[local]"`. Without it, `fluid apply --mode amend-and-build` fails with `No module named 'duckdb'`.

## Problem

Your data product has `email`, `ssn`, `phone_number` or other PII. You need:

1. The columns tagged, so the rest of the toolchain can tell they are sensitive.
2. The values treated before they land, so the landed file, S3 object or table holds treated values.
3. A check that fails when a column that should be treated is not.
4. Readers and AI agents limited to what they are allowed to see.

## Solution

Five additions to one contract, each read by a different part of forge. The first four steps run end to end on the local provider; steps 5 and 6 are explained from the contract, `fluid policy compile` output and the 0.18.1 source.

| You add | What reads it on 0.18.1 |
|---------|--------------------------|
| `sensitivity: pii` on a schema column | `fluid policy-check` (it requires a masking rule for the column); the MCP output port (it redacts the values) |
| `policy.privacy.masking` on the expose | The DuckDB acquisition runner (it treats the values as they land); `fluid verify` (it checks them); the MCP output port (it leaves the column out) |
| `policy.authz.columnRestrictions` | `fluid apply` on a BigQuery or AWS Lake Formation binding; the MCP output port |
| `accessPolicy.grants` | `fluid policy compile` writes the bindings; `fluid apply` provisions the dataset grants on GCP. `fluid policy apply` changes nothing in 0.18.1 |
| `policy.agentPolicy` | The MCP output port |

As of 0.18.1, the engine that applies masking at landing is the DuckDB acquisition runner (`pattern: acquisition`, `engine: duckdb`). An embedded-SQL build refuses an expose that declares masking; see [Edge cases](#edge-cases).

## 1. Tag the columns and declare the masking

```text
customers/
├── contract.fluid.yaml
└── data/
    └── customers.csv
```

```csv
customer_id,name,email,phone_number,ssn
c-001,Anna Berg,anna@example.com,+46701234567,19800101-1234
c-002,Bo Lind,bo@example.com,+46709876543,19750505-9876
c-003,Cleo Sand,cleo@example.com,+46705550000,19900909-4321
```

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.crm.customers
name: CRM customers
metadata:
  layer: Bronze
  productType: SDP
  owner:
    team: data-platform
    email: data-platform@example.com
builds:
  - id: ingest_customers
    pattern: acquisition
    engine: duckdb
    properties:
      source:
        kind: filesystem
        mode: full_refresh
        connection:
          uri: data/customers.csv
        reader:
          format: csv
        streams:
          - customers
      sink:
        format: parquet
    outputs:
      - customers
exposes:
  - exposeId: customers
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/customers.parquet
    contract:
      schema:
        - { name: customer_id, type: VARCHAR }
        - { name: name,         type: VARCHAR, sensitivity: pii }
        - { name: email,        type: VARCHAR, sensitivity: pii }
        - { name: phone_number, type: VARCHAR, sensitivity: pii }
        - { name: ssn,          type: VARCHAR, sensitivity: pii }
    policy:
      privacy:
        masking:
          - column: email
            strategy: tokenize
          - column: phone_number
            strategy: hash
          - column: ssn
            strategy: mask
            params:
              keepLast: 4
          - column: name
            strategy: encrypt
```

`sensitivity` takes one of `none`, `internal`, `confidential`, `restricted`, `pii`, `phi`, `cleartext`, `treated`, `anonymized`, `pseudonymized`, `tokenized` or `encrypted`. By itself it is a label. The masking rules are what change the data.

### The four strategies

The runner rewrites each masked column inside the `COPY` that writes the data, after the quality gates have run on the source values. What lands in the local file, the S3 object, the file a BigQuery load job reads, and the dead-letter queue is already treated.

| `strategy` | What lands | `params` | Secret, read from the environment |
|------------|------------|----------|-----------------------------------|
| `hash` | Lowercase hex SHA-256 of the salt followed by the value (64 characters). For one salt, the same value hashes to the same digest, so joins across products that share the salt still work. The same digest is computed in DuckDB and in Athena | `saltEnv`: the variable that holds the salt | `FLUID_PII_HASH_SECRET` unless `saltEnv` names another. At least 16 bytes |
| `mask` | Every character replaced with `*` except the first `keepFirst` (default 0) and the last `keepLast` (default 4); length is preserved. A value no longer than the two together is masked entirely | `keepFirst`, `keepLast` | None |
| `tokenize` | A 32-character hex token, HMAC-SHA256 of the value, truncated. Deterministic for one key | `keyEnv`: the variable that holds the key | `FLUID_PII_TOKENIZATION_KEY` unless `keyEnv` names another. At least 32 bytes |
| `encrypt` | `aesgcm:v1:` followed by base64url of nonce, ciphertext and tag (AES-GCM, column name as associated data). Reversible with the key, not deterministic, so you cannot join on it | `keyEnv` | `FLUID_PII_ENCRYPTION_SECRET_KEY` unless `keyEnv` names another. The base64 of 16, 24 or 32 bytes (`openssl rand -base64 32`) |

`k_anonymity` is in the schema's `strategy` enum but is refused at build: k-anonymity is a property of a whole table, and a per-column rule cannot guarantee it.

The secrets come from the environment, not from the contract. A literal `salt` or `key` in `params` is refused, because it would be published with the contract.

## 2. Land the data

```bash
export FLUID_PII_HASH_SECRET=$(openssl rand -hex 16)
export FLUID_PII_TOKENIZATION_KEY=$(openssl rand -hex 32)
export FLUID_PII_ENCRYPTION_SECRET_KEY=$(openssl rand -base64 32)

fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --mode amend-and-build --yes
```

In CI, set the three variables from your secret store. `--mode amend-and-build` is what runs the build; the default `amend` mode does not. The landed Parquet file, read back (your hash, token and ciphertext differ, because your secrets differ):

```text
('c-001', 'aesgcm:v1:2pYroNzxP6_4bexzNYE9LVsYbK38r0afJP3_UgK_Pn8GNmAbZA',
 '7eec54f79efc369cd9fb0fca6c686864',
 '80672927a78fc34d23f4254c9e0af3feb19d75b5d822125c47c6cb44320770a9',
 '*********1234')
```

The columns are `customer_id`, `name`, `email`, `phone_number`, `ssn`: the encrypted name, the email token, the phone hash and the masked SSN. The mask keeps the last four characters of `19800101-1234`, so the hyphen is replaced too.

## 3. Verify that the data landed treated

```bash
fluid verify contract.fluid.yaml --strict
```

```text
   🔍 Dimension 2: Masking
      ✅ PASS - every non-null value has its strategy's shape: email (tokenize),
phone_number (hash), ssn (mask), name (encrypt)
```

`fluid verify` checks every non-null value of each masked column against the shape its strategy produces, on a local file, on S3 through Athena, and on BigQuery. It does not hold the salt or the key, so it checks shape, not correctness.

Overwrite the file with a cleartext `email` and verify again:

```text
   🔍 Dimension 2: Masking
      ❌ FAIL - masked column(s) did not land treated
         ❌ email (tokenize): 3 of 3 non-null value(s) are not 32 lowercase
hexadecimal characters (HMAC-SHA256 token); the column holds untreated values
         ✅ phone_number (hash): 3 non-null value(s), all 64 lowercase
hexadecimal characters (SHA-256)
```

The severity is CRITICAL, and `fluid verify --strict` exits 1. Without `--strict` the same run exits 0 and only reports.

## 4. Make `sensitivity: pii` count

```bash
fluid policy-check contract.fluid.yaml
```

`fluid policy-check` fails a column tagged `pii` that has no masking rule. Remove the `ssn` rule from the contract above and the check fails with exit 1:

```text
🚨 🔒 Data Sensitivity & Privacy (CRITICAL)
└── 🚨 CRITICAL (1)
    └── Field marked as pii but no privacy protection configured
        ├── 📍 customers → ssn
        └── 💡 Remediation: Add masking strategy for 'ssn' in
            policy.privacy.masking
```

With the rule restored, the same check passes with a 95/100 score; the 5 points are an advisory that a contract holding sensitive data should declare `lifecycle.retention`. The check confirms that a rule exists for the column. It does not read the data; step 3 does.

## 5. Limit who reads the columns

Restrict columns by principal with `policy.authz.columnRestrictions`, and grant the read itself with the root-level `accessPolicy`:

```yaml
accessPolicy:
  grants:
    - principal: group:analysts@example.com
      permissions: [read, select]
exposes:
  - exposeId: customers
    policy:
      authz:
        columnRestrictions:
          - principal: group:analysts@example.com
            columns: [name, ssn]
            access: deny
```

- **BigQuery.** `fluid apply` creates a Data Catalog taxonomy per product and dataset, a policy tag per set of restricted columns that share their readers, and grants the fine-grained reader role on each tag to exactly the principals allowed. A denied principal gets an access error on the restricted columns. On 4 October 2026, against real Google Cloud, on 0.18.0, the refusal read: `User has neither fine-grained reader nor masked get permission to get data protected by policy tag "<taxonomy> : <tag>" on column <project>.<dataset>.<table>.<column>.`
- **AWS.** On a binding with Lake Formation grants, each `SELECT` grant excludes the restricted columns its principal may not read.
- A restriction on an expose that has no reader is refused on both clouds (`column-restriction-no-readers` on GCP, `column-restriction-unenforceable` on AWS), because the policy tag or Lake Formation exclusion would otherwise lock the columns for everyone.
- **Snowflake.** As of 0.18.1, forge reads none of `sensitivity`, `policy.privacy.masking`, `policy.authz.columnRestrictions` or `policy.privacy.rowLevelPolicy` when it deploys to Snowflake, and creates no masking or row access policy object from them. Treat the data with step 2 before it reaches Snowflake.
- **Dynamic masking on BigQuery** (a data policy that shows hashed or nulled values to a masked-reader role) is not emitted: it would need a third set of principals the contract has no field for.

`fluid policy compile` turns `accessPolicy` into provider bindings. With the expose bound to a BigQuery table (`platform: gcp`, `format: bigquery_table`):

```bash
fluid policy compile contract.fluid.yaml --out runtime/policy/bindings.json
fluid policy apply runtime/policy/bindings.json --mode check     # reports the bindings; changes nothing in 0.18.1, in either mode
```

```json
{
  "bindings": [
    {
      "provider": "gcp",
      "resource_type": "bigquery.dataset",
      "resource_id": "my-project.crm",
      "project": "my-project",
      "dataset": "crm",
      "principal": "group:analysts@example.com",
      "roles": [
        "roles/bigquery.dataViewer"
      ]
    }
  ],
  "warnings": []
}
```

On the local binding from steps 1 to 4, `fluid policy compile` writes `"bindings": []` and the warning `No IAM bindings generated from contract`, because local files have no IAM.

## 6. Limit AI agents

`agentPolicy` lives on each expose, at `exposes[].policy.agentPolicy`. It is not a contract-root key; a root-level `agentPolicy` fails `fluid validate`.

```yaml
exposes:
  - exposeId: customers
    policy:
      agentPolicy:
        allowedModels: [claude-sonnet-4-6]
        allowedUseCases: [analysis, summarization]
        deniedUseCases: [training]
        auditRequired: true
```

Agents that read the product through the MCP output port are held to it, and the port treats the columns you tagged as follows:

- A column tagged `sensitivity: pii`, `phi` or `sensitive` stays in the result so the agent knows it exists, but every value is replaced with `[REDACTED-PII]`.
- A column named in a `policy.privacy.masking` rule, or denied by `columnRestrictions` for any principal, is left out of the result.

The fields of `agentPolicy` are in [Agent Policy](../concepts/agent-policy.md), and the port itself is in [MCP output port](../advanced/mcp.md). An agent that reads the landed files or the warehouse directly is outside this: `agentPolicy` and the redaction apply at the MCP gateway.

## Edge cases

- **Declare a masked column with a string type.** A treated column lands as a string. `BIGINT` on a masked column is refused at build: `declares 'ssn' as BIGINT, but mask lands it as a string`. On a CSV source, declare `VARCHAR`: the same column declared `string` failed with `source schema drift detected` (`type_changed`) under the default schema policy, because the source reports `VARCHAR`.
- **Unset or short secrets are refused, not skipped.** With `FLUID_PII_TOKENIZATION_KEY` unset: `masking tokenize on column 'email' needs a key in the environment variable FLUID_PII_TOKENIZATION_KEY, which is unset or empty. Refusing to land the column untreated`. A salt shorter than 16 bytes, or a key shorter than 32, is refused the same way. A name in `saltEnv` or `keyEnv` must be an upper-case environment variable name.
- **Rules naming a column the source lacks fail the build** and nothing is landed: `names column 'nope', which stream 'customers' does not have`.
- **Unknown `params` are refused.** `hash` takes only `saltEnv`, `mask` takes `keepFirst` and `keepLast`, and `tokenize` and `encrypt` take `keyEnv`.
- **Embedded SQL does not mask.** A build with `pattern: embedded-logic` that lands an expose declaring `policy.privacy.masking` fails with `MaskingNotAppliedError`, including when it lands to BigQuery. A governed Silver or Gold table with masking is therefore not built by embedded SQL today. Mask in the Bronze acquisition build, or write the masking into the build's SQL and declare the columns as they then land. See [Consume one contract from another](./consumes-contract-to-contract.md).
- **Quality checks see different values before and after.** The acquisition build's own `quality.gates` run on the source values, before the rewrite. `dq.rules` run by `fluid test` read the landed, treated file, so a rule that expects the original values, such as `valid_values` on a hashed column, no longer matches. See [Add a quality rule](./add-a-quality-rule.md).

## See also

- [Concepts: Governance and Policy](../concepts/governance-policy.md): `accessPolicy`, `sovereignty` and the rest of the policy surface
- [Governance parity](../concepts/governance-parity.md): the column-restriction emit on BigQuery and Lake Formation, and what `fluid verify` checks on each
- [Masking at landing](../advanced/source-aligned-acquisition.md#masking-at-landing): where the DuckDB build treats the values
- [Concepts: Agent Policy](../concepts/agent-policy.md): the `agentPolicy` fields
- [`fluid policy-check`](../cli/policy-check.md), [`fluid policy compile`](../cli/policy-compile.md), [`fluid policy apply`](../cli/policy-apply.md)
- [`fluid verify`](../cli/verify.md): the masking dimension and `--strict`
- [Source-aligned acquisition](../advanced/source-aligned-acquisition.md): the acquisition build the masking runs in
