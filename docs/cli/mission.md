# `fluid mission`

Declarative, verifiable goals for a data product. A **mission** is a YAML file that pairs a
plain-language `goal` with **deterministic `success_criteria`** — and the criteria, not the model,
decide when the mission is done.

`fluid mission check` runs those criteria with **zero LLM calls**, so it drops straight into CI.
`fluid mission run` adds the autonomous loop: the model plans and edits, the code-owned checks
re-run against the re-read contract on disk after every cycle, and the run terminates only when
they pass (or when a budget, iteration, or stall ceiling fires).

::: tip New in `0.13.0`
`fluid mission` ships in `v0.13.0`. See [Release Notes `0.13.0`](../RELEASE_NOTES_0.13.0.md).
:::

## Syntax

```bash
fluid mission <check|run|trust|list> [options]
```

Exit codes are shared across `check` and `run`:

| Code | Meaning |
| --- | --- |
| `0` | Scorecard green — every non-advisory criterion passed. |
| `1` | Scorecard red — at least one non-advisory criterion failed. |
| `2` | Harness error — bad spec, untrusted spec, unreadable contract, or a failed run. |

## Subcommands

### `fluid mission check <spec> [contract]`

Load the spec (trust-gated), re-read the on-disk contract, run every success criterion, and render
a scorecard. **No LLM is involved** — this is a pure gate and safe to run in CI.

| Argument / Option | Description |
| --- | --- |
| `<spec>` | Mission name (e.g. `quality-coverage`) or a path to a spec YAML file. |
| `[contract]` | Contract to verify. Default `contract.fluid.yaml`. |
| `--json` | Emit the scorecard as JSON instead of the rendered table. |

### `fluid mission run <spec> [contract]`

Run the mission autonomously: **VERIFY → PLAN → EXECUTE → GATE → PROGRESS**, repeating until the
deterministic checks pass or a ceiling fires. Needs a configured LLM provider.

| Argument / Option | Description |
| --- | --- |
| `<spec>` | Mission name or spec YAML path. |
| `[contract]` | Contract to work on. Default `contract.fluid.yaml`. |
| `--resume` | Re-enter the newest unfinished run for this mission. VERIFY is idempotent, so resuming just re-verifies what is on disk — there is no replay. |
| `--run-id <id>` | Target a specific mission run id. |
| `--llm-provider <name>` | LLM provider (default: your configured provider). |
| `--llm-model <id>` | LLM model id. |
| `--workspace <dir>` | Workspace root for receipts and tool confinement (default: auto-detected). |
| `--json` | Emit the outcome as JSON. |

### `fluid mission trust <spec>`

One-time, direnv-style approval of a workspace spec: records the file's `sha256` in
`~/.fluid/mission_trust.json`. Editing the file requires re-approval. Built-ins and user-global
specs (`~/.fluid/missions/`) are trusted implicitly — trusting them is a no-op.

### `fluid mission list`

List every discoverable mission spec (built-in, user-global, workspace) with its trust status and
description.

## Examples

```bash
fluid mission list                                   # what's available, and is it trusted?
fluid mission check quality-coverage                 # zero-LLM gate against ./contract.fluid.yaml
fluid mission check gdpr-clean ./contract.fluid.yaml --json   # machine-readable, for CI
fluid mission trust .fluid/missions/my-mission.yaml  # approve a workspace spec (pins its sha256)
fluid mission run gdpr-clean                         # autonomous loop until the checks pass
fluid mission run gdpr-clean --resume                # re-enter a paused run
```

## Built-in missions

Two flagship missions ship with the CLI.

| Name | Goal |
| --- | --- |
| `gdpr-clean` | Every PII column is classified with provenance, every MCP-exposed port carries an `agentPolicy` with retention limits, and the contract validates. |
| `quality-coverage` | Every exposed output port carries at least one data-quality rule and the contract validates against its declared `fluidVersion` schema. |

## Spec format

A mission spec is snake_case YAML. `name`, `description`, `goal`, and `success_criteria` are the
substance; `budgets`, `gates`, `tools`, and `plan_hint` configure the autonomous runner. Unknown
keys are rejected loudly — a typo must never silently weaken a criterion.

```yaml
name: quality-coverage
description: Reach data-quality rule coverage on every output port.
goal: >
  Every exposed output port carries at least one data-quality rule and
  the contract validates against its declared fluidVersion schema.
success_criteria:
  - check: validate
  - check: predicate
    path: "exposes[*].contract.dq.rules"
    op: exists
budgets:
  max_usd: 3.00
  max_iterations: 4
  max_wall_seconds: 1200
gates:
  destructive: ask
tools:
  allow:
    - discover_workspace
    - read_sample_schema
    - validate_contract
    - propose_contract
plan_hint:
  - inspect
  - add_dq_rules
```

### `success_criteria`

