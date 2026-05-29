# OpenMetadata Catalog

`v0.8.3` ships an **OpenMetadata** publish-side registrar — contracts can register themselves into an [OpenMetadata](https://open-metadata.org/) server at apply / publish time so the catalog reflects the data product alongside the underlying tables.

> **Recommended for:** teams running OpenMetadata as their data discovery / governance catalog, especially in stacks that already use OpenMetadata's lineage and glossary surfaces.

::: tip Publish-side only on this page
There is no source-side OpenMetadata read adapter on `v0.8.6` — `fluid forge data-model from-source` does not (yet) include OpenMetadata in the seven catalogs supported by the source-side flow. If you need to forge a contract *from* OpenMetadata metadata, open an issue and we'll prioritise the read adapter.
:::

## Opt in

```yaml
# contract.fluid.yaml
properties:
  catalog:
    register: [openmetadata]
```

## Environment variables

| Variable | Purpose |
|---|---|
| `FLUID_CATALOG_OPENMETADATA_URL` | OpenMetadata REST endpoint (e.g. `https://openmetadata.corp.example.com/api`). |
| `FLUID_CATALOG_OPENMETADATA_TOKEN` | OpenMetadata bearer token. |

The publish-side path uses the canonical SSRF-guarded HTTP client. See [network safety](/forge_docs/advanced/network-safety.html).

## What gets emitted

| Contract field | OpenMetadata entity |
|---|---|
| Output ports | `Table` per port (REST `PUT /v1/tables`) |
| Per-port schema | `Column` entries on the matching table |
| `metadata.layer` / `metadata.productType` | Extension fields on the table (canonical extension namespace) |
| `metadata.domain` | `Domain` (created if absent) |
| Tags / classifications | `Tag` entries surfaced via OpenMetadata's classification API |

The registrar writes are idempotent — re-publishing the same contract is a no-op against OpenMetadata.

## Verify a publish locally

```bash
export FLUID_CATALOG_OPENMETADATA_URL=https://openmetadata.local:8585/api
export FLUID_CATALOG_OPENMETADATA_TOKEN=$(cat ~/.openmetadata-pat)
fluid apply contract.fluid.yaml --yes
# → ... [publish] openmetadata: PUT /v1/tables (200)
```

If the registrar can't reach OpenMetadata, the publish step warns rather than fails the apply.

## See also

- [Catalog overview](./overview.md) — the unified publish-side flow
- [DataHub publish](./datahub.md#publishing-to-datahub) — the parallel registrar for DataHub
- [DMM publish](./datamesh-manager.md#publishing-to-data-mesh-manager) — the parallel registrar for Data Mesh Manager
- [OpenMetadata upstream docs](https://docs.open-metadata.org/) — for installing / configuring OpenMetadata itself
