# Fluid Forge Docs Baseline: CLI `0.14.0`

**Release Date:** July 28, 2026
**Status:** Current stable docs baseline (supersedes [`0.13.0`](./RELEASE_NOTES_0.13.0.md))

This baseline covers **two CLI releases**: `0.13.1` (July 26) and `0.14.0` (July 28). `0.13.1`
did not receive its own docs pass, so both change sets are documented here.

## Headline

`0.14.0` is the **live-verification hardening** release, and `0.13.1` beneath it is the
**interoperability** release that set it up.

The headline is the **dbt Iceberg loop reaching all three cloud warehouses**. `0.13.1` shipped
both halves for Snowflake: [`fluid generate`](./cli/generate.md) emits dbt's `catalogs.yml` for
Iceberg exposes — Snowflake Horizon (`built_in`) plus the `glue` / `polaris` / `unity` / `rest` /
`nessie` REST-family catalogs — and [`fluid apply`](./cli/apply.md) provisions the prerequisites
dbt refuses to create: the EXTERNAL VOLUME and the AWS Glue CATALOG INTEGRATION (#469, #470).
`0.14.0` extends the loop to **BigQuery**: an `iceberg` expose on a GCP binding — which previously
fell through the emit dispatch and produced *nothing, silently* — now emits `catalogs.yml` with
`catalog_type: biglake_metastore` and provisions the GCS bucket dbt refuses to create (#474). The
whole surface sits behind a new **validate-time anti-no-op gate**: every case where an IaC emitter
would silently skip an Iceberg expose is now a [`fluid validate`](./cli/validate.md) error naming
the missing field, and the check↔skip-branch pairing is test-pinned in both directions (#475).

Alongside it, the **104-defect live-verification wave** (#476, #478): a month of shipped features
was exercised end-to-end against a **real Snowflake account**, every fix re-verified by a second
agent re-running the original failing scenario. The headline finding — embedded-SQL builds on a
`platform: snowflake` contract executed against local DuckDB and exited 0 either way. Snowflake
builds now actually run on Snowflake; the rest of the wave is itemized below.

`pip install --upgrade data-product-forge`.

::: tip Who should upgrade
Anyone running **dbt with Iceberg tables** on Snowflake or BigQuery (the loop now emits
`catalogs.yml` and provisions what dbt won't); anyone on the **Snowflake platform** (the
104-defect wave corrects builds, verify, import round-trips, and governed-query enforcement that
were previously wrong or vacuous); anyone consuming **OpenLineage** or **ODCS** (both surfaces
went from lossy or non-conformant to verified against the official schemas); and any operator
whose audit pipeline filters at WARNING — safety-gate override events are finally visible to it.
:::

::: warning Two behavior changes
1. **`fluid validate --strict` now fails Snowflake Iceberg catalogs that authenticate with
   secrets** (`polaris` / `unity` / `rest` / `nessie`). The emitted IaC module is credential-free
   by design, so strict mode promotes the existing warning to an error (#475). CI pipelines
   running `--strict` over such contracts will go red on upgrade — either move the credential out
   of the contract or drop `--strict` for that lane.
2. **Safety-gate override audit events now log at WARNING**, as documented.
   `opentofu_destructive_gate_override` (`--allow-data-loss`) and `packaging_adoption_override`
   (`--adopt-shared-container`) were emitted at INFO — invisible to audit pipelines filtering at
   WARNING and above. Event names and payloads are unchanged (#450).
:::

## What changed in `v0.14.0`

### Added — the dbt Iceberg loop reaches BigQuery

An `iceberg` expose on a GCP binding previously emitted nothing — the dispatch only handled
`bigquery_table` / `view` / `gcs_bucket` / `pubsub_topic`, so it fell through silently. Now (#474):

- [`fluid generate`](./cli/generate.md) emits `catalogs.yml` with
  `catalog_type: biglake_metastore`. BigQuery's shape genuinely differs from Snowflake's:
  `external_volume` is a bare `gs://` URI (not the name of a pre-existing object), and
  `file_format` is required (Snowflake has no such key).
- [`fluid generate iac`](./cli/generate-iac.md) provisions the **GCS bucket dbt refuses to
  create**, reusing the plain `gcs_bucket` emit so settings, labels, and access-grant IAM stay
  identical.
- **The bucket dbt loads into is always the bucket the IaC creates and governs.** The IaC bucket
  name is derived *from* the same warehouse URI dbt writes into `external_volume` — one shared
  helper pair, so the two sides cannot diverge. A foreign scheme (`s3://` under
  `biglake_metastore`) or a bucket-less URI makes both sides skip together.
- Whole-bucket `force_destroy` is dropped when the product owns only a prefix of a shared
  warehouse root.

Databricks stays out deliberately: its `catalogs.yml` shape is unverified, and emitting a guess is
worse than emitting nothing.

### Added — validate-time anti-no-op gate for Iceberg prerequisite bindings

The Snowflake and GCP IaC emitters *skip* an Iceberg expose missing a required input rather than
emit a broken resource — which previously meant the user found out at `dbt run`. Now
[`fluid validate`](./cli/validate.md) errors on exactly those cases, naming the missing field
(#475). Each validate check mirrors one emitter skip-branch, and the pairing is **test-pinned in
both directions** — a new skip-branch without a matching check fails the suite, and vice versa.

Note the `--strict` consequence in the warning block above: Snowflake catalogs that authenticate
with secrets now fail strict validation, since the emitted module is credential-free.

### Fixed — the 104-defect live-verification wave

A month of shipped features exercised against a real Snowflake account; every fix re-verified by a
second agent re-running the original failing scenario (#476, #478). The clusters:

- **Snowflake builds actually run on Snowflake.** Embedded-SQL builds on a `platform: snowflake`
  contract executed against local DuckDB (exit 0 either way); `--model-contracts` flattened every
  parameterized / alias type to `VARCHAR(16777216)`, so contract enforcement passed vacuously;
  generated `profiles.yml` ignored the contract's schema and silently targeted `PUBLIC`; a freshly
  generated project failed its own contract on first `dbt run`; and a `freshness` dq rule made the
  generated project unparseable.
- **[`fluid import dbt`](./cli/import.md) → `apply` → [`verify`](./cli/verify.md) round-trips
  cleanly.** Importing then applying no longer creates a duplicate lowercase shadow namespace
  (`+2 ~2 -0` → `+0 ~2 -0`), `verify` can read the real objects through `snowflake_view`, and a
  p90 metric no longer silently round-trips into a median.
- **[`fluid publish`](./cli/publish.md) no longer silently skips contract-declared catalog
  targets** (an `ImportError` swallowed by a bare `except`), and apply hooks now run on the
  OpenTofu path — making `--env` plumbing reachable for Snowflake / AWS / GCP applies.
- **Governed access enforcement holds under aliasing.** The governed `query` path now enforces
  `policy.authz.columnRestrictions` (a denied column was readable as a measure), and PII redaction
  can no longer be bypassed by aliasing a restricted column — policy was previously checked on the
  *output* column name, which the semantic layer aliases away.
- **Data-quality test reporting is truthful.** A failing `severity: critical` rule no longer
  reports PASS with exit 0; `accuracy` rules evaluate upper bounds instead of only `MIN()`;
  `summary.checks_passed` no longer counts warnings and failed criticals as passed; `--no-data` no
  longer asserts checks it never performed; and `--engine soda` can now actually produce checks
  (the schemas never defined the `exposes[].quality.tests[]` key it reads). See
  [`fluid test`](./cli/test.md).
- **ODCS export/import fidelity.** Export no longer flattens every parameterized type to
  `logicalType: string`, round-trips no longer lose 88 of 114 leaf fields, and
  [`fluid odcs`](./cli/odcs.md) import no longer rewrites a Snowflake binding to `bigquery` while
  reporting success — now validated against the official ODCS schema.
- **`--adopt-shared-container` respects per-exposure `binding.packaging` overrides.** Flipping one
  binding no longer absorbs a shared platform pool into the tenant's state (which erased the
  pool's COMMENTs); transition scoping now keys on which container is nested where, not on
  resource type.

## What changed in `v0.13.1`

### Added — Snowflake Iceberg loop for dbt, both halves

[`fluid generate`](./cli/generate.md) emits dbt's `catalogs.yml` (v1 schema, Snowflake adapter)
for Iceberg exposes, and [`fluid apply`](./cli/apply.md) provisions the prerequisites dbt refuses
to create — the EXTERNAL VOLUME for Snowflake-managed catalogs and the AWS Glue CATALOG
INTEGRATION (#469, #470). A single deterministic naming helper is shared by both emitters, so the
volume `fluid apply` creates carries exactly the name `catalogs.yml` references (explicit override
honoured via `binding.icebergConfig.properties`). Live-verified with a real `tofu apply`. See the
[Snowflake provider](./providers/snowflake.md).

### Added — `fluid import dbt --split-by`

[`fluid import dbt --split-by {project|folder|group}`](./cli/import.md) splits a dbt manifest into
multiple data products along folder or dbt-group boundaries (`project` remains the byte-stable
single-contract default). Cross-split `ref()`s become cross-product `consumes[]`, `--out` becomes
the output directory for multi-contract imports, and dbt ≥1.10 manifests with `arguments:`-nested
test params now import correctly alongside legacy flat kwargs (#465). In passing, model-level
expose descriptions are now scrubbed like their column/semantic siblings (closing a hostile-Jinja
smuggling path into generated `schema.yml`).

### Added — Bitol ODPS v1.1.0 and declared consumers

- **Bitol ODPS v1.1.0 top-level `type`** (approved RFC 0029): `sourceAligned` / `aggregate` /
  `consumerAligned` map 1:1 and bidirectionally to FLUID's SDP / ADP / CDP classification. The
  default emit target stays v1.0.0 until Bitol cuts the release — **opt in** via `--api-version` /
  `ODPS_API_VERSION`. Validation keys on the document's own `apiVersion`, and custom org types
  round-trip verbatim (#471). See [`fluid exporters`](./cli/exporters.md) and
  [`fluid odps-bitol`](./cli/odps-bitol.md).
- **Declared `consumers:` block in the `0.7.6` preview schema.** Contracts can now declare their
  downstream consumers — dashboards, notebooks, ML systems, applications — with a shape borrowed
  from dbt exposures (`name` / `label` / `type` / `owner` / `url` / `maturity`) plus FLUID-native
  `exposeIds` tying a consumer to specific output ports. Additive and optional; preview schema
  only, no GA change (#466).

### Fixed — OpenLineage events real consumers can ingest

The emitter historically produced payloads no OpenLineage consumer would accept (missing required
`producer` / `schemaURL`, flattened `run` / `job` structure, non-UUID `runId`) — and was never
wired up, so zero events were ever sent. Emission now routes through `openlineage-python` at the
acquisition-runner chokepoints (all six engines, no per-runner wiring), honours the standard
**`OPENLINEAGE_URL`** so an existing Marquez / DataHub deployment just works, and redacts run
facets and stream names before anything leaves the machine. ODCS contract publishing also moves
onto OpenMetadata's first-class Data Contracts entity (#467).

Also in `0.13.1`: `fluid-schema-0.7.5.json` no longer carries UTF-16 surrogate-pair escapes that
broke YAML-based schema consumers such as `datamodel-code-generator` (#451), and the safety-gate
override audit events moved to WARNING (#450 — see the warning block above).

## Security — across both releases

- **`binding.location.dbFile` is now confined to `--readable-paths`** (`0.13.1`, #463). The DuckDB
  output-port driver gated `binding.location.path` and `.attach` against the operator's allowlist
  but passed `dbFile` raw to `duckdb.connect`, so a served contract could open and read **any host
  database** — a read-side sandbox escape. `dbFile` now flows through the same resolve-and-contain
  gate as its siblings (`:memory:` passes through; no-allowlist behaviour is unchanged).
- **Document-controlled ids are contained in exporter filenames** (`0.13.1`, #472). A contract
  with a traversal-shaped `exposeId` run through
  [`fluid generate artifacts --out dist`](./cli/generate-artifacts.md) could write an
  attacker-influenced file outside `--out` — and `MANIFEST.json` would bless the escaped path. New
  `providers/_path_safety.py` (the filename sibling of `_sql_safety.py`) passes schema-valid FLUID
  ids through verbatim, cleans-plus-digests anything else, and re-checks the resolved path against
  the output root at all three write sites. Verified against 204k+ separator/control-char cases
  and a full Unicode sweep with zero escapes and zero canonical-layout changes.
- **[`fluid viz-graph`](./cli/viz-graph.md) escapes contract-authored text before it reaches
  generated DOT source** (`0.14.0`, #481). Mesh node/edge labels were interpolated verbatim, so a
  product label like `X" label="SPOOFED` injected a second `label` attribute and let a contract
  display a name of its choosing — including another product's — in the rendered mesh graph; node
  IDs interpolated through a denylist that missed `"` and `\` let a `consumes[].ref` inject
  phantom nodes into the lineage graph. Both shared helpers are fixed (allowlist IDs,
  backslash-then-quote label escaping).
- **Secret redaction rewritten to redact by exact known value** (`0.14.0`, #478). The previous
  regex-based approach guessed a secret's extent from its shape and leaked 17 known inputs;
  redaction is now delimiter-agnostic by construction, masking the literal values it knows.
- **Commits carrying values from the committer's own environment are refused** (`0.14.0`, #479).
  A new pre-commit/CI hook flags any diff line byte-identical to a non-trivial value in the
  committing machine's environment (`SNOWFLAKE_*`, `AWS_*`, `*_TOKEN`, `*_PASSWORD`, …) or a
  supplied `--env-file` — catching the low-entropy identifiers (account locators, usernames) that
  secret-shape scanners cannot see — and never prints the matched value. `detect-secrets` now also
  actually runs in CI, on changed files.
- **Vulnerability reports route through GitHub Private Vulnerability Reporting** (`0.14.0`, #473).

## Compatibility

- **No breaking changes to existing contracts.** `0.7.5` remains the stable schema default; the
  `consumers:` block is `0.7.6` **preview**, opt-in via `fluidVersion: "0.7.6"`.
- **`fluid validate --strict` is stricter on Snowflake Iceberg.** Secret-authenticating catalogs
  (`polaris` / `unity` / `rest` / `nessie`) now fail under `--strict` — see the warning block.
- **Safety-gate override events log at WARNING.** If your log pipeline *alerted* on these at INFO,
  adjust the filter; names and payloads are unchanged.
- **Data-quality summaries may newly fail.** The truthful-reporting fixes mean CI lanes that
  previously passed on vacuous checks (critical failures counted as passed, `--no-data`
  assertions, DuckDB-instead-of-Snowflake builds) can now go red — for real reasons.
- **ODPS emit target unchanged.** v1.0.0 remains the default; v1.1.0 `type` is opt-in via
  `--api-version` / `ODPS_API_VERSION`.
- **SDK / custom-scaffold:** unchanged (`data-product-forge-sdk 0.10.0`,
  `data-product-forge-custom-scaffold 0.4.0`).
- **Install:** `pip install --upgrade data-product-forge` → `0.14.0`.
