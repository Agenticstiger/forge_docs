# `fluid datamesh-manager`

Publish FLUID data products and contracts to Entropy Data / Data Mesh Manager, and manage the products and teams stored there.

## Syntax

```bash
fluid datamesh-manager publish CONTRACT [options]
fluid datamesh-manager list [--format FMT]
fluid datamesh-manager get PRODUCT_ID
fluid datamesh-manager delete PRODUCT_ID [--yes]
fluid datamesh-manager teams [--format FMT]
```

A short alias `fluid dmm` is registered for the same command group.

## Key options

### `publish`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--overlay`, `-o` | Path to overlay file. |
| `--team-id` | Team ID. Default derived from contract owner. |
| `--dry-run` | Preview the request payload without publishing. |
| `--with-contract` | Also publish a companion data contract per expose. |
| `--no-create-team` | Do not auto-create the team if it is missing. |
| `--contract-format` | `odcs` (Open Data Contract Standard v3.1.0, default) or `dcs` (Data Contract Specification 0.9.3, deprecated). |
| `--data-product-spec` | Override `dataProductSpecification` value sent to Entropy Data (e.g. `odps` or `0.0.1`). |
| `--odps-lineage-mode` | `contract` (default) publishes product-to-product dependencies as Entropy Access agreements; `source-system` enables legacy SourceSystem compatibility for retained ODPS input ports. |
| `--auto-approve-access` | Automatically approve Access agreements generated from `consumes[]`. Use for local sandboxes only; production workflows should review Access separately. |
| `--validate-generated-contracts` | Validate generated ODCS contracts locally before PUT. |
| `--validation-mode` | `warn` (default; logs and continues) or `strict` (fails on invalid contracts). |
| `--fail-on-contract-error` | Exit non-zero if any ODCS contract publish fails. |
| `--api-key` | Entropy Data API key. Falls back to `DMM_API_KEY` env var. |
| `--api-url` | API base URL. Default `https://api.entropy-data.com`. |

### `list`, `teams`

| Option | Description |
| --- | --- |
| `--format`, `-f` | Output format: `table` (default) or `json`. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |

### `get`, `delete`

| Option | Description |
| --- | --- |
| `PRODUCT_ID` | Data product ID. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |
| `--yes`, `-y` | (`delete` only) Skip confirmation prompt. |

## Examples

```bash
fluid datamesh-manager publish contract.fluid.yaml --dry-run
fluid datamesh-manager publish contract.fluid.yaml --with-contract --validation-mode strict
fluid dmm list --format json
fluid dmm delete gold.customer360_v1 --yes
```

## Configuration

| Setting | Purpose |
| --- | --- |
| `DMM_API_KEY` | Required API key. |
| `DMM_API_URL` | API base URL. Defaults to `https://api.entropy-data.com`. |
| `DMM_ODPS_LINEAGE_MODE` | Optional default for ODPS lineage: `contract` or `source-system`. |
| `DMM_AUTO_APPROVE_ACCESS` | Set to `true` to auto-approve generated Access agreements. Keep unset for production review flows. |
| `DMM_ALLOW_INSECURE_HTTP` | Set to `true` only when intentionally sending credentials to a non-local HTTP endpoint. Localhost HTTP is allowed for local development. |

The generic catalog adapter accepts the same behavior through `~/.fluid/config.yaml`:

```yaml
catalogs:
  datamesh-manager:
    endpoint: https://api.entropy-data.com
    auth:
      api_key: ${DMM_API_KEY}
    data_product_specification: odps
    provider_hint: odps
    odps_lineage_mode: contract
    auto_approve_access: false
```

## ODPS lineage and Access agreements

For ODPS publishes, product-to-product `consumes[]` entries are not kept as ODPS `inputPorts` by default. They become Entropy Access agreements from the upstream data product/output port to the consuming data product.

That default avoids duplicated lineage nodes: upstream data products stay data products, and are not mirrored as SourceSystem objects just to satisfy older ODPS importer behavior.

Use `--odps-lineage-mode source-system` only for legacy DMM deployments that explicitly require SourceSystem custom properties on retained ODPS input ports. Explicit source-system consumes authored in the FLUID contract are still preserved as source-system input ports in the default `contract` mode.

Access agreements are create-only by default. Use `--auto-approve-access`, `DMM_AUTO_APPROVE_ACCESS=true`, or catalog config `auto_approve_access: true` only when your environment intentionally auto-approves those agreements.

Team creation is defensive: if the server rejects the initial team payload because member emails do not exist as DMM users yet, the provider retries team creation without `members` while preserving the contact email.

## Notes

- The short alias `fluid dmm` is equivalent to `fluid datamesh-manager`.
- Before any publish, the loaded FLUID contract is validated against the schema matching its declared `fluidVersion`. `--validation-mode strict` aborts on errors; `--validation-mode warn` (the default) logs and proceeds.
- `--validate-generated-contracts` validates generated ODCS companion contracts before PUT. Use it with `--validation-mode strict` when generated catalog contracts should block publish.
- The `dcs` contract format is marked deprecated; prefer the default `odcs`.
- For local-only export to ODCS (no publish), see [`fluid odcs`](./odcs.md). For ODPS exports, see [`fluid odps`](./odps.md) and [`fluid odps-bitol`](./odps-bitol.md).
