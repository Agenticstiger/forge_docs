# `fluid validate`

Validate a contract against FLUID schema rules and provider-aware checks.

> **Why it matters**
> A breaking change surfaces in code review, not at 2am — trust becomes something you check on every commit.
> `fluid validate` checks the contract against the bundled JSON-Schema plus provider- and policy-aware rules before anything is planned or applied.

## Syntax

```bash
fluid validate CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--schema-version` | Validate against a specific schema version |
| `--min-version` | Minimum acceptable schema version |
| `--max-version` | Maximum acceptable schema version |
| `--strict` | Treat warnings as errors |
| `--offline` | Use only cached or bundled schemas |
| `--force-refresh` | Refresh cached schemas |
| `--clear-cache` | Clear schema cache first |
| `--cache-dir CACHE_DIR` | Custom schema cache directory |
| `--verbose`, `-v` | Detailed validation output |
| `--quiet`, `-q` | Minimal output |
| `--format` | `text` or `json` |
| `--list-versions` | List available schema versions |
| `--show-schema` | Show the schema used for validation |
| `--probe` | Run live external connectivity probes for sources / sinks declared in `acquisition` builds. |
| `--report PATH` | Write the structured validation report to a file (in addition to stdout) |

## Examples

```bash
fluid validate contract.fluid.yaml
fluid validate contract.fluid.yaml --env prod
fluid validate contract.fluid.yaml --strict
fluid validate contract.fluid.yaml --schema-version 0.7.2
fluid validate contract.fluid.yaml --verbose --show-schema
```

## `--probe` — live external connectivity checks

::: tip Available in 0.8.3
`--probe` ships in `0.8.3` as part of schema 0.7.3 acquisition support.
:::

By default `fluid validate` is **pure schema validation** — no network. Set `--probe` to additionally test connectivity for every source / sink declared in `acquisition` builds:

```bash
fluid validate contract.fluid.yaml --probe
```

What it checks:

- **Postgres / MySQL / SQLite sources** — connect, run a no-op query, drop the connection
- **Filesystem sources** — readable, files exist
- **S3 / GCS sinks** — bucket exists, current creds can `ListObjects`
- **Airbyte / Kafka Connect endpoints** — health check on the cluster URL
- **Debezium connectors** — Kafka cluster reachable

