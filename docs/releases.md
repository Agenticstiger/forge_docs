---
title: Releases
description: Every forge-cli release, newest first, with what changed and where the details and upgrade steps are.
---

# Releases

These docs are verified against CLI `0.29.0`. Moving to a newer CLI? See [Upgrading](./upgrading.md).
Each version links to its upgrade steps, its release notes, or the forge-cli CHANGELOG.

For what `fluid version`, `fluidVersion` and the schema versions mean, see [Understand the version numbers](./getting-started/README.md#understand-the-version-numbers).

| Version | Date | What changed |
| --- | --- | --- |
| [`0.30.1`](./upgrading.md#changes-in-0-30-1) | 2026-11-13 | `fluid validate --strict` no longer fails a dbt-built Databricks product. |
| [`0.30.0`](./upgrading.md#changes-in-0-30-0) | 2026-11-13 | Databricks Genie spaces for a data product or an estate, Unity Catalog keys, and quality monitoring. |
| [`0.29.0`](./upgrading.md#changes-in-0-29-0) | 2026-11-12 | Agent Skills for coding agents, plus an eval harness for them. |
| [`0.28.0`](./upgrading.md#changes-in-0-28-0) | 2026-11-06 | A Databricks product looks native in Unity Catalog. litellm, mcp and openlineage leave the base install. |
| [`0.27.0`](./upgrading.md#changes-in-0-27-0) | 2026-11-04 | Managed Flink to Iceberg as a 0.7.7 preview, with nested columns and one host rule. |
| [`0.26.0`](./upgrading.md#changes-in-0-25-0-and-0-26-0) | 2026-11-01 | Databricks (Unity Catalog) applies through OpenTofu; dbt builds run in the workspace. |
| [`0.25.0`](./upgrading.md#changes-in-0-25-0-and-0-26-0) | 2026-10-28 | A `$ref` can name any text file, and `fluid split --parts` chooses what moves out. |
| [`0.24.0`](./upgrading.md#changes-in-0-24-0) | 2026-10-27 | Exported ODPS lists each input contract, and ODCS `sql` quality rules become counting queries. |
| [`0.23.0`](./upgrading.md#changes-in-0-23-0) | 2026-10-27 | Exported ODCS and ODPS change shape (a Kafka `bigint` exports as `long`), and two DuckDB 2.x drift defects are fixed. |
| [`0.22.0`](./upgrading.md#changes-in-0-22-0) | 2026-10-22 | Runs on DuckDB 2.x as well as 1.5.x; `--strict` validation covers more. |
| [`0.21.0`](./upgrading.md#changes-in-0-21-0) | 2026-10-19 | Tighter YAML limits and an `engine: flink` preview (0.7.6). |
| [`0.20.0`](./upgrading.md#changes-in-0-20-0) | 2026-10-15 | Six security advisories fixed, each with its own upgrade notes. |
| [`0.19.0`](./upgrading.md#changes-in-0-19-0) | 2026-10-06 | A contract can say a principal reads a column masked, and which rows (schema 0.7.6). |
| [`0.18.2`](./RELEASE_NOTES_0.18.0.md#what-changed-in-0-18-2) | 2026-10-05 | `fluid diff` plans with a project named through an environment variable. |
| [`0.18.1`](./RELEASE_NOTES_0.18.0.md#what-changed-in-0-18-1) | 2026-10-05 | The drift gate reads a target whose binding names its project through an environment variable. |
| [`0.18.0`](./RELEASE_NOTES_0.18.0.md) | 2026-10-03 | A contract's `$ref` and SQL can no longer read outside its directory tree. |
| [`0.17.0`](./RELEASE_NOTES_0.17.0.md) | 2026-09-28 | One contract deploys to AWS and Google Cloud through `--env` overlays, governed the same on both. |
| [`0.16.7`](./RELEASE_NOTES_0.17.0.md) | 2026-09-28 | A Lake Formation grant that hides columns now applies on AWS, not only plans. |
| [`0.16.6`](./RELEASE_NOTES_0.17.0.md) | 2026-09-28 | A Lake Formation grant that hides columns now plans. |
| [`0.16.5`](./RELEASE_NOTES_0.17.0.md) | 2026-09-28 | AWS policies reach AWS, a chained product reads its `consumes[]`, and the drift gate reads OpenTofu state. |
| [`0.16.4`](./RELEASE_NOTES_0.17.0.md) | 2026-09-27 | A local data path named through an environment variable means the same file at every stage. |
| [`0.16.3`](./RELEASE_NOTES_0.17.0.md) | 2026-09-26 | The generated 11-stage pipeline runs as generated, and its gates check what they claim. |
| [`0.16.2`](./RELEASE_NOTES_0.16.0.md) | 2026-09-23 | Applying one contract to AWS and Google Cloud does what it says on both. |
| [`0.16.1`](./RELEASE_NOTES_0.16.0.md) | 2026-09-23 | The Docker image moves to Python 3.14. |
| [`0.16.0`](./RELEASE_NOTES_0.16.0.md) | 2026-09-23 | Generation can no longer write outside the output directory or inject code into Airflow DAGs. |
| [`0.15.3`](./RELEASE_NOTES_0.16.0.md) | 2026-09-15 | Error output stops linking to a documentation domain that belongs to someone else. |
| [`0.15.2`](./RELEASE_NOTES_0.16.0.md) | 2026-09-15 | Every typed error and catalogued event stops linking to a dead documentation domain. |
| [`0.15.1`](./RELEASE_NOTES_0.16.0.md) | 2026-09-15 | A front-door patch for fixes that landed on main after 0.15.0. |
| [`0.15.0`](./RELEASE_NOTES_0.15.0.md) | 2026-09-14 | Sovereignty enforcement: `sovereignty.enforcementMode` blocks, warns or informs as declared. |
| [`0.14.1`](./RELEASE_NOTES_0.15.0.md) | 2026-08-03 | The MCP output port works on both MCP SDK generations, and two authorisation bypasses close. |
| [`0.14.0`](./RELEASE_NOTES_0.14.0.md) | 2026-07-28 | Live-verification hardening: the dbt Iceberg loop reaches all three cloud warehouses. |
| [`0.13.1`](./RELEASE_NOTES_0.14.0.md) | 2026-07-26 | Two path-confinement security fixes and the dbt importer's product-boundary split. |
| [`0.13.0`](./RELEASE_NOTES_0.13.0.md) | 2026-07-18 | Verifiable autonomy and declarative packaging, with a wave of semantics fixes. |
| [`0.12.0`](./RELEASE_NOTES_0.12.0.md) | 2026-07-18 | dbt integration and schema 0.7.5 promoted to stable. |
| [`0.11.0`](./RELEASE_NOTES_0.11.0.md) | 2026-07-13 | The AI-ready and RAG surface: vector output port, semantic-drift guard, `ai_ready` agent. |
| [`0.10.2`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-06-27 | A polish and internal-quality release; no breaking changes. |
| [`0.10.1`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-06-27 | A bug-fix and security release on top of 0.10.0. |
| [`0.10.0`](./RELEASE_NOTES_0.10.0.md) | 2026-06-27 | Plugin governance: an operator trust boundary over plugins and a real plugin version gate. |
| [`0.9.0`](./RELEASE_NOTES_0.9.0.md) | 2026-06-25 | The streaming Kafka to Iceberg sink. |
| [`0.8.11`](./RELEASE_NOTES_0.8.11.md) | 2026-06-16 | Pluggable metadata sources and modeling techniques for `fluid forge data-model`. |
| [`0.8.10`](./RELEASE_NOTES_0.8.10.md) | 2026-06-08 | `fluid describe --self`, opt-in usage telemetry and diffs before refine writes. |
| [`0.8.9`](./RELEASE_NOTES_0.8.9.md) | 2026-06-01 | Keyless contract authoring through local AI coding agents. |
| [`0.8.8`](./RELEASE_NOTES_0.8.8.md) | 2026-05-31 | On-demand OpenTofu with `--ensure-opentofu`, and real catalog discovery in `fluid market`. |
| [`0.8.7`](./RELEASE_NOTES_0.8.7.md) | 2026-05-30 | Schema 0.7.4 made backward-compatible with 0.7.3, and stale version fallbacks fixed. |
| [`0.8.6`](./RELEASE_NOTES_0.8.6.md) | 2026-05-29 | The `fluid mcp` gateway enforces `agentPolicy` at runtime with JWT-bearer identity. |
| [`0.8.5`](./RELEASE_NOTES_0.8.5.md) | 2026-05-28 | Agentic uplift: LiteLLM fallback, a judge gate, a PII classifier and `fluid agents`. |
| [`0.8.4`](./RELEASE_NOTES_0.8.4.md) | 2026-05-26 | A fuller `fluid dmm` command surface and better lineage. |
| [`0.8.3`](./RELEASE_NOTES_0.8.3.md) | 2026-05-25 | ODCS and Bitol ODPS provider, unified catalog registry and the OpenTofu autogenerator. Also: [Catalog integration](./advanced/v1.5-release-notes.md). |
| [`0.8.3rc1`](./RELEASE_NOTES_0.8.3.md#what-was-already-in-v0-8-3rc1-graduates-to-stable-here) | 2026-05-12 | Pre-release of 0.8.3: plugin extension points and the acquisition-pattern engine. |
| [`0.8.2`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-05-10 | Beta of the acquisition-pattern engine runners and the EngineRuntime registry. |
| [`0.8.0`](./RELEASE_NOTES_0.8.0.md) | 2026-04-25 | `fluid compile` becomes `fluid bundle --format yaml`; policy commands move under `fluid policy`. |
| [`0.7.11`](./RELEASE_NOTES_0.7.11.md) | 2026-04-16 | Tooling release: a refactored release pipeline and packaging fixes. |
| [`0.7.9`](./RELEASE_NOTES_0.7.9.md) | 2026-04-06 | Smart first-run recovery in `fluid forge`, and a self-contained `fluid doctor`. |
| [`0.7.8`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-04-03 | A Windows timeout fix and a version-consistency fix. |
| [`0.7.7`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-04-01 | A modular Forge copilot with declarative domain agents and project memory. |
| [`0.7.6`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2026-03-31 | Data Mesh Manager payload conformance fixes and ODCS v3.1.0 support. |
| [`0.7.1`](./RELEASE_NOTES_0.7.1.md) | 2026-01-30 | Multi-provider Airflow, Dagster and Prefect generators. |
| [`0.5.7`](https://github.com/Agenticstiger/forge-cli/blob/main/CHANGELOG.md) | 2025-08-15 | The initial public release: `validate`, `plan`, `apply` and the BigQuery provider. |
