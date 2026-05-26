# `fluid generate`

Unified artifact generation from FLUID contracts.

## Syntax

```bash
fluid generate <transformation|speed-transformation|dbt|dbt-tests|schedule|ci|standard|artifacts>
```

## Subcommands

### `fluid generate artifacts`

**Stage 3 of the 11-stage pipeline.** Fanout that produces all catalog + execution artifacts for a contract in one call:

- ODCS (v3.1.0) contract files under `odcs/`
- ODPS-Bitol (v1.0.0) product files under `odps-bitol/`
- Schedule DAGs under `schedule/` (Airflow / Dagster / Prefect — depending on `orchestration.engine`)
- Policy bindings under `policy/bindings.json` (IAM / GRANT)
- A unified `MANIFEST.json` (SHA-256 per file + merkle root) for downstream stage-4 verification

Reference-only contracts (`builds[].pattern: hybrid-reference` / `reference` / `external-reference`) auto-skip the `schedule` and `policies` emitters — those execution artifacts are owned by the team's own dbt/Airflow repo. Catalog artifacts (`odcs/`, `odps-bitol/`) are still emitted.

Key options:

- `CONTRACT` — path to `contract.fluid.yaml` (or a tgz bundle from `fluid bundle --format tgz`)
- `--out PATH` — output directory (default `dist/artifacts/`)
- `--emit {odcs,odps-bitol,opds,schedule,policies}[,...]` — explicit emit set; default is everything except the `opds` / `odps` aliases which remain opt-in until the Linux-Foundation emitter shape is fixed
- `--env ENV` — environment overlay
- `--no-generate-artifacts` — CI helper: auto-skip this stage when the contract is reference-only (`pattern: hybrid-reference` etc.)

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/        # tgz input
fluid generate artifacts contract.fluid.yaml --emit odcs,odps-bitol      # catalog only
```

Verify the emitted tree with [`fluid validate-artifacts`](./validate-artifacts.md) (stage 4).

### `fluid generate transformation`

Generate transformation artifacts such as dbt projects or SQL output.

Key options:

- `contract`
- `--output`, `-o`
- `--build-index`
- `--overwrite`
- `--env`
- `--dbt-validate`
- `--list`
- `--verbose`

When the contract was produced by `fluid forge data-model`, the generator auto-loads the logical sidecar named by `labels.modelSidecar` and emits deterministic SQL from the forged logical model. For dbt output, zero generated `models/**/*.sql` files is a hard failure rather than a quiet success.

A normal dbt output directory includes:

- `dbt_project.yml`
- `profiles.yml`
- `models/sources.yml` when source hints are available
- non-empty SQL models under `models/`

`fluid generate speed-transformation` and `fluid generate dbt` remain aliases for this path.

### `fluid generate dbt-tests`

Read the contract's `exposes[].contract.dq.rules[]` and emit a dbt `schema.yml` so your data-quality rules run as native dbt tests.

```bash
fluid generate dbt-tests
fluid generate dbt-tests contract.fluid.yaml -o dbt/models/schema.yml
fluid generate dbt-tests --env prod
```

Key options:

| Option | Description |
| --- | --- |
| `contract` | Contract path. Defaults to `contract.fluid.yaml` in the current directory. |
| `--out`, `-o` | Output path for the dbt `schema.yml` (default `./schema.yml`). Drop it into your dbt project's `models/<schema>/` directory. |
| `--env` | Environment overlay (`dev` / `test` / `prod`). |

- **Column-level rules** map to dbt's built-in tests — `not_null`, `unique`, `accepted_values` — with `dbt-utils` placeholders emitted for rules that have no native dbt equivalent.
- **Model-level rules** map to `dbt-utils`: `anomaly_detection` / `drift_detection` rules become `dbt-utils` expressions, and a `freshness` rule becomes `dbt_utils.recency`.
- The generated `dbt-utils`-based tests require the `dbt-utils` package to be installed in your dbt project.
- A managed-by sentinel marks the generated file, so re-running the command never clobbers a `schema.yml` you have hand-edited.

After generating, run `dbt test` in your dbt project to execute the rules.

### `fluid generate schedule`

Generate orchestration artifacts such as Airflow DAGs, Dagster pipelines, or Prefect flows.

Key options:

- `contract`
- `--output`, `-o`
- `--scheduler`
- `--overwrite`
- `--env`
- `--list`
- `--verbose`

This is the promoted path for orchestration generation.

### `fluid generate ci`

Generate CI/CD pipeline configuration for Jenkins, GitHub Actions, GitLab CI, Azure DevOps, Bitbucket, CircleCI, or Tekton.

Key options:

| Option | Description |
| --- | --- |
| `contract` | Contract path. Defaults to `contract.fluid.yaml` when omitted. |
| `--system` | Target CI system: `jenkins`, `github`, `gitlab`, `azure`, `bitbucket`, `circle`, or `tekton`. |
| `--out PATH` | Override the primary output path. Multi-file systems still write their supporting files to canonical locations. |
| `--no-generate-artifacts` | Skip transformation/schedule artifact stages for reference-only contracts. Reference-only builds are also auto-detected from `builds[].pattern`. |
| `--install-mode {pypi,dev-source}` | Jenkins only. `pypi` installs `data-product-forge`; `dev-source` installs from a `/forge-cli-src` bind mount for contributor labs. |
| `--default-publish-target TARGET` | Jenkins only. Emits a Stage 10 shell fallback of `${PUBLISH_TARGETS:-TARGET}` so the first Pipeline-from-SCM build can publish to the intended catalog before Jenkins exports parameter defaults. |
| `--[no-]verify-strict-default` | Jenkins only. Controls the generated `VERIFY_STRICT` parameter default. Default is `true`. |
| `--[no-]publish-stage-default` | Jenkins only. Controls the generated `RUN_STAGE_10_PUBLISH` parameter default. Default is `false`. |
| `--[no-]publish-include-env` | Jenkins only. Controls whether Stage 10 appends `--env "${FLUID_ENV:-dev}"` to `fluid publish`. Use `--no-publish-include-env` for catalog publish paths that should not receive an environment flag. |

Jenkins example for an Entropy Data / Data Mesh Manager first run:

```bash
fluid generate ci contract.fluid.yaml \
  --system jenkins \
  --install-mode pypi \
  --default-publish-target datamesh-manager \
  --no-verify-strict-default \
  --publish-stage-default \
  --no-publish-include-env \
  --out Jenkinsfile
