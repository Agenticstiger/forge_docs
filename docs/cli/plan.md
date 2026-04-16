# `fluid plan`

Generate an execution plan without applying changes.

## Syntax

```bash
fluid plan CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay |
| `--out`, `--output` | Write the plan JSON, default `runtime/plan.json` |
| `--verbose`, `-v` | Show detailed action information |
| `--validate-actions` | Validate generated provider actions |
| `--estimate-cost` | Ask the provider to estimate cost |
| `--check-sovereignty` | Ask the provider to validate sovereignty constraints |
| `--provider` | Override the provider from the contract |
| `--html` | Generate an HTML visualization |

## Examples

```bash
fluid plan contract.fluid.yaml
fluid plan contract.fluid.yaml --verbose
fluid plan contract.fluid.yaml --env prod --out runtime/prod-plan.json
fluid plan contract.fluid.yaml --html
```

## Notes

- `plan` is the safest place to preview a provider override or environment overlay before you run `apply`.
- The generated plan can be passed to [`fluid apply`](./apply.md).

## Visualizing the plan — `fluid viz-graph`

`fluid plan --html` emits a quick HTML summary alongside `runtime/plan.json`. For richer visualization — themed lineage and build-DAG diagrams — use `fluid viz-graph`:

```bash
fluid viz-graph CONTRACT [options]
```

### Key options

**Input / output**

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required) |
| `--env ENV` | Apply an environment overlay |
| `--plan PATH` | Overlay a saved `runtime/plan.json` so build actions are shown on the graph |
| `--out PATH`, `--output PATH` | Output file path (default: `runtime/graph/contract.svg`) |

**Format & appearance**

| Option | Description |
| --- | --- |
| `--format {dot,svg,png,html}` | Output format (default: `svg`) |
| `--theme NAME` | Color theme (default: `dark`) |
| `--custom-theme PATH` | Path to a custom theme JSON/YAML file |
| `--rankdir {LR,TB,RL,BT}` | Graph layout direction (default: `LR`) |
| `--title TEXT` | Custom title for the graph |

**Content**

| Option | Description |
| --- | --- |
| `--show-legend` | Add a legend explaining node types |
| `--collapse-consumes` / `--collapse-exposes` | Collapse consumed sources or exposed artifacts into one node each |
| `--show-descriptions` | Include descriptions in node labels |
| `--hide-metadata` | Hide domain / layer metadata tags |
| `--max-label-length N` | Max label length before truncation (default: `50`) |

**Behavior**

| Option | Description |
| --- | --- |
| `--open` | Open the output file in the default viewer when done |
| `--force` | Overwrite an existing output file without prompting |
| `--quiet` | Suppress non-error output |
| `--graphviz-args ...` | Extra args passed through to Graphviz `dot` |
| `--debug` | Enable debug output and keep intermediate files |

### Examples

```bash
fluid viz-graph contract.fluid.yaml
fluid viz-graph contract.fluid.yaml --format html --theme dark --open
fluid viz-graph contract.fluid.yaml --plan runtime/plan.json --show-legend
fluid viz-graph contract.fluid.yaml --out docs/graph.svg --title "Customer Churn Pipeline"
```

Requires Graphviz (`dot`) on `PATH` for `svg`, `png`, and the enhanced `html` output (`brew install graphviz` on macOS; `apt install graphviz` on Debian/Ubuntu). If the enhanced renderer is unavailable, a lightweight `fluid graph` fallback emits plain DOT. A compatibility entry point `fluid viz-plan` still exists for rendering a saved plan as HTML, but new work should prefer `fluid viz-graph --plan runtime/plan.json`.
