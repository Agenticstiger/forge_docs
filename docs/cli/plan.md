# `fluid plan`

Stage 6 of the 11-stage pipeline. Generate an execution plan without applying changes, and emit the cryptographic digests (`bundleDigest` / `planDigest`) that stage 7 apply verifies before executing any DDL.

> **Why it matters**
> See exactly what will change — and prove it's what gets applied — before you touch production.
> `fluid plan` emits the action list plus a `planDigest` that `fluid apply` re-verifies, so the plan you reviewed is the plan that runs.

## Syntax

```bash
fluid plan CONTRACT [--env ENV] [--mode MODE] [--out PATH]
                    [--provider NAME] [--project PROJECT] [--region REGION]
                    [--validate-actions] [--estimate-cost] [--check-sovereignty]
                    [--html [PATH]] [--verbose]
```

`CONTRACT` is optional — when omitted, `plan` auto-finds `contract.fluid.yaml` in the current directory.

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay (dev, staging, prod) |
| `--mode` | Apply mode the plan is generated FOR. Stamped into `plan.json` so a later `fluid apply --mode X` can detect a mismatch and refuse. Choices: `amend` (default) \| `amend-and-build` \| `replace` \| `replace-and-build` \| `dry-run` \| `create-only`. When unset, the plan is generated mode-less. |
| `--out`, `--output` | Write the plan JSON, default `plan.json` in the current directory |
| `--verbose`, `-v` | Show detailed action information |
| `--validate-actions` | Validate generated provider actions against the ProviderAction SDK schema |
| `--estimate-cost` | Ask the provider to estimate cost |
| `--check-sovereignty` | *(since 0.15.0)* Resolve a real sovereignty verdict and name which source produced it — the provider's `validate_sovereignty` hook when it has one, otherwise the built-in policy engine (the same checker [`fluid validate`](./validate.md) runs), otherwise `NOT CHECKED`. **Exits 1 when the check fails.** Opt-in, off by default. See [Sovereignty gate](#sovereignty-gate-since-0-15-0). |
| `--provider` | Override the provider from the contract |
| `--project` | Override the project / account from the contract |
| `--region` | Override the region / location from the contract |
| `--html` | Generate an HTML visualization with a mermaid-rendered action DAG (colour-coded by mode: blue=amend, red=replace, grey=skipped). Optional path argument; defaults to `plan.html` in the current directory. |

## Plan binding

`0.8.0` plans embed two cryptographic digests:

