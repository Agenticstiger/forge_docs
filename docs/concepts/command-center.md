---
title: The CLI and the Command Center
description: What fluid publish and fluid apply send to a FLUID Command Center, how the organization is chosen, and how to turn reporting off.
---

# The CLI and the Command Center

The FLUID Command Center is a web control plane that keeps a catalog of data
products and a history of their runs. The CLI talks to one in two places:

| Command | Sends | When |
|---|---|---|
| [`fluid publish`](../cli/publish.md) | The product (an asset), its contract version, and git provenance | A publish to the `fluid-command-center` target, the default target |
| [`fluid apply`](../cli/apply.md) | A record of the run: what was applied, where, and how it ended | An apply, once a Command Center credential is configured (since 0.17.0), subject to [When it reports](#when-it-reports) |

Both use the same configuration: an endpoint, a credential, and the
organization the product belongs to.

## Example

Point the CLI at a Command Center and preview a publish. `--dry-run` resolves
the configuration and prints the requests it would make, with the credential
redacted, and makes no network call. Read the API key from a secret store, so it
is not typed into your shell history (`vault` stands for any secret store):

```console
$ export FLUID_CC_ENDPOINT=https://cc.example.com
$ export FLUID_API_KEY="$(vault kv get -field=api_key <secret-path>)"
$ fluid publish contract.fluid.yaml --dry-run --format json
📤 Publishing 1 contract(s) to 1 target(s): fluid-command-center
[
 {
  "success": true,
  "catalog_id": "fluid-command-center",
  "asset_id": "gold.customer.analytics_360_v1",
  ...
  "details": {
   "dry_run": true,
   ...
   "organization_id": null,
   "organization": "the credential's only organization, from GET /api/v1/organizations at publish time",
   "headers": {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-API-Key": "<redacted>",
    "X-Organization-Id": "<resolved at publish time>"
   },
   "lookup": { "method": "GET", "path": "/api/v1/assets",
               "params": { "fluid_contract_id": "gold.customer.analytics_360_v1", "limit": 1 } },
   "asset_write": {
    "create": { "method": "POST", "path": "/api/v1/assets" },
    "update": { "method": "PATCH", "path": "/api/v1/assets/{asset_id}" },
    "body": { "name": "Customer 360 Analytics", "type": "dataproduct", "is_public": false, ... }
   },
   "contract_sync": { "method": "POST", "path": "/api/v1/contracts/sync", ... },
   "lineage": { "declared_in": "consumes", "edges": [ ... ] },
   "summary": "dry run: POST (or PATCH) /api/v1/assets with is_public=false, then POST /api/v1/contracts/sync; 3 upstream lineage edge(s)"
  }
 }
]
```

Drop `--dry-run` to publish. With a credential that belongs to one
organization, the CLI picks it and says so:

```console
$ fluid publish contract.fluid.yaml
📤 Publishing 1 contract(s) to 1 target(s): fluid-command-center
Publishing into Command Center organization sales (org-1), the only one this credential belongs to
Sending asset_data with 10 metadata keys
Creating new asset for contract: gold.customer.analytics_360_v1
✅ Published Customer 360 Analytics to Command Center (attempt 1/3, 0.74s)
...
```

From then on, `fluid apply` runs from the same configuration are reported too
(see [When it reports](#when-it-reports) for the exceptions), and ends with one line about it:

```console
$ fluid apply contract.fluid.yaml --yes
...
✅ Data product deployed successfully
...
  command center: run f972d32e-005b-4087-b123-f847927d67ef reported
```

The outputs on this page were captured against a local stand-in that records
requests, not a real Command Center.

## Configuration

| Setting | Environment variable | `fluid.config.yaml` key |
|---|---|---|
| Endpoint | `FLUID_CC_ENDPOINT` | `catalogs.fluid-command-center.endpoint` |
| API key, sent as `X-API-Key` | `FLUID_API_KEY` | `catalogs.fluid-command-center.auth.api_key` |
| Bearer token, sent as `Authorization: Bearer` | `FLUID_BEARER_TOKEN` | `auth.type: bearer` and `auth.token` |
| Organization id | `FLUID_CC_ORG_ID` | `catalogs.fluid-command-center.organization_id` |
| Organization slug | (none) | `catalogs.fluid-command-center.organization` |

Environment variables win over files. Of the files, a project file in the
current directory (the first of `.fluidrc.yaml`, `.fluidrc`,
`fluid.config.yaml`, `.fluid/config.yaml`) wins over a user file (the first of
`~/.fluidrc.yaml`, `~/.fluidrc`, `~/.fluid/config.yaml`,
`~/.config/fluid/config.yaml`), which wins over `/etc/fluid/config.yaml`.
`${VAR}` references in catalog values are expanded. A committed project config
can name the organization by slug, which stays the same across Command Center
deployments where ids do not:

```yaml
# fluid.config.yaml
catalogs:
  fluid-command-center:
    endpoint: https://cc.example.com
    organization: finance
```

::: warning Keep the credential out of the repository, and the configuration under review
- In CI, set `FLUID_CC_ENDPOINT`, `FLUID_CC_ORG_ID` and `FLUID_API_KEY` in the
  job's environment. Environment variables win over every file, so the job
  decides where it reports and with which credential.
- Set `FLUID_COMMAND_CENTER_ENABLED=false` in jobs whose applies should not be
  reported. It does not affect `fluid publish`.
- Treat `fluid.config.yaml`, `.fluidrc*` and `.fluid/config.yaml` in a
  repository like code: they set the endpoint and the organization, so put them
  under CODEOWNERS and review every change.
- Never commit a literal `auth.api_key`. Write `${FLUID_API_KEY}` and supply the
  value from the job's secret store.
- Run `fluid apply` and `fluid publish` with Command Center reporting only on
  checkouts you trust.
:::

`--target fluid-command-center`, `--target command-center` and
`--target fluid_cc` are the same target. `--target command-center:<url>`
overrides the endpoint for one call.

## Choosing the organization

Each request after the organization lookup carries an `X-Organization-Id`
header. The CLI settles the organization once per run, in this order:

1. `organization_id` from the configuration, or `FLUID_CC_ORG_ID`.
2. `organization` (a slug), matched against the organizations the credential
   belongs to.
3. The credential's only organization, from `GET /api/v1/organizations`.

When none of these gives exactly one organization, nothing is written and the
publish fails with exit code `1`:

```console
$ fluid publish contract.fluid.yaml
📤 Publishing 1 contract(s) to 1 target(s): fluid-command-center
❌ The Command Center credential belongs to 2 organizations and none was chosen: sales (id org-1), finance (id org-2). Set FLUID_CC_ORG_ID=<id> or catalogs.fluid-command-center.organization_id to pick one.
```

| Situation | Result |
|---|---|
| Credential in several organizations, none named | Refused (`cc_organization_unresolved`), lists the slugs and ids |
| Credential in no organization | Refused (`cc_organization_unresolved`) |
| `FLUID_CC_ORG_ID` set but empty | Refused (`cc_organization_id_blank`). An empty CI parameter does not fall back to the credential's only organization |
| Slug that no organization, or more than one, carries | Refused, lists the credential's organizations |
| No credential configured | Refused (`cc_credential_missing`) instead of sending the organization lookup without one |

```console
$ FLUID_CC_ORG_ID= fluid publish contract.fluid.yaml
...
│ gold.customer.analytics_360_v1 │ ❌ Failed │ fluid_cc │ FLUID_CC_ORG_ID is set but blank, so no Command Center organization was │
│                                │           │          │ chosen and nothing was written. Set it to the id of the organization    │
│                                │           │          │ to publish into, or unset it to use                                     │
│                                │           │          │ catalogs.fluid-command-center.organization_id or the only organization  │
│                                │           │          │ the credential belongs to.                                              │
```

## What `fluid publish` sends

A publish makes these requests, in order:

1. `GET /api/v1/assets?limit=1`: a reachability check (skip it with
   `--skip-health-check`).
2. `GET /api/v1/organizations`, only when no organization id is configured.
3. `GET /api/v1/assets?fluid_contract_id=<contract id>`: is this contract
   already a product?
4. `POST /api/v1/assets` for a new product, or `PATCH /api/v1/assets/<id>` for
   an existing one.
5. `POST /api/v1/contracts/sync`: records the contract version.

The asset body carries the contract's `name`, `description`, `domain`,
`metadata.layer`, `metadata.owner`, `metadata.tags` and classification, the
platform, location and schema of the **first** expose, the contract YAML, and
`metadata.fluid_contract_id`, the contract `id` the product is found by. As of
0.18.1 the asset `version` is always `1.0.0`: it is read from a top-level
`version` key that the contract schema does not have, and `exposes[].version`
is not used.

**Visibility comes from the contract.** `is_public` is `true` only when the
contract is classified `public`: `metadata.classification: public`, or, when
that is not set, every expose's `policy.classification` (or legacy
`sensitivity`) says `public`. Any other label, or none, publishes a product
only its organization can see.

**Contract versions.** The `contracts/sync` request records the contract YAML,
its `fluidVersion`, and where it came from: `git_commit_sha`, `git_branch`,
`git_repo_url` (with credentials removed) and `git_file_path`, read from
Jenkins' `GIT_*` variables or the contract's own repository, and
`deployed_by`, Jenkins' `BUILD_TAG` or the OS user. A fact that cannot be read
is left out. When the Command Center already holds the same contract version
(same `contract_hash`), no new version is recorded; `--force` records one
anyway. A failed sync is logged as a warning and does not fail the publish,
whose asset write has already succeeded.

**Lineage.** The Command Center derives product-to-product edges from the
contract's `consumes[]`. `--dry-run` shows the edges it will derive.

### Publishing an environment, and last-writer-wins

`--env <name>` publishes the contract with that environment's overlay applied,
the way `fluid apply --env <name>` loads it, and records the environment as
`metadata.fluid_env`:

```bash
fluid publish contract.fluid.yaml --target command-center --env staging
fluid publish contract.fluid.yaml --target command-center --env prod
```

The Command Center keeps **one product per contract id**. Both commands above
update the same product: the second `PATCH` replaces the platform, location
and `fluid_env` the first one wrote. Publishing one contract from two
environments, or from two clouds, leaves the product describing whichever
published last. A pipeline that deploys one contract to several clouds should
publish from one of them. In a Jenkins pipeline generated by
[`fluid generate ci`](../cli/generate.md#fluid-generate-ci), the publish stage
is off by default (`--no-publish-stage-default`); generate the pipeline for the
publishing cloud with `--publish-stage-default`.

## What `fluid apply` reports

Since 0.17.0, `fluid apply` records each run in the Command Center:
`POST /api/v1/executions` registers it, and `PATCH /api/v1/executions/<id>`
closes it as `success` or `failed`.

### When it reports

| Configuration | Result |
|---|---|
| A publish configuration with a credential (above) | Reported, with the organization `fluid publish` would use |
| Same, but the organization cannot be settled | Not reported: `command center: run not reported (the Command Center organization could not be settled (CommandCenterOrganizationError))` |
| `FLUID_COMMAND_CENTER_URL` and `FLUID_COMMAND_CENTER_API_KEY` only | Reported. `X-Organization-Id` is sent only when `FLUID_CC_ORG_ID` is set; without it, as of 0.18.1, the run is sent with no organization |
| `FLUID_COMMAND_CENTER_ENABLED` set to `false`, `0`, `no` or `off` | Not reported: `command center: run not reported (FLUID_COMMAND_CENTER_ENABLED is off)` |
| No endpoint with a credential | Not reported, and nothing is printed |

The endpoint must pass the SSRF host check: loopback, or a public address, or a
host listed in `FLUID_COMMAND_CENTER_HOST_ALLOWLIST`. A private or
cloud-metadata address is refused.

### What it sends

| Field | Value |
|---|---|
| `command`, `runner`, `cli_version`, `python_version` | `apply`; `jenkins` when `JENKINS_URL` is set, else `cli` |
| `contract_path`, `environment`, `metadata.mode` | As passed on the command line |
| `metadata.product_id`, `product_name`, `fluid_version` | From the contract. `contract_version` is read from a top-level `version` key the schema does not have, so as of 0.18.1 it is empty |
| `metadata.contract_hash` | The hash the Command Center keys contract versions by |
| `provider`, `metadata.platform`, `metadata.state` | The provider and the OpenTofu state location |
| `result.planned_changes`, `result.applied_changes` | `add`, `change` and `remove` counts |
| `result.resources` | The address of each resource the OpenTofu module declares |
| `result.builds[]` | For `--mode amend-and-build` or `replace-and-build`: each build's id and outcome, and from its run record the run id, loaded table, destinations and rows |
| `result.exit_code`, timings, `error_event`, `current_phase` | How and when the run ended; a failure is named by its typed event, such as `build_failed:<build id>` |

The contract hash, provider, state, change counts and resource addresses come
from the OpenTofu engine, which `aws`, `gcp`, `snowflake` and `confluent` apply
through. A run on the `local` engine reports the product's identity, exit code
and timings:

```json
{"execution_id": "f972d32e-...", "command": "apply", "contract_path": "contract.fluid.yaml",
 "provider": null, "environment": null, "status": "running", "runner": "cli",
 "cli_version": "0.18.1", "python_version": "3.11.15",
 "metadata": {"product_id": "gold.customer.analytics_360_v1",
              "product_name": "Customer 360 Analytics", "fluid_version": "0.7.5",
              "environment": null, "mode": null}}
```

**Not sent:** credentials, request headers, environment variable values, and
OpenTofu output, whose text can carry attribute values. The contract body is
not part of a run report; `fluid publish` is what sends the
contract.

### Best effort

A Command Center that is down, slow or refusing costs the apply a warning and
a bounded wait, never its exit code:

```console
$ fluid apply contract.fluid.yaml --yes
...
Failed to send event to Command Center: POST /api/v1/executions -> ConnectionError
Failed to send event to Command Center: PATCH /api/v1/executions/f0ee855e-1c14-4b50-8749-6a3d7c508aa0 -> ConnectionError
Command Center reporter stopped
  command center: run f0ee855e-1c14-4b50-8749-6a3d7c508aa0 not fully reported (0 of 2 requests accepted); the apply's result is unaffected
$ echo $?
0
```

To stop reporting while keeping `fluid publish` configured:

```bash
export FLUID_COMMAND_CENTER_ENABLED=false
```

## Related

- [`fluid publish`](../cli/publish.md): the publish options, and the other
  catalog targets.
- [`fluid apply`](../cli/apply.md): apply modes and safety gates.
- [Environment variables](../advanced/environment-variables.md#fluid-command-center)
- [Per-environment overlays](../recipes/per-environment-overlays.md): what
  `--env` loads.