Probe failures emit `ConnectivityProbeError` ([typed CLI errors](/forge_docs/advanced/typed-cli-errors.html#connectivity-secrets)) with the source coordinate, the underlying network error, and a fix hint. Probes time out at 5 seconds per target so a misconfigured source doesn't hang validation.

Use `--probe` in CI for any environment that has network access to the declared sources; skip it when you're validating offline or on a build agent without source access (the default behavior — pure schema — works there).

## Iceberg prerequisite checks (since 0.14.0)

The Snowflake and GCP IaC emitters are *emit-when-derivable*: an `iceberg` expose whose binding is missing a required input used to produce no `EXTERNAL VOLUME`, no catalog integration, and no GCS bucket — nothing failed at `fluid apply`, and the gap only surfaced at `dbt run` when the warehouse rejected the write.

Since `0.14.0`, `fluid validate` mirrors every skip branch of those emitters, so each silent no-op is now a validation **error naming the missing field**:

- **Snowflake-managed (Horizon) tables** — need `binding.location.warehouse` (`s3://` or `gs://`) or `binding.location.bucket`; an S3-backed `EXTERNAL VOLUME` additionally needs `binding.location.iam_role_arn`.
- **Glue-cataloged tables** — need `binding.location.iam_role_arn` and `binding.location.account` so FLUID can create the Snowflake `CATALOG INTEGRATION`.
- **Volume overrides** — an explicit `binding.icebergConfig.properties.external_volume` must be a legal Snowflake identifier, and two exposes that derive the same volume name but point at different storage are rejected (one expose's data would land in the other's bucket).
- **BigQuery Iceberg tables** — need `binding.location.bucket` or a `gs://` `binding.location.warehouse` that names a bucket.

The emitters themselves are unchanged — the validator is the loud half. See the Iceberg sections of the [Snowflake provider](/forge_docs/providers/snowflake.html) and [GCP provider](/forge_docs/providers/gcp.html) guides for what each emitter provisions.

::: warning Behavior change under `--strict` in 0.14.0
A Snowflake Iceberg catalog that authenticates with a secret — `polaris`, `unity`, `rest` / `iceberg_rest`, `nessie` — is *understood but not emitted*: its `CATALOG INTEGRATION` needs an OAuth secret or bearer token, and the emitted OpenTofu module is credential-free. `fluid validate` now surfaces that as a warning, and because `--strict` promotes warnings to errors, **CI pipelines running `fluid validate --strict` on such contracts start failing on `0.14.0`**. Either run those contracts without `--strict`, or create the catalog integration out of band and take the secret-authenticated catalog out of the contract binding.
:::

## GCP binding checks (since 0.15.0)

The GCP IaC emitter is *emit-when-derivable*, so a `platform: gcp` expose it cannot resolve to a BigQuery / Cloud Storage / Pub-Sub target emits nothing and says nothing. Since `0.15.0`, `fluid validate` reports those exposes — resolved through the **emitter's own** dispatch, so the gate can neither block a contract that would have emitted nor wave through one that emits nothing.

The error/warning split is deliberate, because `fluid validate` runs for contracts that never reach `fluid generate iac`:

- **Error** — a `format` that *names* a GCP container while omitting the `binding.location` key that container needs. In practice, `format: gcs_file` with no `location.bucket`.
- **Warning** — everything else that resolves to nothing, including the `other` escape hatch. [A resource-free module is itself a hard failure](./generate-iac.md#a-resource-free-module-is-an-error-since-0-15-0) at the stage that actually needs the resource, so the loud stop is already in the right place and this only has to explain it early.

Formats with no `hashicorp/google` resource by design stay silent (`http_api`, `grpc_api`, `kafka_topic`, a store on another platform), and Iceberg exposes are left to the Iceberg gate above, which owns a more specific message for the same input.

## Schema dialect (since 0.15.0)

Since `0.15.0`, every schema is validated with the dialect it declares instead of with a pinned `Draft7Validator` — and Draft 7 ignores keywords it does not recognise rather than rejecting them, so any constraint expressed in a newer keyword was silently dropped.

**`fluid validate` on a contract behaves identically today.** The bundled FLUID schemas declare 2020-12 but have so far used only `$defs`, which Draft 7 resolves as an ordinary JSON pointer; 52 example contracts validate identically either way. The observable effect of the fix is on [`fluid validate-artifacts`](./validate-artifacts.md#schema-dialect-since-0-15-0), where the vendored ODCS v3.1.0 schema declares 2019-09 and guards nine objects with `unevaluatedProperties: false`.

One thing did change on this path, in the fail-safe direction: `schema_manager`'s `jsonschema` probe no longer names the unused `Draft7Validator` or the deprecated `RefResolver`. An `ImportError` in that probe sets `JSONSCHEMA_AVAILABLE = False`, which makes contract validation **skip** rather than error — so the day a `jsonschema` release drops `RefResolver`, the probe would have quietly disabled validation across the CLI.

## Notes

- A contract can legitimately use `fluidVersion: 0.7.2` even when the installed CLI release is `0.15.0`. Schema `0.7.5` is GA as of `0.10.0`.
- *(since 0.15.0)* `fluid validate` shares its sovereignty checker with [`fluid plan --check-sovereignty`](./plan.md#sovereignty-gate-since-0-15-0), and `sovereignty.enforcementMode` now decides severity in both directions: a `strict` contract whose binding region resolves outside its declared `jurisdiction` newly **fails** with exit 1, and an `advisory` contract that failed now only warns. Full table, and the region-table derivation that changes verdicts on contracts nobody edited: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
- For most users, plain `fluid validate contract.fluid.yaml` is enough. Reach for explicit schema flags when you are debugging compatibility or working across versions.

## Extension point: custom validators

As of `0.8.3`, `fluid validate` automatically runs any `Validator` plugin discovered via Python entry-points. After `pip install <some-validator-plugin>`, the validator's findings appear in `fluid validate` output alongside the core schema validation.

This is how teams enforce governance rules (every Gold product MUST declare a steward, every contract MUST have a cost-center label, etc.) without forking the CLI.

- Author a validator: [SDK & Plugins → Custom validator journey](/forge_docs/sdk-and-plugins/journeys/custom-validator.html)
- Reference: [Entry points → `fluid_build.validators`](/forge_docs/sdk-and-plugins/reference/entry-points.html)
- Example: [`steward-validator`](/forge_docs/sdk-and-plugins/examples/steward-validator.html)