- `bundleDigest` — SHA-256 of the tgz bundle the plan was derived from (matches `MANIFEST.json`'s merkle root). Set to `null` when planning from a raw YAML contract.
- `planDigest` — SHA-256 of the plan's action list itself (internal consistency check).

`fluid apply` re-verifies both before executing any DDL. Helpers live in `fluid_build/forge/core/plan_digest.py`:

- `compute_plan_digest(plan)` — canonical JSON → SHA-256
- `inject_digests(plan, bundle_digest)` — adds both fields
- `verify_plan_binding(plan_path, bundle_path)` — re-computes and compares; raises `PlanBindingError` on mismatch
- `PlanBindingError.kind` is a stable string (`"bundle-mismatch"` or `"plan-tamper"`) — CI log parsers can key off it.

The `--no-verify-plan-binding` flag on `apply` is the DR escape hatch for bypassing this check; see [`fluid apply`](./apply.md#safety-gates).

## Sovereignty gate (since 0.15.0)

`--check-sovereignty` stays **opt-in and off by default**, but on `0.15.0` it is a gate rather than a label. The verdict resolves in a fixed order, and the output always names which source answered:

1. The target provider's `validate_sovereignty` hook, when it returns a verdict.
2. Otherwise the **built-in policy engine** — the same sovereignty checker `fluid validate` runs, so the two stages cannot reach opposite verdicts on the same contract.
3. Otherwise `Sovereignty check: NOT CHECKED`, which is also what a contract declaring no `sovereignty` block gets. Exit code stays 0.

```
Sovereignty check: PASS  — source: built-in policy engine, enforcementMode=strict; the aws provider has no sovereignty hook
```

A failing check prints a `Sovereignty check: N finding(s)` header naming the source, then its findings as a bulleted list, then `❌ Sovereignty check FAILED`, and **exits 1**. The plan file is still written; the non-zero exit is what makes the flag usable as a CI gate.

On `0.14.1` and earlier none of that happened. No shipped provider implements `validate_sovereignty`, the hook helper returned an empty violation list for a hook that was absent (and for one that raised, because the invoker swallows the exception and hands back its first argument), and an empty list rendered as `Sovereignty check: PASS` with exit 0 — printed on contracts `fluid validate` rejects with two residency errors. The flag was also skipped outright when the provider failed to build. `PASS` is now printed only when a check actually ran and found nothing.

::: warning Behavior change in 0.15.0
A pipeline that already passes `--check-sovereignty` moves from a step that could only ever be green to one that can fail. Two rules decide whether it blocks: a region named in `deniedRegions` is an **error in every mode**, and everything else follows the contract's own `sovereignty.enforcementMode`, whose default is `strict`. Full table: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
:::

## Examples

### Basic plan

```bash
fluid plan contract.fluid.yaml
fluid plan contract.fluid.yaml --verbose
fluid plan contract.fluid.yaml --env prod --out runtime/prod-plan.json
```

### With HTML visualization (mermaid DAG)

```bash
fluid plan contract.fluid.yaml --html
# writes plan.json + plan.html in the current directory
```

The HTML report contains:

- A mermaid `graph TD` of the action DAG with per-mode colour coding
- A legend for the colour classes
- A collapsible raw-JSON drill-down for each action

Opening `plan.html` in a browser loads mermaid from `cdn.jsdelivr.net` (required online on first view). `securityLevel: 'strict'` is set in the mermaid init call; action ID / op strings flow through `html.escape(quote=True)` before rendering, so malicious contract values cannot smuggle `<script>` into a label.

For a richer DOT / Mermaid action-graph export, use [`fluid viz-graph`](#visualizing-the-plan-—-fluid-viz-graph) below — `plan` itself only emits the JSON plan and the optional `--html` summary.

### Hand-off to apply

```bash
fluid plan contract.fluid.yaml --out runtime/plan.json
fluid apply runtime/plan.json --mode amend --yes
# apply re-verifies bundleDigest + planDigest before any DDL
```

## Notes

- `plan` is the safest place to preview a provider override or environment overlay before you run `apply`.
- The generated plan can be passed to [`fluid apply`](./apply.md) — the digests pin the apply to exactly this plan.
- When planning from a tgz bundle directly, `bundleDigest` is populated from `MANIFEST.json`. When planning from a raw YAML contract, `bundleDigest` is `null` and only `planDigest` is verified.

## Visualizing the plan — `fluid viz-graph`

`fluid plan --html` emits a quick HTML summary alongside `runtime/plan.json`. For richer visualization — themed lineage and build-DAG diagrams — use `fluid viz-graph`:

```bash
fluid viz-graph CONTRACT [options]
```

### Key options

**Input / output**

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional). Optional, and ignored, when `--mesh` is used. |
| `--env ENV` | Apply an environment overlay |
| `--plan PATH` | Overlay a saved `runtime/plan.json` so build actions are shown on the graph |
| `--out PATH`, `--output PATH` | Output file path (default: `runtime/graph/contract.svg`) |
| `--mesh` | Mesh mode: walk `**/*.fluid.yaml` under the mesh root and render the cross-product DAG (SDP→ADP→CDP) built from each contract's `consumes[]`, instead of one contract's internal DAG. |
| `--mesh-root DIR` | Root directory for the mesh-mode walk. Default `.`. Ignored without `--mesh`. |

**Format & appearance**

| Option | Description |
| --- | --- |
| `--format {dot,svg,png,html,mermaid,json}` | Output format (default: `svg`). `svg` / `png` / `html` need Graphviz; `dot` / `mermaid` / `json` are pure-text. Passing `mermaid` or `json` without `--mesh` is rejected with `ERR_VALIDATION_ERROR`. |
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
