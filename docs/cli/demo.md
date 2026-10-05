# `fluid demo`

Scaffold a customer-360 example project with sample data, then try to run it locally. No API key and no cloud account.

## Syntax

```bash
fluid demo [NAME] [--dry-run] [--no-run] [--quiet]
```

## Examples

```bash
fluid demo
fluid demo my-customer-360
fluid demo --dry-run
fluid demo my-project --no-run
```

`fluid demo` creates `fluid-demo/` in the current directory (or `NAME/`), from the same `customer-360` template that `fluid init --quickstart` uses:

```text
.
├── .fluid/run-id.txt
└── fluid-demo/
    ├── contract.fluid.yaml
    ├── README.md
    ├── data/
    │   ├── customers.csv
    │   ├── interactions.csv
    │   └── orders.csv
    └── .fluid/
        ├── db.duckdb
        └── init-receipt.json
```

## What happens on 0.18.1

The scaffold step works. The step that runs the pipeline does not: as of 0.18.1 it fails, and the command still reports success and exits `0`.

```text
✅ Copied template files from customer-360
✅ Sample data loaded: 3 CSV files
✅ Local database initialized (DuckDB)

🚀 Running pipeline locally...

Loading FLUID contract: .../fluid-demo/contract.fluid.yaml
Using simple execution mode (local provider)
💥 Unexpected error during execution: 'ApplyArgs' object has no attribute 'config_override'
⚠️  Could not auto-run pipeline: 'ApplyArgs' object has no attribute 'debug'
You can run it manually:
  $ cd fluid-demo
  $ fluid apply contract.fluid.yaml --provider local

╭─ 🎉 Success ─────────────────────────────────────────────────────────────────╮
│                                                                              │
│  Your data product is ready!                                                 │
...
```

Nothing ran at that point. Treat `Success` as "the project was scaffolded". The manual command it prints does run:

```bash
cd fluid-demo
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --provider local --yes
```

`validate` passes. `apply` exits `0` and writes `output/customer_360.parquet` and `output/high_value_customers.parquet`, but each is a 24-byte placeholder: the contract declares its SQL per stage under `builds[].properties.stages[]`, and the local provider reports `Build customer_360_pipeline has no SQL, skipping`. The demo contract is a good project to read and to run `validate`, `plan` and `verify` against. It does not produce data on 0.18.1.

For a scaffold whose local apply writes rows, use `fluid init orders --blueprint fluid.starter` (it writes `runtime/out/orders.csv`) or the `csv-basics` template. See [Run what you scaffolded](./init.md#run-what-you-scaffolded).

## Key options

| Option | Description |
| --- | --- |
| `NAME` | Directory name for the demo project (positional, optional, default: `fluid-demo`). |
| `--dry-run` | Preview what would be created without writing anything. |
| `--no-run` | Scaffold the project but skip the pipeline run. |
| `--quiet`, `-q` | Suppress the next-steps panel and other post-success hints. |

## Notes

- The demo runs against the `local` provider. It has no option to deploy to a cloud account.
- It refuses to write into a symlinked target or a non-empty existing directory. Pick a different name or remove the directory first.
- `--no-run` skips the step that fails on 0.18.1, so it is the option to use when you want a clean exit status.
- After it finishes you have a normal project: try [`fluid validate`](./validate.md), [`fluid plan`](./plan.md) and [`fluid apply`](./apply.md) inside it.
- To start your own project, use [`fluid init`](./init.md); for AI-guided creation, [`fluid forge`](./forge.md).
