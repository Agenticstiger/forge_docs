# Publishing to a Catalog — Overview

`v0.8.3` consolidated catalog publishing under one registry. Contracts opt in via a single key in `properties.catalog.register`; the matching registrar is constructed from environment configuration at apply / publish time. Three publish-side backends are active today.

> Looking for **source-side** catalog *reading* (forge a contract from existing catalog metadata)? That's a different flow — see the [catalog index](./README.md) for the `fluid forge data-model from-source` adapters (Snowflake, Databricks Unity, BigQuery, Dataplex, AWS Glue, DataHub, Data Mesh Manager).

## Opting a contract in

Add `register` to your contract's `properties.catalog` block:

```yaml
# contract.fluid.yaml
properties:
  catalog:
    register: [datahub, datamesh_manager]    # one or more publish-side backends
```

That's the entire contract-side surface. The `acquisitionCatalog` schema block carries only target *names* (it's `additionalProperties: false`) — endpoints, tokens, and other deployment config are read from the environment.

## Active publish-side backends

| Backend | Reference | Notes |
|---|---|---|
| `datahub` | [Publishing to DataHub](./datahub.md#publishing-to-datahub) | DataHub GMS REST + MCP. Emits `DataProduct` + `Domain` + `Datasets` + `DataContract` with full schema, ownership, tags, descriptions. The `fluid.layer` and `fluid.productType` structured properties, and the `fluid_layer`, `fluid_product_type`, `fluid_domain` and `fluid_version` custom properties, surface the medallion classification. |
| `openmetadata` | [Publishing to OpenMetadata](./openmetadata.md) | OpenMetadata REST (Tables + extension fields). |
| `datamesh_manager` | [Publishing to Data Mesh Manager](./datamesh-manager.md#publishing-to-data-mesh-manager) | Bidirectional. `PUT /api/dataproducts/{id}` in ODPS + `PUT /api/datacontracts/{product_id}.{expose_id}` in ODCS per asset. Emits proper `SourceSystem` lineage links (Phase 1 of the DMM flow); per-port `contractId` resolves to a sibling ODCS contract. |

## How dispatch works

The publish stage (`build_runners/_catalog.py`) reads `properties.catalog.register` from the contract, calls `build_registrar(target)` for each entry to construct the registrar from env config, and pushes a uniform `CatalogPublicationPayload` to every backend. The shared payload shape means a contract that publishes cleanly to one backend publishes cleanly to all.

## Retired registrars — Glue + Snowflake Horizon

The previously-shipped `glue` and `snowflake_horizon` publish-side registrars were retired in `v0.8.3` (PR #140). The same metadata they used to push at publish time (table descriptions, per-column comments, FLUID classification tags, contract YAML) is now folded into the **IaC layer** and emitted into `aws_glue_catalog_table` and `snowflake_table` resources directly:

- One source of truth (the contract → IaC pipeline owns the catalog metadata along with the table itself).
- Drift detection comes free from `tofu plan`.
- No more out-of-band registrar writes fighting IaC state.

Contracts that still list `glue` or `snowflake_horizon` under `properties.catalog.register` will get a "not configured" result from `build_registrar`. The migration is:

1. Drop `glue` / `snowflake_horizon` from `properties.catalog.register`.
2. Run `fluid apply` against the cloud provider as usual — `aws` / `gcp` / `snowflake` providers auto-route through OpenTofu, which now owns the catalog metadata. See [`fluid generate iac`](../generate-iac.md) for the emit-and-review path.
3. `aws_glue_catalog_table.parameters` and `snowflake_table` comments now carry the same metadata.

## Databricks Unity Catalog

A Databricks Unity Catalog **read** adapter still exists under `fluid_build/copilot/catalog/unity.py` and powers `fluid forge data-model from-source --source unity` (see the [Unity catalog adapter page](./unity.md)). The publish-side Unity registrar was dropped — the OSS Unity Catalog server's strict `v0.4+` table-create validation made round-tripping the canonical payload too fragile for a generic publish path. Databricks-hosted UC remains addressable via the upstream Databricks SDK if needed.

## See also

- [`fluid publish`](../publish.html) — the user-facing publish command
- [Source-side catalog index](./README.md) — forge contracts *from* catalog metadata
- [Network safety](/forge_docs/advanced/network-safety.html) — SSRF posture on catalog HTTP calls
- [`fluid generate iac`](../generate-iac.md) — the IaC layer that absorbed Glue + Snowflake Horizon metadata
