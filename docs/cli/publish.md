# `fluid publish`

Stage 10 of the 11-stage pipeline. Publish one or more contracts to one or more catalogs.

## Syntax

```bash
fluid publish CONTRACT_FILES [options]
```

`CONTRACT_FILES` supports one or more paths or glob patterns. With no `--target`, the contract goes to the FLUID Command Center. [The Command Center](../concepts/command-center.md) covers what is sent, the organization it goes to and who can see the product.

## Examples

### Single target

```bash
fluid publish contract.fluid.yaml --target command-center
```

### Publish an environment's overlay

```bash
fluid publish contract.fluid.yaml --target command-center --env aws
```

`--env aws` loads the contract with its overlay, as `fluid apply --env aws` does, so the catalog describes the `aws` binding. The environment is recorded on the Command Center asset as `metadata.fluid_env`. The value must be a plain environment name: letters, digits, `.`, `_` and `-`. See [Per-environment overlays](../recipes/per-environment-overlays.md).

### Multiple targets in one call

```bash
fluid publish contract.fluid.yaml \
  --target command-center \
  --target datamesh-manager
```

The publish report contains a per-target result block, so a partial failure (a DataHub authentication problem while Data Mesh Manager succeeded) is distinguishable from a full failure.

### Endpoint override (self-hosted catalogs)

```bash
fluid publish contract.fluid.yaml \
  --target fluid-command-center:https://cc.internal.example \
  --target datamesh-manager:https://dmm.internal.example
```

### Glob input

```bash
fluid publish customer-*.fluid.yaml --target datamesh-manager
```

### Dry-run preview

```bash
fluid publish contract.fluid.yaml --target datamesh-manager --dry-run
fluid publish contract.fluid.yaml --target command-center --dry-run --format json
```

## Key options

