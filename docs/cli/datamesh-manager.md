# `fluid datamesh-manager`

Publish FLUID data products and contracts to Entropy Data / Data Mesh Manager, and manage the products and teams stored there.

::: tip Not a provider
*(from 0.27.0)* Data Mesh Manager is a catalog, not an infrastructure provider. `--provider datamesh-manager` (or `datamesh_manager`) exits 2 with `Provider 'datamesh-manager' was retired: Data Mesh Manager is a catalog, not a provider; use fluid publish --target datamesh-manager (or fluid datamesh-manager)`. Publishing is unchanged: `fluid publish --target datamesh-manager` (aliases `entropy-data`, `dmm`) and this command.
:::

## Syntax

```bash
fluid datamesh-manager publish CONTRACT [options]
fluid datamesh-manager list [--format FMT]
fluid datamesh-manager get PRODUCT_ID
fluid datamesh-manager delete PRODUCT_ID [--yes]
fluid datamesh-manager teams [--format FMT]
fluid datamesh-manager list-contracts [--format FMT]
fluid datamesh-manager get-contract CONTRACT_ID
fluid datamesh-manager delete-contract CONTRACT_ID [--yes]
fluid datamesh-manager wipe [--yes] [--max-passes N]
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
| `--with-contract` | Also publish a companion data contract per expose. *(since 0.31.0, [forge-cli #914](https://github.com/Agenticstiger/forge-cli/pull/914))* No umbrella contract is sent, and every contract carries its expose's `version`. See [Contracts](#contracts-and-their-retirement). |
| `--no-create-team` | Do not auto-create the team if it is missing. |
| `--contract-format` | `odcs` (Open Data Contract Standard v3.1.0, default) or `dcs` (Data Contract Specification 0.9.3, deprecated). |
| `--data-product-spec` | Override `dataProductSpecification` value sent to Entropy Data (e.g. `odps` or `0.0.1`). |
| `--odps-lineage-mode` | `contract` (default) or `source-system`. `source-system` also writes `customProperties[sourceSystem]` (the upstream product id) on each consume's input port. `fluid publish --target datamesh-manager` ignores it and warns. *(since 0.31.0, [forge-cli #908](https://github.com/Agenticstiger/forge-cli/pull/908))* |
| `--auto-approve-access` | Automatically approve Access agreements generated from `consumes[]`. Use for local sandboxes only; production workflows should review Access separately. |
| `--no-auto-approve-access` | Keep Access agreements pending even when `DMM_AUTO_APPROVE_ACCESS=true` is set. Use it to override a sandbox-wide default for one publish. |
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

### `list-contracts`, `get-contract`, `delete-contract`

Manage companion data contracts published alongside data products.

| Option | Description |
| --- | --- |
| `CONTRACT_ID` | Data contract ID (as published via `--with-contract`). |
| `--format`, `-f` | (`list-contracts` only) Output format: `table` (default) or `json`. |
| `--yes`, `-y` | (`delete-contract` only) Skip confirmation prompt. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |

### `wipe`

Delete **every data product** in the configured DMM tenant. Data contracts are not deleted: remove those with `delete-contract`. Intended for local sandbox cleanup and CI teardown. Prompts for confirmation unless `--yes` is passed.

DMM refuses to delete a product that other products consume, so `wipe` works in passes: each pass deletes the products DMM accepts, and the products that were refused as in use go to the next pass. Consumers drain before their producers. It stops when nothing is left, when a pass makes no progress, or after `--max-passes`. When a pass makes no progress it names the consumers that block each remaining product. The command exits `0` when the tenant ends empty, and `1` when any product remains.

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation prompt. |
| `--max-passes N` | Maximum delete passes before giving up on products still in use. Default `8`. |
| `--api-key` | Entropy Data API key. |
| `--api-url` | API base URL. |

::: warning
`fluid dmm wipe` is **destructive** and irreversible against a live DMM instance. Only use it against local sandboxes or disposable test environments.
:::

## Examples

```bash
# Publish
fluid datamesh-manager publish contract.fluid.yaml --dry-run
fluid datamesh-manager publish contract.fluid.yaml --with-contract --validation-mode strict
fluid dmm publish contract.fluid.yaml --auto-approve-access

