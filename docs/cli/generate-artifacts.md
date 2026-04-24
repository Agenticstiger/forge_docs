# `fluid generate artifacts`

Stage 3 of the 11-stage pipeline. Fanout that produces all catalog + execution artifacts for a contract in one call, plus a unified `MANIFEST.json` (SHA-256 per file + merkle root) that stage 4 verifies.

Added in `0.8.0` as a top-level subcommand of [`fluid generate`](./generate.md).

## Syntax

```bash
fluid generate artifacts CONTRACT [--out PATH] [--emit KEYS] [--env ENV]
```

`CONTRACT` can be a contract YAML file OR a tgz bundle emitted by [`fluid bundle --format tgz`](./bundle.md). When it's a tgz, `generate artifacts` extracts the content-addressable bundle first and validates its MANIFEST — so stage 3 can't be fed a tampered bundle.

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Contract YAML file or tgz bundle (positional, required). |
| `--out PATH` | Output directory. Default `dist/artifacts/`. |
| `--emit KEYS` | Comma-separated emit keys. Default: `odps-bitol,odcs,schedule,policies`. See emit-set table below. |
| `--env ENV` | Environment overlay. |
| `--no-generate-artifacts` | CI helper: auto-skip if the contract is reference-only. Useful in generated pipeline templates. |

## Emit set

| Key | What it emits | Status |
| --- | --- | --- |
| `odcs` | ODCS v3.1.0 contract files under `odcs/` (one per expose port) | Default on. Schema vendored from `bitol-io/open-data-contract-standard`. |
| `odps-bitol` | ODPS-Bitol v1.0.0 product file under `odps-bitol/` | Default on. Schema vendored from `bitol-io/open-data-product-standard`. |
| `opds` / `odps` | OPDS v4.1 product file under `opds/` | **Opt-in only** (broken shape vs upstream — see `trello-verify-odps-linux-foundation`). |
| `schedule` | DAG / flow files under `schedule/` (airflow / dagster / prefect) | Default on. Auto-skipped for reference-only contracts + contracts without `orchestration.engine`. |
| `policies` | `policy/bindings.json` (compiled IAM / GRANT bindings) | Default on. Auto-skipped for reference-only contracts. |

## Reference-only auto-skip

Contracts with `builds[].pattern: hybrid-reference` / `reference` / `external-reference` declare that the target tables are materialised by an externally-owned dbt / Airflow project. For these, `schedule` and `policies` are NOT emitted — the external project owns those concerns. Catalog artifacts (`odcs/`, `odps-bitol/`) are still produced.

The auto-skip is logged as `generate_artifacts_skip_reference_only`.

## Examples

### Catalog + execution artifacts

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
```

### tgz bundle input (production pipeline)

```bash
fluid bundle contract.fluid.yaml --format tgz --out runtime/bundle.tgz
fluid generate artifacts runtime/bundle.tgz --out dist/artifacts/
```

### Explicit emit set

```bash
# Catalog only (skip DAGs + bindings)
fluid generate artifacts contract.fluid.yaml --emit odcs,odps-bitol

# Execution only
fluid generate artifacts contract.fluid.yaml --emit schedule,policies
```

### With environment overlay

```bash
fluid generate artifacts contract.fluid.yaml --env prod --out dist/artifacts-prod/
```

## Output shape

```
dist/artifacts/
├── MANIFEST.json                            # SHA-256 per file + merkle root
├── odcs/product.odcs.<exposeId>.yaml        # one per exposed port
├── odps-bitol/<product>.odps-bitol.yaml
├── schedule/
│   ├── dags/<product>_dag.py                # Airflow
│   └── flows/<product>_flow.py              # Prefect
└── policy/bindings.json                     # compiled IAM / GRANT bindings
```

## Next step

Run [`fluid validate-artifacts`](./validate-artifacts.md) against the emitted tree to verify MANIFEST integrity + per-format schemas before shipping to catalogs or scheduler.

```bash
fluid generate artifacts contract.fluid.yaml --out dist/artifacts/
fluid validate-artifacts dist/artifacts/ --strict
```