| Option | Description |
| --- | --- |
| `--target`, `-t` *(repeatable)* | Target catalog name, with an optional `:<endpoint>` suffix to override the catalog's URL for this target. Pass it more than once to publish to several catalogs. Default `fluid-command-center`. See [Target names](#target-names). |
| `--catalog`, `-c` | **Deprecated** alias for `--target`, single catalog only. Still registered in 0.18.1. Emits a warning; treat it as historical. |
| `--list-catalogs` | List configured catalogs. `CONTRACT_FILES` is still a required argument, so pass any contract path: `fluid publish contract.fluid.yaml --list-catalogs`. |
| `--dry-run` | Show what would be sent (request bodies, lookup and write routes, lineage edges) and make no network call. Secrets in headers are redacted. With `--format json` the preview is machine-readable. |
| `--verify-only` | Check whether a contract is already published; create nothing. |
| `--force` | Command Center only: record a contract version even when the stored contract hash says the contract is unchanged. See [Contract versions](#contract-versions). |
| `--env ENV` | Publish the contract with this environment overlay applied, as `fluid apply --env` loads it. An environment with no overlay logs `overlay_not_found` and runs on the base contract; [`--env` and environment overlays](./validate.md#env-and-environment-overlays) says when it fails instead. See [Environments and overlays](../concepts/environments-and-overlays.md#when-no-overlay-matches). |
| `--format`, `-f` | Output format: `text` (default), `json` or `yaml`. |
| `--verbose`, `-v` | Detailed output |
| `--quiet`, `-q` | Minimal output |
| `--skip-health-check` | Skip catalog health checks |
| `--show-metrics` | Show detailed metrics |
| `--auto-approve-access` | Data Mesh Manager only: approve generated Access agreements immediately, so lineage renders at once. Same as `DMM_AUTO_APPROVE_ACCESS=true`. For sandboxes. |

### Target names

| `--target` | Catalog |
| --- | --- |
| `fluid-command-center` (default), `command-center`, `fluid_cc` | FLUID Command Center |
| `datamesh-manager`, `datamesh_manager`, `dmm`, `entropy-data` | Data Mesh Manager (Entropy Data) |
| `datahub` | DataHub |
| `openmetadata` | OpenMetadata |

`command-center` is the spelling the CLI's own help and the generated pipelines use. The three Command Center names are aliases: a name with no config block of its own reads the `catalogs.fluid-command-center` block.

## Publishing to the FLUID Command Center

### Configure the endpoint, credential and organization

Set these in the environment, or under `catalogs.fluid-command-center` in a FLUID config file (for example `~/.fluid/config.yaml`, or `fluid.config.yaml` in the project):

| Setting | Environment variable | Config key |
| --- | --- | --- |
| Endpoint (default `http://localhost:8000`) | `FLUID_CC_ENDPOINT`, or `FLUID_CATALOG_FLUID_CC_URL` | `endpoint` |
| API key | `FLUID_API_KEY`, or `FLUID_CATALOG_FLUID_CC_TOKEN` | `auth.api_key` |
| Bearer token | `FLUID_BEARER_TOKEN`, with `auth.type: bearer` | `auth.token` |
| Organization id | `FLUID_CC_ORG_ID` | `organization_id` |
| Organization slug | | `organization` |

For the endpoint, API key and organization id, an environment variable wins over the config file. These variables belong to `fluid publish`. `FLUID_COMMAND_CENTER_URL` and `FLUID_COMMAND_CENTER_API_KEY` are different settings, read by [`fluid market`](./market.md) detection and by run reporting, so setting them does not change where `fluid publish` sends a contract. [`fluid apply`](./apply.md#reporting-to-the-command-center-since-0-17-0) reuses this Command Center configuration and organization to report its runs.

```yaml
# ~/.fluid/config.yaml
catalogs:
  fluid-command-center:
    endpoint: https://cc.internal.example
    auth:
      type: api_key
    organization: acme-data      # slug; an organization_id here, or FLUID_CC_ORG_ID, wins
```

### Which organization a product lands in

A product belongs to exactly one organization, so the write requests (asset lookup, create or update, contract sync) carry an `X-Organization-Id` header naming it. The organization is the first of:

1. `FLUID_CC_ORG_ID`, or `organization_id` in the config.
2. The organization whose slug is `organization` in the config, matched against `GET /api/v1/organizations`. An unknown or ambiguous slug writes nothing: it never falls back to another organization.
3. The credential's only organization, when `GET /api/v1/organizations` lists exactly one.

When none of these settles one organization, nothing is written and the result carries an `error_code`:

| `error_code` | Cause |
| --- | --- |
| `cc_organization_unresolved` | The credential belongs to no organization or to several, the slug matched none or several, or the organization list could not be read. The message lists the organizations, so you can pick an id. |
| `cc_organization_id_blank` | `FLUID_CC_ORG_ID` is set but empty, which usually means an empty CI parameter. It is refused instead of falling back, so a job whose binding came up empty cannot publish into another organization. Unset the variable to get the fallback on purpose. |
| `cc_credential_missing` | No API key or token is configured. |

`--verify-only` raises the same errors. `--dry-run` raises only the ones it can find without asking the server: a blank or malformed organization id.

### Visibility

A product is private unless the contract says it is public. `is_public` is `true` only when `metadata.classification` is `public`, or, with no `metadata.classification`, when every expose declares `public` through `policy.classification` or `sensitivity`. A contract that declares nothing, or any other label (`internal`, `confidential`, `restricted`), publishes a product only its organization can see.

### Contract versions

After the asset is written, each publish posts the contract to `/api/v1/contracts/sync`, with its git provenance: commit, branch, repository URL, the contract's path in the repository, and who deployed it. Commit, branch and URL come from `GIT_COMMIT`, `GIT_BRANCH` and `GIT_URL` when set, otherwise from the contract's own repository. `deployed_by` is `BUILD_TAG` when set, otherwise the OS user. Credentials are stripped from the repository URL, and a fact that cannot be read is left out, never guessed.

The post is skipped, with status `unchanged`, when the product's stored `contract_hash` already equals this contract's. `--force` records a new version anyway. If the post fails, the product and its lineage are written, a warning says so, and the next publish records the version.

### What is sent

`fluid publish` sends the fully resolved contract, one flattened document: the `$ref` fragments of a [fragment layout](../concepts/contract-refs.md) are composed first and are not published as separate files ([sharing a contract outside the CLI](../concepts/fragments.md#sharing-a-contract-outside-the-cli)). Run `fluid bundle` before handing a fragment root to anything that reads a single file, such as a Command Center upload. `{{ env.NAME }}` placeholders are resolved before sending, except those whose name looks like a credential (`..._PASSWORD`, `..._TOKEN`, `..._SECRET`, `..._API_KEY`), which stay literal.

### Dry-run preview

`--dry-run` prints the asset body, the contract-sync body and the lineage edges, with credentials replaced by `<redacted>`, and makes no network call. This is the `details` object of the `--format json` result for a contract published with `--env aws`, with some keys left out and long values trimmed with `...`:

```json
{
  "dry_run": true,
  "valid": true,
  "endpoint": "https://cc.example.com",
  "organization_id": "org-123",
  "organization": "configured",
  "headers": {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-API-Key": "<redacted>",
    "X-Organization-Id": "org-123"
  },
  "lookup": {
    "method": "GET",
    "path": "/api/v1/assets",
    "params": { "fluid_contract_id": "bronze.customer_subscriptions", "limit": 1 }
  },
  "asset_write": {
    "create": { "method": "POST", "path": "/api/v1/assets" },
    "update": { "method": "PATCH", "path": "/api/v1/assets/{asset_id}" },
    "body": {
      "name": "Customer subscriptions",
      "type": "dataproduct",
      "is_public": false,
      "metadata": {
        "fluid_contract_id": "bronze.customer_subscriptions",
        "platform": "aws",
        "classification": null,
        "fluid_env": "aws"
      },
      "contract_yaml": "fluidVersion: 0.7.5\n..."
    }
  },
  "contract_sync": {
    "method": "POST",
    "path": "/api/v1/contracts/sync",
    "body": { "asset_id": "{asset_id}", "fluid_version": "0.7.5", "contract_yaml": "..." },
    "skipped_when": "the existing product's contract_hash is already b97616e6..."
  },
  "lineage": { "declared_in": null, "edges": [] }
}
```

With no organization configured, `organization_id` is `null` and the header reads `<resolved at publish time>`: the dry run does not ask the server.

### One product per contract id

The Command Center keeps one product per contract. The lookup key is `metadata.fluid_contract_id`, so publishing the same contract again updates that product, whichever `--env` published it last. Publishing one contract from two environments, for example `aws` and `gcp`, makes the product's platform and location whatever the last publish sent. If your pipelines publish from more than one environment, decide which one publishes; [Publishing an environment, and last-writer-wins](../concepts/command-center.md#publishing-an-environment-and-last-writer-wins) has the detail. For a Jenkins pipeline, `fluid generate ci --no-publish-stage-default` leaves stage 10 off by default.

## Publishing to Data Mesh Manager (Entropy Data)

**Data Mesh Manager** (now Entropy Data) is one of the catalogs Fluid Forge publishes to. It has its own dedicated entry point so data products *and* data contracts can be published with the right payload shape:

```bash
fluid datamesh-manager publish CONTRACT   # or: fluid dmm publish CONTRACT
```

### Setup

| Env var | Required | Purpose |
| --- | --- | --- |
| `DMM_API_KEY` | Yes | API key. Generate at *Profile → Organization → Settings → API Keys*. |
| `DMM_API_URL` | No | Base URL override (default: `https://api.entropy-data.com`). |
| `DMM_ODPS_LINEAGE_MODE` | No | `contract` (default) uses Entropy Access agreements for product-to-product lineage; `source-system` is legacy compatibility mode. |
| `DMM_AUTO_APPROVE_ACCESS` | No | Set to `true` only when Access agreements should be approved automatically. |
| `DMM_ALLOW_INSECURE_HTTP` | No | Set to `true` only when intentionally publishing to a non-local HTTP endpoint. |

### Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--dry-run` | Validate and preview the API payload without publishing |
| `--with-contract` | Publish a companion data contract alongside the data product |
| `--team-id ID` | Override team-id resolution; auto-creates the team if it doesn't exist |
| `--data-product-spec VALUE` | Override the data product payload spec. Use `odps` for Entropy ODPS publishes. |
| `--odps-lineage-mode {contract,source-system}` | Choose ODPS lineage behavior. `contract` is the default. |
| `--auto-approve-access` | Approve generated Access agreements immediately. Intended for local sandboxes, not review-based production flows. |
| `--no-auto-approve-access` | Keep Access agreements pending even when `DMM_AUTO_APPROVE_ACCESS=true`. |
| `--validation-mode {warn,strict}` | Gate on pre-publish schema validation. `warn` (default) logs and continues; `strict` aborts on any violation. Both modes validate against the contract's **own** declared `fluidVersion`, so a 0.5.7 contract is validated against `fluid-schema-0.5.7.json`, a 0.7.2 contract against `fluid-schema-0.7.2.json`, and so on. Upgrading the CLI never invalidates a contract that was valid against its own version. |

### Examples

```bash
export DMM_API_KEY="..."
fluid dmm publish contract.fluid.yaml
fluid dmm publish contract.fluid.yaml --dry-run
fluid dmm publish contract.fluid.yaml --with-contract
fluid dmm publish contract.fluid.yaml --data-product-spec odps --odps-lineage-mode contract
fluid dmm publish contract.fluid.yaml --validation-mode strict
```

### What gets sent

- **Data product** via `PUT /api/dataproducts/{id}`, built from FLUID `metadata`, `exposes`, `consumes`.
- **Data contract** (optional, with `--with-contract`) via `PUT /api/datacontracts/{id}`: the ODCS v3.1.0 payload of the contract.
- **Access agreements** from product-to-product `consumes[]` entries. This is the default ODPS lineage path and prevents duplicated SourceSystem graph nodes.
- **Input / output ports** mapped from FLUID `consumes[]` / `exposes[]`. Product-to-product consumes are Access-only in ODPS mode; explicit source-system consumes remain input ports.
- **PII detection** from `schema[].sensitivity` / `classification` fields.
- **Multi-provider location** mapping: BigQuery, Snowflake, S3, Kafka, Redshift, and others.
- **Safe team bootstrap**: if DMM rejects team members because users do not exist yet, the provider retries team creation without `members` while keeping the contact email.
- Retries with backoff for transient failures (`429`, `5xx`).

For every flag and subcommand of the dedicated entry point, see [`fluid datamesh-manager`](./datamesh-manager.md).

### Catalog-adapter route

The same behavior is reachable through the generic catalog surface:

```bash
fluid publish contract.fluid.yaml --target datamesh-manager
```

Use the dedicated `fluid dmm publish` entry point when you want `--validation-mode`, `--with-contract` or `--odps-lineage-mode`. Use `fluid publish --target datamesh-manager` when you're treating DMM as one catalog among several behind a common interface. `--auto-approve-access` works on both.

## Notes

- A typical flow is `validate → plan → apply → verify → publish`.
- Use [`fluid market`](./market.md) to verify discoverability after publishing.
- `--target` is repeatable rather than comma-separated, for consistency with kubectl, helm and gh. The deprecated `--catalog a,b,c` form is not equivalent to `--target a --target b --target c`.
