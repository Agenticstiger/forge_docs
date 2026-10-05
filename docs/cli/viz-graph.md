# `fluid viz-graph`

Render a FLUID contract as an interactive lineage and build graph (SVG, PNG, HTML, or Graphviz DOT).

## Syntax

```bash
fluid viz-graph [CONTRACT] [--mesh] [--mesh-root DIR] [--out PATH] [--format FMT] [--theme THEME] [--plan PLAN_JSON] [options]
```

## Key options

### Input / output

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml`. Optional, and ignored, when `--mesh` is used. |
| `--env` | Environment overlay to apply (e.g. `dev`, `prod`). |
| `--plan` | Optional `plan.json` file to overlay build actions on the graph. |
| `--out`, `--output` | Output file path. Default `runtime/graph/contract.svg`. |
| `--mesh` | Mesh mode: walk `**/*.fluid.yaml` under the mesh root and render the cross-product DAG (SDP→ADP→CDP) built from each contract's `consumes[]`, instead of one contract's internal DAG. |
| `--mesh-root` | Root directory for the mesh-mode walk. Default `.`. Ignored without `--mesh`. |

### Format & appearance

| Option | Description |
| --- | --- |
| `--format` | Output format: `dot`, `svg`, `png`, `html` in single-contract mode; `--mesh` additionally accepts `mermaid` and `json`. Default `svg`. `svg` / `png` / `html` need Graphviz; `dot` / `mermaid` / `json` are pure-text. Passing `mermaid` or `json` without `--mesh` is rejected with `ERR_VALIDATION_ERROR` and exit 2. Without Graphviz installed, `svg`, `png` and `html` do not fail: see [Without Graphviz](#without-graphviz). |
| `--theme` | Color theme: `dark` (default), `light`, `minimal` or `blueprint`. |
| `--custom-theme` | Path to a custom theme JSON or YAML file. |
| `--rankdir` | Graph layout direction: `LR`, `TB`, `RL`, `BT`. Default `LR`. |
| `--title` | Custom title for the graph. |

### Content options

| Option | Description |
| --- | --- |
| `--show-legend` | Add a legend explaining node types. |
| `--collapse-consumes` | Collapse all consumed sources into a single node. |
| `--collapse-exposes` | Collapse all exposed artifacts into a single node. |
| `--show-descriptions` | Include descriptions in node labels. |
| `--hide-metadata` | Hide domain / layer metadata tags. |
| `--max-label-length` | Maximum label length before truncation. Default `50`. |

### Behavior

| Option | Description |
| --- | --- |
| `--open` | Open the output file in the default viewer when done. |
| `--force` | Overwrite the existing output file without prompting. |
| `--quiet` | Suppress non-error output. |

### Advanced

| Option | Description |
| --- | --- |
| `--graphviz-args ...` | Extra arguments forwarded to the Graphviz `dot` command. |
| `--debug` | Enable debug output and save intermediate files. |

## Examples

```bash
fluid viz-graph contract.fluid.yaml
fluid viz-graph contract.fluid.yaml --format html --theme dark --open
fluid viz-graph contract.fluid.yaml --theme blueprint --show-legend
fluid viz-graph contract.fluid.yaml --plan runtime/plan.json
fluid viz-graph contract.fluid.yaml --out docs/graph.svg --title "Customer Churn Pipeline"
```

## Without Graphviz

`svg`, `png` and `html` are rendered by the Graphviz `dot` binary (`brew install graphviz` on macOS, `apt-get install graphviz` on Debian/Ubuntu). When `dot` is not on the `PATH`, the command still exits `0`. It logs `graphviz_not_available_writing_dot` and writes a DOT file next to where the requested output would have gone:

```bash
fluid viz-graph contract.fluid.yaml --out g.svg --force
ls g.*
```

```text
g.dot
```

Check for the file you asked for. In CI, use `--format dot`, or `--format mermaid` or `--format json` with `--mesh`, which need no binary.

## Notes

- There is no `fluid graph` command or alias: `fluid graph contract.fluid.yaml` exits 2 with `invalid choice: 'graph'`.
- See [`fluid plan`](./plan.md) for a non-graphical execution preview.
