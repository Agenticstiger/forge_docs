# `fluid plan`

Stage 6 of the 11-stage pipeline. Generate an execution plan without applying changes, and emit the cryptographic digests (`bundleDigest` / `planDigest`) that stage 7 apply verifies before executing any DDL.

> **Why it matters**
> See exactly what will change — and prove it's what gets applied — before you touch production.
> `fluid plan` emits the action list plus a `planDigest` that `fluid apply` re-verifies, and records the `--mode` and `--env` it was made for, so the plan you reviewed is the plan that runs.

## Plan, then apply

```bash
# Plan, then apply the plan with the same mode
fluid plan contract.fluid.yaml --env prod --out runtime/plan.json
fluid apply runtime/plan.json --yes

# A build-augmented or destructive apply needs a plan made for that mode
fluid plan contract.fluid.yaml --env prod --mode amend-and-build --out runtime/plan.json
fluid apply runtime/plan.json --mode amend-and-build --yes
```

`CONTRACT` may also be a bundle (`.tgz`) written by [`fluid bundle`](./bundle.md).

## Syntax

```bash
fluid plan CONTRACT [--env ENV] [--mode MODE] [--out PATH]
                    [--provider NAME] [--project PROJECT] [--region REGION]
                    [--validate-actions] [--estimate-cost]
                    [--check-sovereignty | --no-check-sovereignty]
                    [--html [PATH]] [--verbose]
```

`CONTRACT` is optional — when omitted, `plan` auto-finds `contract.fluid.yaml` in the current directory.

## Key options