Every non-advisory criterion must pass. Set `advisory: true` to report a criterion on the scorecard
without gating on it. Three check types ship in v1:

| `check` | What it does |
| --- | --- |
| `validate` | Runs the same in-process schema validation `fluid validate` runs, with exit-0 semantics. |
| `ai_ready` | Reuses the AI-readiness agent. `require` accepts `sensitive_exposes_annotated` and `missing_descriptions`. |
| `predicate` | Evaluates a dotted path over the contract dict. |

The `predicate` mini-language is **deliberately frozen**: dotted paths, `[*]` array fan-out, and the
operators `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `exists`, `contains`. No filters, no functions, no
extensibility hooks. Fan-out is fail-closed — a port with no `dq.rules`, an empty list, or no ports
at all fails the criterion.

```yaml
  - check: predicate
    path: "exposes[*].policy.agentPolicy.retentionPolicy.maxRetentionDays"
    op: lte
    value: 30
```

### `budgets`

| Key | Meaning |
| --- | --- |
| `max_usd` | Hard per-run spend ceiling. Re-summed from on-disk receipts each cycle, so pause/resume cannot reset spend. |
| `max_iterations` | Maximum outer cycles. |
| `max_wall_seconds` | Deadline checked before every step and every check; the remaining time becomes the per-call LLM timeout. |

Overshoot is bounded but nonzero — one in-flight call can cross the line.

### `gates`

`gates.destructive` is `ask` or `deny`. On a non-TTY it resolves to **deny** — the gate fails
closed, and `--yes` never approves a destructive diff. This is what stops a model from satisfying
"every column has a description" by deleting columns.

### `tools`

`tools.allow` is an allowlist, intersected with the live tool registry inside the agent loop. The
planner may reorder or drop `plan_hint` steps; it can never add a tool that is not on the list.

## How the loop terminates

The load-bearing inversion: **only the code-owned checks may declare success.** There is no "finish"
action available to the model. Every cycle begins by re-reading and re-hashing the contract on disk
and re-running the criteria against it — so:

- **Resume is free.** VERIFY is idempotent and reads only from disk. A paused, stalled, or crashed
  run re-enters at VERIFY with no replay machinery; the scorecard is simultaneously the termination
  authority and the resume pointer.
- **Self-healing is free.** Failing-check diagnostics are recycled verbatim as the next cycle's
  repair feedback. Verification failure *is* the repair prompt.
- **Every proposed write passes the destructive gate** before it lands.

A run's `status` stays inside `running | paused | complete | failed`. A `paused` run carries a
`pause_reason` of `stalled`, `budget`, `timeout`, `iterations`, or `gate_rejected`.

## Trust boundary

A mission spec configures autonomous execution — tool allowlist, gate mode, budgets, and the goal
text that reaches the planner. A cloned repo shipping `.fluid/missions/` must therefore not silently
control any of it.

| Source | Trust |
| --- | --- |
| Built-in (shipped with the CLI) | Trusted implicitly. |
| `~/.fluid/missions/` (user-global, outside any repo) | Trusted implicitly. |
| `.fluid/missions/` (workspace) and arbitrary paths | **Requires `fluid mission trust`**, pinned by the file's `sha256`. |

The gate **fails closed**: an unpinned or changed spec is refused with a
`mission_untrusted_spec_refused` WARNING before anything the spec configures takes effect. A changed
file needs re-approval. There is no bypass environment variable — `fluid mission trust` is the only
way to approve.

## Receipts

`fluid mission run` writes to `<workspace>/.fluid/missions/<run-id>/`, mirroring the
`.fluid/agents/<run-id>/` convention:

```
.fluid/missions/<run-id>/
    manifest.json               run-level state (the resume pointer)
    scorecard.json              latest VERIFY result
    cycles/<n>/scorecard.json   per-cycle scorecard
    cycles/<n>/cost.json        per-cycle cost receipt
    cycles/<n>/plan.json        the planner's step list
```

A run id is an opaque **single path segment**, validated as such — this is a security boundary, not
cosmetics ([`0.13.0` security fixes](../RELEASE_NOTES_0.13.0.md#security)).

## Using `mission check` in CI

`check` is the CI-safe half: no LLM, no network, no credentials.

```yaml
- name: Mission gate
  run: |
    pip install data-product-forge==0.13.0
    fluid mission check quality-coverage contract.fluid.yaml
```

Non-zero exit fails the job. Add `--json` if you want to post the scorecard as a check annotation.

## See also

- [`fluid validate`](./validate.md) — the schema-validation stage the `validate` check wraps
- [`fluid agents`](./agents.md) — the sibling `.fluid/agents/<run-id>/` receipt stack
- [`fluid stats`](./stats.md) — aggregate spend across runs
- [Release Notes `0.13.0`](../RELEASE_NOTES_0.13.0.md)
