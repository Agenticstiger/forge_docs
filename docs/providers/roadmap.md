# Provider Roadmap

What each provider does today, and what is not built yet. This page records status; it does not promise dates.

## Current status

| Provider | Plan / Apply | Orchestration generation | Availability |
|----------|-------------|-----------------|--------------|
| **GCP** | ✅ OpenTofu (`hashicorp/google`) | ✅ Airflow, Dagster, Prefect | Available |
| **AWS** | ✅ OpenTofu (`hashicorp/aws`) | ✅ Airflow, Dagster, Prefect | Available |
| **Snowflake** | ✅ OpenTofu (`snowflakedb/snowflake`) | ✅ Airflow, Dagster, Prefect | Available |
| **Local (DuckDB)** | ✅ Native | N/A | Available |
| **Azure** | Not built | Not built | Not available |
| **Databricks** | ✅ OpenTofu (`databricks/databricks`) | dbt builds run as Databricks jobs; `fluid generate schedule` gives such a build no task | Available since 0.26.0 ([Databricks](./databricks.md)) |

**Legend:**
- **Plan / Apply**: `fluid plan` + `fluid apply` provision the platform's resources.
- **Orchestration generation**: `fluid generate schedule --scheduler airflow|dagster|prefect` writes a DAG, pipeline or flow.

ODPS and ODCS are spec exporters, not providers ([`fluid exporters`](../cli/exporters.md)). Data Mesh Manager and the FLUID Command Center are catalog targets reached with [`fluid publish`](../cli/publish.md).

## Governance by provider

"Available" covers provisioning and builds. Governance is not the same on every cloud. In 0.18.1:

| Contract field | GCP | AWS | Snowflake | Databricks (on forge-cli `main`, not yet in a release) |
|---|---|---|---|---|
| `accessPolicy.grants` | dataset IAM members | not emitted; access is `binding.governance.lakeFormation.grants` | compiled by `fluid policy-compile`, not applied | one `databricks_grant` per principal, scoped by `resources` to the tables it names |
| `policy.authz.columnRestrictions` | Data Catalog policy tags; with `access: mask`, a BigQuery data policy *(0.19.0)* | Lake Formation excluded columns | not read | Unity Catalog column masks; a denied column reads `NULL` |
| `policy.privacy.masking` | applied at landing by the DuckDB acquisition runner; checked by `fluid verify` | applied at landing by the DuckDB acquisition runner; checked by `fluid verify` | not read | applied at landing by the DuckDB acquisition runner; refused on an expose another build writes |
| `exposes[].lifecycle.expire` *(0.7.6)* | expiring DAY partitions | S3 lifecycle rule | not read | a Delta history limit, for a table rebuilt in full (`databricks-retention-*` otherwise) |
| `binding.encryption.kms` *(0.7.6)* | Cloud KMS key ring and key | KMS key as the bucket default | not read | refused |
| `policy.authz.rowFilters` *(0.7.6)* | a `google_bigquery_row_access_policy` per filter *(0.19.0)* | a Lake Formation data cells filter per filter *(0.19.0)* | not read | a Unity Catalog row filter |
| Governance labels | labels on the dataset, table and key *(0.19.0)* | tags on the bucket and key, parameters on the Glue table *(0.19.0)* | not read | Unity Catalog tags |

`policy.privacy.masking` is applied when the data lands; no cloud receives a dynamic masking policy from it. On GCP, a column restriction with `access: mask` does get a BigQuery data policy *(0.19.0)*. [Governance parity](../concepts/governance-parity.md) compares AWS and GCP in full. The [GCP](./gcp.md#security-governance), [AWS](./aws.md) and [Snowflake](./snowflake.md#snowflake-native-security) pages give the detail.

## Not built yet

Not emitted as of 0.18.1 (checked against the GCP and Snowflake emitters):

- **GCP:** BigQuery dynamic data masking from `policy.privacy.masking`, VPC Service Controls, partitioning and clustering from `binding.properties`. BigQuery row-level security and a data policy for a column restriction with `access: mask` were added in 0.19.0, so they are not in this list.
- **Snowflake:** grants from `accessPolicy`, masking and row access policies from the contract's `policy` fields.
- **Azure** as a `fluid apply` target.

## Orchestration code

```bash
fluid generate schedule contract.fluid.yaml --scheduler airflow
fluid generate schedule contract.fluid.yaml --scheduler dagster
fluid generate schedule contract.fluid.yaml --scheduler prefect
```

`fluid generate-airflow` still exists; the docs use `fluid generate schedule`.

## One contract, several clouds

Keep one base contract and put each cloud's `binding` in an overlay ([per-environment overlays](../recipes/per-environment-overlays.md)), then apply with `--env`:

```bash
fluid apply contract.fluid.yaml --env aws --yes
fluid apply contract.fluid.yaml --env gcp --yes
```

Each provider keeps its own OpenTofu state (`fluid/<id>/<provider>/terraform.tfstate` under a remote backend), so the two applies do not plan to destroy each other's resources. The [switch-clouds recipe](../recipes/switch-clouds.md) shows the binding diff, and [One contract, two clouds](../recipes/one-contract-two-clouds.md) walks the whole deployment.

## Community providers

A provider is a Python package registered under the `fluid_build.providers` entry-point group. See [Creating Custom Providers](./custom-providers.md).

## Request a provider

- [Provider feature requests](https://github.com/Agenticstiger/forge-cli/issues?q=is%3Aissue+is%3Aopen+label%3Aprovider)
- [GitHub Discussions](https://github.com/Agenticstiger/forge-cli/discussions)
- [Open a provider request issue](https://github.com/Agenticstiger/forge-cli/issues/new?labels=provider-request)