| Option | Description |
| --- | --- |
| `--env` | Apply an environment overlay (dev, staging, prod). An environment with no overlay logs `overlay_not_found` and runs on the base contract; [`--env` and environment overlays](./validate.md#env-and-environment-overlays) says when it fails instead. See [Environments and overlays](../concepts/environments-and-overlays.md#when-no-overlay-matches). |
| `--mode` | Apply mode the plan is generated FOR. Stamped into `plan.json` so a later `fluid apply --mode X` can detect a mismatch and refuse (`apply_plan_mode_mismatch`, exit 1). Choices: `amend` \| `amend-and-build` \| `replace` \| `replace-and-build` \| `dry-run` \| `create-only`. When unset, the plan records no mode, and apply treats that as `amend`. |
| `--out`, `--output` | Write the plan JSON, default `plan.json` in the current directory |
| `--verbose`, `-v` | Show detailed action information |
| `--validate-actions` | Validate generated provider actions against the ProviderAction SDK schema |
| `--estimate-cost` | Ask the provider to estimate cost |
| `--check-sovereignty` | *(since 0.15.0)* Resolve a real sovereignty verdict and name which source produced it — the provider's `validate_sovereignty` hook when it has one (the `gcp` provider has one since 0.17.0), otherwise the built-in policy engine (the same checker [`fluid validate`](./validate.md) runs), otherwise `NOT CHECKED`. **Exits 1 when the check fails.** *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `plan` checks the policy without this flag too, and refuses before it writes a plan; the flag adds the provider's hook and the printed verdict. See [Sovereignty gate](#sovereignty-gate-since-0-15-0). |
| `--no-check-sovereignty` | *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* Skip the sovereignty check `plan` runs by default, and write the plan whatever the policy says. Prints a warning and logs a WARNING (`sovereignty_check_skipped`). `fluid apply` keeps its own checks. |
| `--provider` | Override the provider from the contract |
| `--project` | Override the project / account from the contract |
| `--region` | Override the region / location from the contract |
| `--html` | Generate an HTML visualization with a mermaid-rendered action DAG (colour-coded by mode: blue=amend, red=replace, grey=skipped). Optional path argument; defaults to `plan.html` in the current directory. |

## Plan binding

`0.8.0` plans embed two cryptographic digests:

- `bundleDigest` — SHA-256 of the tgz bundle the plan was derived from (matches `MANIFEST.json`'s merkle root). An empty string when planning from a raw YAML contract.
- `planDigest` — SHA-256 of the plan's action list itself (internal consistency check).

`fluid apply` re-verifies both before executing any DDL. Helpers live in `fluid_build/forge/core/plan_digest.py`:

- `compute_plan_digest(plan)` — canonical JSON → SHA-256
- `inject_digests(plan, bundle_digest)` — adds both fields
- `verify_plan_binding(plan_path, bundle_path)` — re-computes and compares; raises `PlanBindingError` on mismatch
- `PlanBindingError.kind` is a stable string (`"bundle-mismatch"`, `"plan-tamper"` or `"bundle-missing"`). `fluid apply` surfaces it as the event `apply_plan_digest_<kind>` with `-` written as `_` — CI log parsers can key off it.

The `--no-verify-plan-binding` flag on `apply` is the DR escape hatch for bypassing this check; see [`fluid apply`](./apply.md#safety-gates).

### What `plan.json` records

Besides the digests, `plan.json` carries what `apply` needs to refuse a plan that is being used for something it was not made for. This is a trimmed excerpt of a plan made with `fluid plan contract.fluid.yaml --env dev --mode amend-and-build`:

```json
{
  "mode": "amend-and-build",
  "bundleDigest": "",
  "planDigest": "sha256:227ff7dab5d3a...",
  "contract_metadata": {
    "env": "dev",
    "id": "gold.customer.analytics_360_v1",
    "name": "Customer 360 Analytics",
    "source_path": ".../contract.fluid.yaml",
    "version": "0.7.5"
  },
  "contract": { "...": "the resolved contract, overlay applied" },
  "actions": [ "..." ]
}
```

| Field | Written when | What `apply` does with it |
| --- | --- | --- |
| `mode` | Always; `null` without `--mode`. | `fluid apply plan.json --mode Y` with a `Y` other than the recorded mode is refused with `apply_plan_mode_mismatch`, before any build. A missing mode and `amend` count as the same. |
| `contract_metadata.env` | `--env` was given, or the plan was made from a bundle that records an env. | In a build mode (`amend-and-build`, `replace-and-build`), `apply` without `--env` runs the builds in that env, and a different `--env` is refused with `plan_env_mismatch`. See [`fluid apply`](./apply.md#the-plan-s-environment). |
| `contract_metadata.source_contract` | The plan was made from a bundle. | Names the source contract file the bundle was built from. |
| `contract` | Always. | Apply runs the embedded contract, which already has the overlay applied. *([forge-cli #714](https://github.com/Agenticstiger/forge-cli/pull/714), since 0.20.0)* It validates it against its schema first, on both engines, and refuses a plan with no embedded contract with `apply_plan_missing_contract`. See [Contract validation](./apply.md#contract-validation). |

A bundle is never re-overlaid: `fluid plan bundle.tgz --env prod` on a bundle built for `dev` is refused with `bundle_env_mismatch`. Plan the bundle without `--env`, or rebuild it with `fluid bundle <contract> --env prod --format tgz`.

## Sovereignty gate (since 0.15.0)

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `fluid plan` checks the contract's sovereignty policy by default, before it plans. It asks the built-in policy engine, the checker [`fluid validate`](./validate.md) runs, and refuses what `validate` refuses:

- Under `enforcementMode: strict`, the schema default, the findings that block include a binding outside `allowedRegions`, one in a region of another jurisdiction, and one on AWS, GCP, Azure or Databricks that declares no region (the platform would pick it).
- In every mode, a binding in a region listed in `deniedRegions` blocks.

A refusal exits 1 with `ERR_SOVEREIGNTY_VIOLATION` and writes no plan. A plan file an earlier run left at `--out` stays as it was. The check builds no provider, so it needs no cloud SDK and no credentials. When nothing blocks it prints nothing, and the plan is written as before: for a contract with no `sovereignty` block, and for one whose findings are only warnings or info lines (under `advisory` or `audit`, every finding but a denied region).

This is the refusal on 0.30.0 for a contract with `enforcementMode: strict`, `allowedRegions: [eu-central-1, eu-west-1]`, `deniedRegions: [us-west-2]` and one binding in `us-west-2`:

```text
Sovereignty check: 3 finding(s)  — source: built-in policy engine, enforcementMode=strict
  - ❌ [customer_events] Region 'us-west-2' is explicitly denied by sovereignty policy
   💡 Use one of the allowed regions: eu-central-1, eu-west-1
  - ❌ [customer_events] Region 'us-west-2' not in allowed regions list
   💡 Allowed regions: eu-central-1, eu-west-1
  - ❌ [customer_events] Region 'us-west-2' (jurisdiction: US) does not match required jurisdiction: EU
   💡 Consider using regions in EU jurisdiction

❌ Sovereignty check FAILED — enforcementMode is 'strict'.
❌ sovereignty_violation  [ERR_SOVEREIGNTY_VIOLATION]
  command: plan
  contract: .../contract.fluid.yaml
  errors: ["[customer_events] Region 'us-west-2' is explicitly denied by sovereignty policy", "[customer_events] Region 'us-west-2' not in allowed regions list", "[customer_events] Region 'us-west-2' (jurisdiction: US) does not match required jurisdiction: EU"]
  message: The contract's sovereignty policy (enforcementMode strict) blocks where it puts data, so fluid plan wrote no plan.
...
```

Each finding names its expose in brackets, and the error carries the findings as `errors`. The suggestions printed after it are listed under [`sovereignty_violation`](../advanced/error-codes.md#sovereignty-violation).

Up to 0.29.0 the check was opt-in: plain `fluid plan` wrote a plan for this contract and exited 0. To write the plan anyway now, pass [`--no-check-sovereignty`](#no-check-sovereignty).

::: warning Behavior change in 0.30.0
A script or pipeline that runs `fluid plan` on a contract `fluid validate` refuses for sovereignty now stops at plan, with exit 1 and no plan file. See [Changes in 0.30.0](../upgrading.md#changes-in-0-30-0).
:::

### `--check-sovereignty`

`--check-sovereignty` runs the same check first. If nothing blocks, plan then resolves a verdict and prints it, naming which source answered, in a fixed order:

1. The target provider's `validate_sovereignty` hook, when it returns a verdict.
2. Otherwise the **built-in policy engine** — the same sovereignty checker `fluid validate` runs, so the two stages cannot reach opposite verdicts on the same contract.
3. Otherwise `Sovereignty check: NOT CHECKED`, which is also what a contract declaring no `sovereignty` block gets. Exit code stays 0.

On `aws` the answer comes from the built-in policy engine, because the provider has no hook:

```
Sovereignty check: PASS  — source: built-in policy engine, enforcementMode=strict; the aws provider has no sovereignty hook
```

Since 0.17.0 the `gcp` provider has a hook, so a `gcp` contract is answered by the provider. The hook runs the same contract checks and then checks where the plan would put things: the planned actions and the OpenTofu resources the apply would emit, such as the BigQuery dataset and the Cloud KMS key ring. A binding with no region is checked as the placement the platform would give it, which for BigQuery is `US`. This is real output for a contract whose allowed region is `europe-west1`, first with its binding in that region and then in `us-central1`:

```
Sovereignty check: PASS  — source: gcp provider hook
```

```
Sovereignty check: 10 violation(s)  — source: gcp provider hook
  - orders: Region 'us-central1' not in allowed regions list
  - orders: Region 'us-central1' (jurisdiction: US) does not match required jurisdiction: EU
  - dataset_sales: Region 'us-central1' not in allowed regions list
  ...
  - google_kms_key_ring.gold_sales_orders_v1_sales_kms: Region 'us-central1' not in allowed regions list
  ...
❌ sovereignty_violation  [ERR_SOVEREIGNTY_VIOLATION]
```

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* The second output predates 0.30.0. Now the default check runs first and refuses that contract under `strict` before the hook is asked: 0.30.0 prints the built-in engine's two findings for the `us-central1` binding (`not in allowed regions list` and the jurisdiction mismatch) and writes no plan. The hook's verdict is printed when the engine finds no error.

The pipeline `fluid generate ci --system github` writes runs `fluid plan ... --check-sovereignty` in its plan job, and the Jenkins pipeline's stage 6 does the same.

A failing check prints a `Sovereignty check: N finding(s)` header naming the source, then its findings as a bulleted list, then `❌ Sovereignty check FAILED`, and **exits 1**. *([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* It writes no plan, as the default check does. Up to 0.29.0 the plan file was still written, and only the non-zero exit stopped a pipeline.

On `0.14.1` and earlier none of that happened. No shipped provider implemented `validate_sovereignty`, the hook helper returned an empty violation list for a hook that was absent (and for one that raised, because the invoker swallows the exception and hands back its first argument), and an empty list rendered as `Sovereignty check: PASS` with exit 0 — printed on contracts `fluid validate` rejects with two residency errors. The flag was also skipped outright when the provider failed to build. `PASS` is now printed only when a check actually ran and found nothing.

::: warning Behavior change in 0.15.0
A pipeline that already passes `--check-sovereignty` moves from a step that could only ever be green to one that can fail. Two rules decide whether it blocks: a region named in `deniedRegions` is an **error in every mode**, and everything else follows the contract's own `sovereignty.enforcementMode`, whose default is `strict`. Full table: [Governance → Sovereignty enforcement modes](../advanced/governance.md#sovereignty-enforcement-modes-since-0-15-0).
:::

### `--no-check-sovereignty`

*([forge-cli #868](https://github.com/Agenticstiger/forge-cli/pull/868), since 0.30.0)* `--no-check-sovereignty` skips the check and writes the plan whatever the policy says:

```bash
fluid plan contract.fluid.yaml --no-check-sovereignty --out runtime/plan.json
```

```text
⚠️  Sovereignty check skipped (--no-check-sovereignty): the plan is written whatever the contract's sovereignty policy says.
```

It also logs a WARNING with the event `sovereignty_check_skipped`, so the skip is on record. It changes nothing in `fluid apply`, which keeps its own checks; [Where sovereignty is enforced](../advanced/governance.md#where-sovereignty-is-enforced) lists them.

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
fluid plan contract.fluid.yaml --env prod --mode amend --out runtime/plan.json
fluid apply runtime/plan.json --mode amend --yes
# apply re-verifies bundleDigest + planDigest, the mode and the env before any DDL
```

`amend` is the default, so `--mode amend` may be left off on both sides. For any other mode, pass the same `--mode` to both commands: `fluid apply` refuses a plan whose recorded mode differs, with `apply_plan_mode_mismatch`.

## Notes

- `plan` is the safest place to preview a provider override or environment overlay before you run `apply`.
- *(since 0.27.0, [forge-cli #813](https://github.com/Agenticstiger/forge-cli/pull/813))* For a contract with `builds`, `plan` prints the warning [`fluid validate` gives](./validate.md#an-id-the-build-phase-refuses) for an `id` or `builds[].id` the build phase refuses, and still writes the plan, whatever `--mode` says. `fluid apply` in a build mode refuses that id before it applies anything; see [Build ids](./apply.md#build-ids).
- The generated plan can be passed to [`fluid apply`](./apply.md) — the digests pin the apply to exactly this plan.
- When planning from a tgz bundle directly, `bundleDigest` is populated from `MANIFEST.json`. When planning from a raw YAML contract, `bundleDigest` is an empty string and only `planDigest` is verified.

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
| `--theme NAME` | Color theme: `dark` (default), `light`, `minimal` or `blueprint` |
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

Requires Graphviz (`dot`) on `PATH` for `svg`, `png`, and the enhanced `html` output (`brew install graphviz` on macOS; `apt install graphviz` on Debian/Ubuntu). Without Graphviz, `fluid viz-graph --format svg` (and `png`, `html`) does not fail: it logs `graphviz_not_available_writing_dot`, writes the graph as DOT next to the requested output (`runtime/graph/contract.dot` for the default path) and exits 0. Use `--format dot` to ask for DOT directly. There is no `fluid graph` command. A compatibility entry point `fluid viz-plan` still exists for rendering a saved plan as HTML, but new work should prefer `fluid viz-graph --plan runtime/plan.json`.