# Read / list
fluid dmm list --format json
fluid dmm list-contracts --format json
fluid dmm get-contract my-org.customer360-contract

# Delete
fluid dmm delete gold.customer360_v1 --yes
fluid dmm delete-contract my-org.customer360-contract --yes

# Delete every data product in a sandbox (local dev only!)
fluid dmm wipe --yes
fluid dmm delete-contract my-org.customer360-contract --yes   # contracts are separate
```

## Configuration

| Setting | Purpose |
| --- | --- |
| `DMM_API_KEY` | Required API key. |
| `DMM_API_URL` | API base URL. Defaults to `https://api.entropy-data.com`. |
| `DMM_ODPS_LINEAGE_MODE` | Optional default for ODPS lineage. `contract` (default) or `source-system`. `source-system` also writes `customProperties[sourceSystem]` (the upstream product id) on each consume's input port. `fluid publish --target datamesh-manager` ignores it and warns. *(since 0.31.0, [forge-cli #908](https://github.com/Agenticstiger/forge-cli/pull/908))* |
| `DMM_AUTO_APPROVE_ACCESS` | Set to `true` to auto-approve generated Access agreements. Keep unset for production review flows. |
| `DMM_ALLOW_INSECURE_HTTP` | Set to `true` only when intentionally sending credentials to a non-local HTTP endpoint. Localhost HTTP is allowed for local development. *(since 0.31.0, [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916))* This applies to `fluid publish --target datamesh-manager` too: see [Plain http](#plain-http-and-a-malformed-url). |

*(from 0.27.0)* The client refuses to follow a redirect to another origin, so the API key and the request body never leave the origin `DMM_API_URL` names. The command fails with `Refused to follow a redirect from the Entropy Data API: <reason>. The API key and request body were not sent there; if the API moved, update DMM_API_URL.` The reason names the origins. Set `DMM_API_URL` to the new address.

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

*(since 0.31.0, [forge-cli #908](https://github.com/Agenticstiger/forge-cli/pull/908))* Entropy Data draws a product-to-product edge from an input port's `contractId` alone, and merges it with an approved Access agreement for the same pair. Both publish paths, `fluid datamesh-manager publish` and `fluid publish --target datamesh-manager`, now send what Entropy reads:

- **Each `consumes[]` entry is an ODPS input port** that names the upstream's contract, `<productId>.<exposeId>`. Up to 0.30.1 both paths removed these ports and left the lineage to Access agreements. Those stay `requested` across teams, so a cross-team consume drew no edge. Two upstreams that share an `exposeId` keep distinct contract ids.
- **A build source's input port carries `customProperties[sourceSystemId]` and `customProperties[type]`.** That is the only shape Entropy links a SourceSystem by: its native `sourceSystemId` field is dropped on save. Before, every source-aligned product landed with its SourceSystem node and no edge to it. Only source systems the publish upserts are linked. *(since 0.31.0, [forge-cli #920](https://github.com/Agenticstiger/forge-cli/pull/920))* A consume's source system goes to the port built for that consume, matched by its `contractId`. Before, two upstreams that expose the same port name (`crm.accounts` and `erp.accounts`) gave the first port the second's source system and the renamed second port none, and a consume `name`d apart from its `exposeId` got none.
- **Stale Access agreements are cancelled.** An agreement that forge made (it carries `managedBy: forge-cli`) for a consume the contract no longer has is cancelled on publish, with `POST /api/access/<id>/cancel`. The end time is set ten minutes in the past, so that Entropy ends it now: an end time even slightly in the future keeps it active until Entropy's own sweep. Agreements are never deleted, and agreements a person made, or that are already cancelled or rejected, are left alone. This is best effort: a failed reconcile logs a warning and the publish still succeeds. Both paths send the same input ports and the same Access agreement ids.
- **A consumed product that Entropy holds twice** (as written, and under its slug, a stale copy of an older publish) is consumed under the slug, the live one. An unreadable product list now says so, where it read as an empty one. Two consumes that name one `contractId` with different `sourceSystem`s link neither, with a warning.

`--odps-lineage-mode source-system` also writes `customProperties[sourceSystem]`, the upstream product id, on each consume's input port; `contract` does not. `fluid publish --target datamesh-manager` ignores the mode and warns. The option and `DMM_ODPS_LINEAGE_MODE` are still accepted.

Seen on 0.31.0, with `fluid datamesh-manager publish --dry-run --with-contract` on a contract that consumes `silver.crm.core_v1.crm_core` and `silver.billing.accounts_v1.billing_accounts`. The product payload carries:

```json
"inputPorts": [
  {"name": "crm_core", "version": "1.0.0", "contractId": "silver.crm.core_v1.crm_core"},
  {"name": "billing_accounts", "version": "1.0.0", "contractId": "silver.billing.accounts_v1.billing_accounts"}
]
```

Access agreements are create-only by default. Use `--auto-approve-access`, `DMM_AUTO_APPROVE_ACCESS=true`, or catalog config `auto_approve_access: true` only when your environment intentionally auto-approves those agreements. `--no-auto-approve-access` forces pending agreements for one publish even when the environment variable is set.

Team creation is defensive: if the server rejects the initial team payload because member emails do not exist as DMM users yet, the provider retries team creation without `members` while preserving the contact email.

## Contracts and their retirement

*(since 0.31.0, [forge-cli #914](https://github.com/Agenticstiger/forge-cli/pull/914))* Entropy kept contracts nothing pointed at, and pointed at contracts nobody had. Both paths now keep the two in step:

- **A stale contract is retired.** Before the product is sent, the publish reads the product as Entropy holds it. A contract that its output ports named then, and no longer name (the expose was removed, say), is sent again with `status: retired`. It is never deleted. Only contracts in the product's own `<productId>.` namespace are forge's to retire, so a contract you pinned with `exposes[].contract.id` outside it, or one shared with another product, is never touched. A failure logs a warning, and the publish still succeeds.
- **No umbrella contract.** `--with-contract` used to send an empty contract at the bare product id that no port named. It no longer does, and an umbrella an earlier publish left (`customProperties[umbrella] = true`) is retired. A contract at the product id that is not marked as an umbrella is left alone.
- **A port names only a contract that exists.** Without `--with-contract`, an output port keeps its `contractId` only when Entropy has that contract and it is not retired. A 404 drops the reference, and any other read error keeps it. *(since 0.31.0, [forge-cli #920](https://github.com/Agenticstiger/forge-cli/pull/920))* With `--with-contract`, the native path sends the contracts before the product, and a port drops its `contractId` when that contract failed to render or send and Entropy does not have it.
- **`fluid publish --target datamesh-manager` honours a pinned id.** The contract goes to the id it names, which is the id its output port names. A pinned `exposes[].contract.id` used to go to `<productId>.<exposeId>`, so the port pointed elsewhere.
- **A per-expose ODCS contract carries its expose's `version`**, where it carried `1.0.0` whatever changed. FLUID has no product-level version, so a breaking change used to go out under the version it broke.

## The archetype

*(since 0.31.0, [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916))* Entropy reads a product's archetype from `customProperties[type]`, and only the kebab-case values `source-aligned`, `aggregate` and `consumer-aligned`. Up to 0.30.1 neither path sent it, so every product showed as a plain "Data Product". Both paths now send it, from, in order:

1. `metadata.archetype`, when set. A known value is spelled the kebab way Entropy reads it (`sourceAligned` is not recognised, so it is sent as `source-aligned`), and any other value goes as written.
2. `metadata.productType`: `SDP` is `source-aligned`, `ADP` is `aggregate`, `CDP` is `consumer-aligned`.
3. `metadata.layer`: Bronze is `source-aligned`, Silver `aggregate`, Gold `consumer-aligned`.

A legacy `metadata.type` (`analytical` or `operational`) used to go out as `customProperties[type]`, and so read as the archetype. When there is an archetype to send, it goes as `customProperties[fluidType]` now. The standalone ODPS artifact [`fluid odps`](./odps.md) writes is unchanged.

## The product id

*(since 0.31.0, [forge-cli #920](https://github.com/Agenticstiger/forge-cli/pull/920))* Entropy ids are case-sensitive: `CaseProbe.Mixed` is not `caseprobe.mixed`. Up to 0.30.1 `fluid datamesh-manager publish` published a product under a slug (lower case, with spaces and `/` as `-`), while `fluid publish --target datamesh-manager` and every consumer used the id as written. So a product `Silver.Sales.Orders` was published as `silver.sales.orders`, and its consumers' input ports and Access agreements named a product that did not exist. Both paths now slug the product's own id and every `consumes[].productId` the same way.

- **Exception:** an upstream that Entropy already holds under the id as written, such as a product forge did not publish (`Acme.Orders`), is consumed as written. Forge reads the product list only when an upstream id would change, never in a dry run.
- Pinned contract ids (`exposes[].contract.id`, `consumes[].contractId`) stay as written.
- A product the registrar published under a mixed-case id is published again under the lower-case one. The old product stays in Entropy until you delete it there.
- `fluid datamesh-manager get <id>` and `delete <id>` take the id as written, so a mixed-case argument gets a 404 for a product published under its slug. Pass the slug.

## Plain http and a malformed URL

*(since 0.31.0, [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916))* `fluid publish --target datamesh-manager` sent the API key in cleartext, in both `Authorization` and `x-api-key`, to any `http://` host. It now applies the rule `fluid datamesh-manager publish` has: plain http goes to a local host only, unless `DMM_ALLOW_INSECURE_HTTP=true`. The check runs before any request. Seen on 0.31.0:

```text
Refusing to send DMM credentials over plain HTTP to a non-local host ('example.com'). Use https:// or set DMM_ALLOW_INSECURE_HTTP=true intentionally.
```

*(since 0.31.0, [forge-cli #921](https://github.com/Agenticstiger/forge-cli/pull/921))* A malformed `DMM_API_URL` is refused as an invalid URL, without echoing it, where it raised a bare `ValueError`. Seen on 0.31.0, for `http://[::1]\@evil.com`:

```text
❌ Error: Invalid Data Mesh Manager API URL: it does not parse ('evil.com' does not appear to be an IPv4 or IPv6 address). Set DMM_API_URL to an http(s) URL.
```

## Settings `fluid publish` does not use

*(since 0.31.0, [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916))* `fluid publish --target datamesh-manager` publishes ODPS only, because Entropy rejects DPS 0.0.1. It warns, where it used to ignore them without a word, about `DMM_DATA_PRODUCT_SPECIFICATION` or `DMM_PROVIDER_HINT` set to anything but ODPS, and about `DMM_ODPS_LINEAGE_MODE`. Seen on 0.31.0:

```text
datamesh-manager data_product_specification='0.0.1' (DMM_DATA_PRODUCT_SPECIFICATION) is not used by fluid publish: it publishes ODPS, the only data product format Entropy Data accepts.
DMM_ODPS_LINEAGE_MODE is not used by fluid publish: lineage comes from the contract's consumes[] and build sources.
```

## Listing products

*(since 0.31.0, [forge-cli #916](https://github.com/Agenticstiger/forge-cli/pull/916))* Entropy pages `GET /api/dataproducts` at 1000 products. Both paths read only the first page, so on a tenant with more than 1000 products an upstream past it looked unpublished and its Access agreement was skipped, and `fluid datamesh-manager list` stopped at 1000. Every page is read now, up to 1000 pages.

## Notes

- The short alias `fluid dmm` is equivalent to `fluid datamesh-manager`.
- Before any publish, the loaded FLUID contract is validated against the schema matching its declared `fluidVersion`. `--validation-mode strict` aborts on errors; `--validation-mode warn` (the default) logs and proceeds.
- `--validate-generated-contracts` validates generated ODCS companion contracts before PUT. Use it with `--validation-mode strict` when generated catalog contracts should block publish.
- The `dcs` contract format is marked deprecated; prefer the default `odcs`.
- For local-only export to ODCS (no publish), see [`fluid odcs`](./odcs.md). For ODPS exports, see [`fluid odps`](./odps.md) and [`fluid odps-bitol`](./odps-bitol.md).
