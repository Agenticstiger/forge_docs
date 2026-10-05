---
title: Tutorials
description: End-to-end walkthroughs in the order a new user meets them, with what each one builds, what it needs, and how long it takes.
---

# Tutorials

Each tutorial builds something real from start to finish, with the output the CLI printed when the page was run. Start with [Getting Started](../getting-started/README.md) if you have not installed the CLI yet.

They are listed in the order a data product goes through its life: build it locally, put it on a cloud, ship it through CI, schedule it, serve it, and generate contracts from what you already have. Times are the page's own estimate where it gives one.

## Build locally

| Tutorial | What you build | What you need | Time |
| --- | --- | --- | --- |
| [Getting Started](../getting-started/README.md) | One product that reads a CSV, with a data-quality rule that `fluid test` checks | Python 3.10+, `pip` | about 10 min |
| [Local development](./local.md) | Two chained products in one workspace: the second reads the first through `consumes` | Python 3.10+, `pip` | 15 min |
| [Source-aligned: Postgres → DuckDB](./source-aligned-postgres-duckdb.md) | A Bronze product that ingests a Postgres table into Parquet with no pipeline code | Docker, a clone of the forge-cli repo | — |

## Deploy to a cloud

| Tutorial | What you build | What you need | Time |
| --- | --- | --- | --- |
| [Google Cloud (BigQuery)](./gcp.md) | A BigQuery product with dataset access, partition expiry and the preview `0.7.6` schema | A GCP project with billing, `gcloud`, OpenTofu | 20 min |
| [Snowflake quickstart](../getting-started/snowflake.md) | A first Snowflake deployment from the `smoke` example | A Snowflake account, key-pair or OAuth credentials | — |
| [Snowflake team review](./snowflake.md) | The pull-request flow three engineers use to review a Snowflake contract before it deploys | A Snowflake account, git | 15 min |
| [One contract, two clouds](../recipes/one-contract-two-clouds.md) | One contract deployed to AWS and to GCP through `--env` overlays, governed the same on both | The `local`, `aws` and `gcp` extras, `jq`; OpenTofu and cloud credentials only for the apply | 15 min locally |

There is no separate AWS tutorial. [One contract, two clouds](../recipes/one-contract-two-clouds.md) covers S3, Glue and Lake Formation, and the [AWS provider](../providers/aws.md) page has a worked example.

## Ship through CI and schedule

| Tutorial | What you build | What you need | Time |
| --- | --- | --- | --- |
| [The 11-stage pipeline](./11-stage-pipeline.md) | A generated Jenkinsfile, and each of its eleven stages run by hand so you see what every gate checks | Python 3.10+; Jenkins only to run the generated file | — |
| [Jenkins CI/CD](./jenkins-cicd.md) | The generated pipeline running on a Jenkins controller, with credentials and failure handling | A Jenkins controller and agent | — |
| [Universal pipeline](./universal-pipeline.md) | One hand-written Jenkinsfile that serves several providers | Jenkins, credentials for the providers you target | — |
| [Declarative Airflow](./airflow-declarative.md) | An Airflow DAG that runs `fluid apply` on the schedule declared in the contract | The product from [Local development](./local.md); Airflow to run the DAG | — |
| [Orchestration export](./export-orchestration.md) | Airflow, Dagster or Prefect code exported from a contract's `orchestration.tasks`, for AWS, GCP and Snowflake | Python 3.10+; an account or project id passed with `--project` | — |

## Serve and generate

| Tutorial | What you build | What you need | Time |
| --- | --- | --- | --- |
| [MCP output port](./mcp-output-port.md) | A governed MCP server over one expose, with PII redaction and an `agentPolicy` deny you can watch happen | Python 3.10+, Node.js for the MCP Inspector | 10 min |
| [AI forge and data models](./ai-forge-data-model.md) | Contracts and dbt projects forged from a business intent, DDL or a source catalog | An LLM provider (hosted key or Ollama) | — |
| [Catalog → contract → transformation](./catalog-forge-end-to-end.md) | A contract, a logical-model sidecar and a dbt scaffold from a Snowflake schema | A Snowflake account with `INFORMATION_SCHEMA` access; an LLM key unless you run `--deterministic` | — |

## How tutorials differ from the other sections

- **Tutorials** (this section) teach by building. Follow one from the top.
- **[Recipes](../recipes/README.md)** and **[CLI by task](../cli/tasks/README.md)** are how-to guides: one task each, for a reader who already has a contract.
- **[Concepts](../concepts/README.md)** explain why the contract and the engine work the way they do.
- **[CLI reference](../cli/README.md)** and the **[contract reference](../reference/README.md)** list the commands, flags and fields.

Recorded demos are on [See it run](../see-it-run.md) and [CLI demos](../demos/README.md). The recordings predate 0.18.1; the pages above show current output.
