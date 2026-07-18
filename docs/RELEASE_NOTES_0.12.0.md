# Fluid Forge Docs Baseline: CLI `0.12.0`

**Release Date:** July 18, 2026
**Status:** Current stable docs baseline (supersedes [`0.11.0`](./RELEASE_NOTES_0.11.0.md))

## Headline

`0.12.0` is the **dbt-integration + schema-GA** release. Contract schema **`0.7.5` is promoted
to stable** and becomes the default for untagged contracts — the vector/embeddings
`vectorConfig` output port and the Redshift-Serverless/Kinesis binding fields are now GA, no
opt-in pin required. On the dbt side, a full integration wave lands: a faithful **brownfield
importer** (`fluid import dbt` reads `target/manifest.json`), **dbt model contracts**
(`--model-contracts`), a **MetricFlow bridge** (semantic_models + metrics YAML from the
contract's semantics block), auto-emitted `packages.yml` and `sources.yml` freshness blocks,
`run_results.json` parsed into run records and verify checks, and **dbt Fusion / dbt Core v2**
engine detection with engine-aware `tests:`/`data_tests:` emission. `fluid verify` grows a
second reconcile leg: **`--reconcile-lineage`** cross-checks declared lineage against local run
evidence and the catalog publish payload.

`pip install --upgrade data-product-forge`.

::: tip Who should upgrade
Any team with an existing dbt project (the importer turns `dbt parse` output into a governed
FLUID contract), anyone generating dbt projects from contracts (model contracts, MetricFlow
semantics, packages/freshness emission, Fusion compatibility), and anyone building AI/RAG
products — `vectorConfig` is now stable and default-available. **Note the one-time digest churn
for untagged contracts** described under [Compatibility](#compatibility).
:::

## What changed in `v0.12.0`

### Schema — `0.7.5` promoted to stable (GA); `0.7.6` opens as preview

- **`0.7.5` is now the default schema version for untagged contracts** (contracts that do not
  declare `fluidVersion`). Everything the `0.7.5` preview carried is GA:
  - the **vector / embeddings `vectorConfig` output port** consumed by
    [`fluid generate vector`](./cli/generate-vector.md) (pgvector RAG target),
  - the **Redshift Serverless + Kinesis** `bindingLocation` fields (`stream`, `namespace`,
    `workgroup`, `iam_role_arn`, `external_schema`, `glue_database`),
  - the streaming Kafka→Iceberg surface the version originally introduced.
- **`0.7.6` opens as the next preview** — bundled and fully validatable when a contract
  explicitly declares `fluidVersion: "0.7.6"`, identical to `0.7.5` at open; additive preview
  fields will land there. Preview versions are never the silent default.
- Contracts that **explicitly pin** a `fluidVersion` are unaffected.

### Added — `fluid import dbt` (brownfield dbt importer)

- [`fluid import dbt <project-dir|manifest>`](./cli/import.md#importing-a-dbt-project) converts
  a real dbt project's `target/manifest.json` (produced by `dbt parse` — no warehouse access
  needed) into a FLUID contract. Stdlib-only JSON parse, no dbt-core dependency; one DataProduct
  per dbt project.
- Faithful, not simplified: every model/seed/snapshot becomes an expose (no model cap), the
  `ref()`-derived DAG is recorded per expose, dbt **generic tests are recovered as `dq.rules[]`**
  (via the same shared test mapping the generators use — `relationships` and range tests become
  column `validationRules`), sources become `consumes[]` with freshness mapped to
  `qosExpectations.freshnessMax`, folder layout maps to `metadata.layer` + `metadata.productType`
  (staging→Bronze/SDP, marts→Gold/CDP), and a `catalog.json` overlay supplies warehouse-accurate
  column types when present.
- Requires manifest schema **v9+ (dbt 1.5, 2023)**; the primary target is v12 (dbt 1.8+). Run
  `dbt parse` first so `target/manifest.json` is fresh.
- The legacy no-argument directory scan (`fluid import` / `fluid import --dir`) now routes a dbt
  project with a `target/manifest.json` to this importer automatically.

### Added — dbt model contracts (`--model-contracts`)

- `fluid generate transformation --model-contracts` emits a **dbt model contract** on every
  expose model: `config: {contract: {enforced: true}}` plus per-column `data_type`
  (adapter-correct for bigquery/snowflake/redshift/duckdb) and `constraints` (`not_null` for
  required columns, `primary_key` for declared keys), all derived from
  `exposes[].contract.schema[]`. `dbt build` then fails in producer CI whenever the model's
  output diverges from the contract — build-time enforcement of the contract-first pitch.
- Opt-in (enforcement fails builds for already-drifted user SQL); requires dbt-core ≥ 1.5;
  dbt-only (ignored with a warning for other engines).

### Added — MetricFlow bridge (semantic_models + metrics YAML)

- When a contract carries `exposes[*].semantics`, the generated dbt project now includes
  `models/semantic_models.yml` with **`semantic_models:` + `metrics:`** blocks (dbt Semantic
  Layer / MetricFlow shape). Simple, derived, and ratio metric types all map; a day-grain
  `metricflow_time_spine` model is emitted alongside (MetricFlow hard-requires it).
- Defaulting satisfies MetricFlow parse strictness: primary entity derived from the expose's key
  column, `defaults.agg_time_dimension` resolved or synthesized, unresolvable measures/metrics
  dropped with a warning rather than emitting a project that fails `dbt parse`.
- Contracts without a semantics block are untouched — byte-identical output.

### Added — `packages.yml` + `sources.yml` freshness emission

- Generated dbt projects whose tests reference `dbt_utils.` / `dbt_expectations.` now
  auto-emit a **`packages.yml`** with range-pinned entries for exactly the packages the emitted
  tests use, so the project passes its own `dbt deps` + `dbt parse` without hand-authoring.
  Under `--mesh-hub` the pins fold into the emitted `dependencies.yml` instead (dbt forbids the
  two files coexisting); a user-managed `packages.yml` is never overwritten.
- Contract freshness promises now reach `dbt source freshness`: **`sources.yml` gains a
  `freshness:` block per source table**, derived from upstream
  `exposes[].qos.freshnessSLO` (→ `warn_after`) and consumer
  `consumes[].qosExpectations.freshnessMax` (→ `error_after`), with `loaded_at_field` resolved
  from the upstream acquisition cursor field where possible.
- Bug fixed in passing: emitted `dbt_utils.recency` tests previously carried a non-dbt
  `_fluid_window` argument that failed `dbt compile`; the window now maps to real
  `datepart`/`interval` values.

### Added — `run_results.json` → run records + verify checks

- `fluid apply --mode amend-and-build` previously discarded everything dbt reported except the
  process exit code. The runner now parses `target/run_results.json` (versions v1–v6, stdlib
  only) and persists a canonical run record per dbt node, so **failing contract tests surface in
  [`fluid runs status`](./cli/runs.md)** and in [`fluid verify`](./cli/verify.md), which gains
  transformation-side checks (`dbt_tests_passed`, `no_error_severity_failures`) that gate the
  exit code under `--strict`.

### Added — dbt Fusion / dbt Core v2 compatibility

- The dbt runner now **detects the engine flavor** (`fusion` vs `core` + version) from
  `dbt --version`. Fusion compiles its adapters in and lists no plugins, which previously failed
  the adapter probe and silently punted every Fusion user to the slow Docker fallback — Fusion
  now runs natively. [`fluid doctor`](./cli/doctor.md) and the welcome scan report the detected
  engine flavor.
- **Engine-aware `tests:` / `data_tests:` emission.** dbt-core 1.8 renamed the data-test key,
  and Fusion strict-parses (the legacy `tests:` fails). Generated projects now pick the right
  dialect automatically: `--dbt-tests-key auto|tests|data_tests` (env: `FLUID_DBT_TESTS_KEY`),
  where `auto` (default) probes the dbt binary you would actually run — Fusion or core ≥ 1.8 get
  `data_tests:`, core < 1.8 or no detectable binary gets the universally-parsed legacy `tests:`.
  Pass an explicit value in CI generators with no local dbt binary.
- The dbt executable resolves via **`$DBT_EXECUTABLE`** (absolute path, bare name, or
  multi-token wrapper) before falling back to `PATH` and the active venv. See
  [Environment Variables](./advanced/environment-variables.md).

### Added — `fluid verify --reconcile-lineage`

- A local-only cross-check that the contract's **declared** lineage (`consumes[]` /
  `exposes[]`) agrees with the lineage that was actually **observed** (run records + cursor
  state under `.fluid/`) and the lineage that would actually be **published** (the catalog
  payload rebuilt locally — no network). Three drift classes:
  - `declared_but_never_read` (**soft**) — a consume with no run evidence; never fails.
  - `read_but_undeclared` (**critical**) — a stream a runner actually read that the contract
    never admits to; gates under `--strict`.
  - `publish_payload_mismatch` (**critical**) — the registrar payload's lineage edges disagree
    with the contract; gates under `--strict`.
- `--warn-only` downgrades drift from both reconcile legs (`--reconcile-dbt` /
  `--reconcile-lineage`) to warnings. See [`fluid verify`](./cli/verify.md).

### Fixed & internal

- **Copilot enrichment now emits schema-valid slots + ISO-8601 dq-rule windows**, closing a
  class of authoring-time validation failures.
- The three contract→dbt-test mappers are consolidated into one shared module (the importer's
  reverse mapping reads the same table, so import→generate round-trips stay symmetric).
- CI: the overloaded 3.12 test leg is split into a parallel coverage-and-audit job; a
  test-leg hang (timezone-formatter × warning-amplification) is retired; the release image's
  Docker CVE gate is green again via base-image upgrade + re-curated ignores.

## Compatibility

- **One-time plan/bundle digest churn for untagged contracts.** Because untagged contracts now
  default to `0.7.5` (previously `0.7.4`), their canonical form changes once, so
  `bundleDigest` / `planDigest` values recomputed after upgrade will differ from pre-`0.12.0`
  values. This is deliberate and happens **once per contract on first re-plan** after the
  upgrade. Re-run `fluid bundle && fluid plan` to re-baseline; contracts that explicitly declare
  `fluidVersion` are unaffected.
- **Contract schema:** `0.7.5` is stable and the new default; `0.7.6` is bundled as opt-in
  preview. No fields were removed; validation of explicitly-pinned contracts is unchanged.
- **SDK / custom-scaffold:** unchanged (`data-product-forge-sdk 0.10.0`,
  `data-product-forge-custom-scaffold 0.4.0`).
- **Install:** `pip install --upgrade data-product-forge` → `0.12.0`.
