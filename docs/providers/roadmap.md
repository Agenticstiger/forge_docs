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
| **Databricks** | Not built | Not built | Not available |

**Legend:**
- **Plan / Apply**: `fluid plan` + `fluid apply` provision the platform's resources.
- **Orchestration generation**: `fluid generate schedule --scheduler airflow|dagster|prefect` writes a DAG, pipeline or flow.

ODPS and ODCS are spec exporters, not providers ([`fluid exporters`](../cli/exporters.md)). Data Mesh Manager and the FLUID Command Center are catalog targets reached with [`fluid publish`](../cli/publish.md).

## Governance by provider

"Available" covers provisioning and builds. Governance is not the same on every cloud. In 0.18.1:

| Contract field | GCP | AWS | Snowflake |
|---|---|---|---|
| `accessPolicy.grants` | dataset IAM members | not emitted; access is `binding.governance.lakeFormation.grants` | compiled by `fluid policy-compile`, not applied |
| `policy.authz.columnRestrictions` | Data Catalog policy tags | Lake Formation excluded columns | not read |
| `policy.privacy.masking` | applied at landing by the DuckDB acquisition runner; checked by `fluid verify` | applied at landing by the DuckDB acquisition runner; checked by `fluid verify` | not read |
| `exposes[].lifecycle.expire` *(0.7.6)* | expiring DAY partitions | S3 lifecycle rule | not read |
| `binding.encryption.kms` *(0.7.6)* | Cloud KMS key ring and key | KMS key as the bucket default | not read |

The [GCP](./gcp.md#security-governance), [AWS](./aws.md) and [Snowflake](./snowflake.md#snowflake-native-security) pages give the detail.

## Not built yet

Not emitted as of 0.18.1 (checked against the GCP and Snowflake emitters):

- **GCP:** BigQuery row-level security, BigQuery dynamic data masking, VPC Service Controls, partitioning and clustering from `binding.properties`.
- **Snowflake:** grants from `accessPolicy`, masking and row access policies from the contract's `policy` fields.
- **Azure and Databricks** as `fluid apply` targets.

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

Each provider keeps its own OpenTofu state (`fluid/<id>/<provider>/terraform.tfstate` under a remote backend), so the two applies do not plan to destroy each other's resources. The [switch-clouds recipe](../recipes/switch-clouds.md) shows the binding diff.

## Community providers

A provider is a Python package registered under the `fluid_build.providers` entry-point group. See [Creating Custom Providers](./custom-providers.md).

## Request a provider

- [Provider feature requests](https://github.com/Agenticstiger/forge-cli/issues?q=is%3Aissue+is%3Aopen+label%3Aprovider)
- [GitHub Discussions](https://github.com/Agenticstiger/forge-cli/discussions)
- [Open a provider request issue](https://github.com/Agenticstiger/forge-cli/issues/new?labels=provider-request)