```

### `fluid generate standard`

Export to data product standards.

Key options:

- `contract`
- `--format`, `-f`
- `--out`, `-o`
- `--env`
- `--list`

Supported formats:

| `--format` | What it is | Use it when |
| --- | --- | --- |
| `odps` *(default)* | **Bitol ODPS v1.0.0** — Open Data Product Standard (center-stage) | Publishing to Entropy Data / Data Mesh Manager. Rich product metadata, lineage, SLA, governance. Preserves FLUID-specific fields under an `x-fluid` namespace. |
| `odcs` | Open Data Contract Standard (ODCS) v3.1.0 — the Bitol.io standard | Publishing **contract-level** specs (schema, quality, SLA) to Bitol-aligned tooling. Where ODPS describes a whole data product, ODCS focuses on the consumer-facing contract. |
| `odps-v4.1` | LF/ODPI ODPS v4.1 — Open Data Product Specification (opt-in) | ODPI-aligned catalogs that consume the Linux Foundation / Open Data Product Initiative spec. |
| `odps-bitol` | Standards-compliant Bitol ODPS payload, stricter than `odps` | Strict conformance — fields that are not explicitly declared on a `consumes[]` entry are omitted (no synthetic `contractId`, no default `required: True`). |
| `opds` | **Deprecated alias** for `odps` | Back-compat only. Emits a deprecation warning. Use `odps` instead. |

### Examples of each format

```bash
fluid generate standard contract.fluid.yaml --format odps        # FLUID -> Bitol ODPS v1.0.0 (default, center-stage)
fluid generate standard contract.fluid.yaml --format odcs        # FLUID -> ODCS v3.1.0
fluid generate standard contract.fluid.yaml --format odps-v4.1  # FLUID -> LF/ODPI ODPS v4.1 (opt-in)
fluid generate standard contract.fluid.yaml --format odps-bitol  # FLUID -> ODPS (strict Bitol conformance)
```

### ODPS environment tuning

The ODPS exporter reads a few environment variables for output shape:

| Env var | Default | Purpose |
| --- | --- | --- |
| `ODPS_INCLUDE_BUILD_INFO` | `true` | Include build information (engine, pattern) |
| `ODPS_INCLUDE_EXECUTION_DETAILS` | `false` | Include execution details (triggers, runtime) |
| `ODPS_TARGET_PLATFORM` | `generic` | Platform-specific tuning (`collibra`, etc.) |
| `ODPS_VALIDATE_OUTPUT` | `true` | Validate the emitted JSON |

All formats are deterministic — identical input yields byte-identical output, so the result is safe to check into version control.

#### Shortcut — `fluid export-odps`

For a one-shot file write of the ODPS format:

```bash
fluid export-odps CONTRACT [--env ENV] [--out PATH]
```

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--env ENV` | Apply an environment overlay |
| `--out PATH` | Output file path (default: `runtime/exports/product.odps.json`) |

Produces the same output as `fluid generate standard --format odps`. The old `fluid export-opds` spelling is kept as a back-compat alias.

## Examples

```bash
fluid generate transformation
fluid generate transformation contract.fluid.yaml -o ./dbt_project
fluid generate transformation contract.fluid.yaml -o ./dbt_project --dbt-validate
fluid generate schedule contract.fluid.yaml --scheduler airflow -o dags
fluid generate ci --system github
fluid generate standard contract.fluid.yaml --format odps
fluid generate standard contract.fluid.yaml --format odps-v4.1
```

## Compatibility note

[`fluid generate-airflow`](./generate-airflow.md) still works for Airflow generation, but current docs lead with `fluid generate schedule --scheduler airflow`.
