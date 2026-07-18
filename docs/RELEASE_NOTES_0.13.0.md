# Fluid Forge Docs Baseline: CLI `0.13.0`

**Release Date:** July 18, 2026
**Status:** Current stable docs baseline (supersedes [`0.12.0`](./RELEASE_NOTES_0.12.0.md))

## Headline

`0.13.0` is the **verifiable-autonomy + declarative-packaging** release.

The headline is a new top-level command: [**`fluid mission`**](./cli/mission.md). A mission is a
YAML file pairing a plain-language goal with **deterministic success criteria** — and the criteria,
not the model, decide when the work is done. `fluid mission check` runs those criteria with **zero
LLM calls** and drops straight into CI. `fluid mission run` adds the autonomous
VERIFY → PLAN → EXECUTE → GATE → PROGRESS loop, in which the model plans and edits but has no
mechanism to terminate the run.

Alongside it, **declarative packaging modes** land in the `0.7.6` **preview** schema: a `packaging`
block declares, per infrastructure container, whether this product **owns** it (`isolated`) or
writes into a pre-existing **platform-owned pool** (`shared`). A shared container is emitted as an
OpenTofu *data source* plus leaf-only resources — so a tenant's product structurally cannot destroy
a pool. `0.7.5` remains the stable default; `0.7.6` is opt-in.

And a correctness fix worth reading if you grant cross-project or cross-account access:
**`accessPolicy` is now the IaC access-grant surface.** The GCP plugin previously read
`metadata.policies`, which **no shipped schema permits** — so the documented cross-project mechanism
was not expressible in a contract that passes `fluid validate`. See
[accessPolicy](#accesspolicy-is-now-the-iac-access-grant-surface) below.

`pip install --upgrade data-product-forge`.

::: tip Who should upgrade
Anyone who wants agentic contract work that a CI gate can actually verify (`fluid mission`);
platform teams running **multi-tenant shared infrastructure pools** on AWS / GCP / Snowflake
(packaging modes); anyone granting **cross-project or cross-account** access from a contract (the
`accessPolicy` fix); and anyone using the **semantic layer** — several correctness fixes below
changed the numbers a governed query returns.
:::

## What changed in `v0.13.0`

### Added — `fluid mission` (declarative, verifiable goals)

[`fluid mission`](./cli/mission.md) has four subcommands:

| Subcommand | What it does |
| --- | --- |
| `fluid mission check <spec> [contract]` | Run the spec's success criteria against the on-disk contract and render a scorecard. **Zero LLM calls** — safe as a standalone CI gate. |
| `fluid mission run <spec> [contract]` | Run the mission autonomously until the code-owned checks pass or a ceiling fires. `--resume` re-enters an unfinished run. |
| `fluid mission trust <spec>` | One-time, direnv-style approval of a workspace spec — pins its `sha256`. |
| `fluid mission list` | Available specs (built-in / user-global / workspace) with trust status. |

Exit codes: `0` scorecard green, `1` scorecard red, `2` harness error.

Two flagship missions ship built in: **`gdpr-clean`** (every PII column classified with provenance,
every MCP-exposed port carrying an `agentPolicy` with retention limits) and **`quality-coverage`**
(every exposed output port carries at least one data-quality rule).

**Only code-owned checks can declare success.** There is no "finish" action available to the model.
Every cycle re-reads and re-hashes the contract on disk and re-runs the criteria against it. Three
consequences:

- **Resume is free.** VERIFY is idempotent and reads only from disk, so a paused, stalled, or
  crashed run re-enters at VERIFY with no replay machinery — the scorecard is simultaneously the
  termination authority and the resume pointer.
- **Self-healing is free.** Failing-check diagnostics are recycled verbatim as the next cycle's
  repair feedback.
- **Anti-gaming is enforced.** Every proposed write passes the destructive gate before it lands, so
  a model cannot satisfy "every column has a description" by deleting columns. The gate **fails
  closed**: on a non-TTY it resolves to deny, and `--yes` never approves a destructive diff.

Success criteria come in three v1 check types — `validate` (the same in-process validation
`fluid validate` runs), `ai_ready`, and `predicate`. The `predicate` mini-language is **deliberately
frozen**: dotted paths, `[*]` array fan-out, and the operators
`eq / ne / lt / lte / gt / gte / exists / contains`. Nothing more.

**`.fluid/missions/` is a trust boundary.** A spec configures autonomous execution — tool allowlist,
gate mode, budgets, and the goal text that reaches the planner — so a cloned repo must not silently
control any of it. Built-ins and user-global specs (`~/.fluid/missions/`) are trusted implicitly;
workspace specs and arbitrary paths require `fluid mission trust`, pinned by the file's `sha256`
(a changed file needs re-approval). There is no bypass environment variable.

Budgets (`max_usd`, `max_iterations`, `max_wall_seconds`) are hard and cumulative — spend is
re-summed from on-disk receipts each cycle, so pause/resume cannot reset it. Overshoot is bounded
but nonzero: one in-flight call can cross the line.

Receipts land in `<workspace>/.fluid/missions/<run-id>/` (`manifest.json`, `scorecard.json`, and
per-cycle `scorecard.json` / `cost.json` / `plan.json`), mirroring the existing
`.fluid/agents/<run-id>/` convention.

### Added — declarative packaging modes (`0.7.6` preview)

A new `packaging` block in the **`0.7.6` preview** schema declares container ownership:

```yaml
fluidVersion: "0.7.6"          # preview — 0.7.5 remains the stable default
packaging:
  mode: shared                 # isolated | shared
  pool: analytics-pool-eu      # REQUIRED whenever any container resolves 'shared'
  containers:                  # per-kind overrides win over `mode`
    warehouse: isolated        # hybrid tier: shared database, own warehouse
```

- **`isolated`** emits an owned OpenTofu **resource** — today's exact emit.
- **`shared`** emits a **data source** referencing a pre-existing, platform-owned pool, plus
  leaf-only owned resources (tables, prefixed objects, scoped grants). The product writes into the
  pool but cannot destroy it.
- Six container kinds: `bucket`, `database`, `dataset`, `schema`, `warehouse`, `cluster`. (`cluster`
  accepts `shared` only in v1 — dedicated Confluent cluster provisioning is not yet supported.)
- `binding.packaging` overrides the contract-wide block per exposure. Precedence is
  `binding.packaging` > top-level `packaging` > absent.
- **An absent `packaging` block is a distinct LEGACY sentinel**, not a synonym for `isolated`: the
  IaC emit is **byte-identical** to pre-packaging releases, golden-pinned. Every existing contract
  is unaffected.
- `pool` propagates as the `fluid_pool` label/tag for cost attribution. Optional `poolManifest`
  snapshots the platform team's pool file into the bundle so `bundleDigest` covers it.

**Ownership-transition guard.** Changing a container's mode changes who owns it, but OpenTofu only
sees a resource that left the configuration and plans a **destroy** — on a pool, that reaches every
other tenant's data. So the ownership model is diffed against `tofu state list` **before**
`tofu plan`, and a transition fails closed with copy-pasteable `tofu state rm` remediation:

- **`isolated` → `shared`** (owned → referenced) is **always blocked**. There is no flag; the only
  correct move is to drop the resource from state first, which touches zero bytes of infrastructure.
- **`shared` → `isolated`** (referenced → owned) requires the new
  [`fluid apply --adopt-shared-container`](./cli/apply.md#packaging-modes) flag, which
  emits a structured `packaging_adoption_override` audit event — the same discipline as
  `--allow-data-loss`. Without the gate, brownfield adoption would `tofu import` the platform's pool
  into this product's state with `force_destroy` restored.

Detection is deliberately conservative — over-flagging asks a human to look; under-flagging destroys
a pool. Structured `packaging_transition_blocked` / `packaging_adoption_override` events are emitted
for CI log scrapers. The existing data-loss gate is untouched and remains the unconditional last
line. LEGACY contracts resolve to the sentinel and can never transition, so the guard is a provable
no-op for every pre-existing contract.

**`plan.json` tells the truth.** Under `packaging.mode: shared` the plan no longer lists a create
action for a container the product does not own; a packaging summary is included in the
digest-bound artifact a human approves.

See [`fluid generate iac`](./cli/generate-iac.md#packaging-modes) for the emitted
shapes per provider.

### `accessPolicy` is now the IaC access-grant surface

**Read this if you grant cross-project (GCP) or cross-account (AWS) access from a contract.**

The GCP IaC plugin read `contract.metadata.policies` to emit BigQuery `access[]` entries and GCS IAM
members. That surface is **not in any shipped schema** — every version from `0.7.1` to `0.7.6`
declares `metadata` with `additionalProperties: false` and no `policies` property — so a contract
carrying it fails `fluid validate`:

```
metadata: Additional properties are not allowed ('policies' was unexpected)
```

`fluid generate iac` does not run schema validation, so the emit path worked while the contract was
unusable everywhere else. **Users could not express a cross-project grant in a contract that
validates.**

The fix reads the schema-valid, already-documented root-level **`accessPolicy`** surface:

```yaml
accessPolicy:
  grants:
    - principal: "serviceAccount:consumer@other-project.iam.gserviceaccount.com"
      permissions: [read, select, query]
    - principal: "group:data-analytics@company.com"
      permissions: [read]
```

- **`metadata.policies` still emits**, for back-compat with out-of-tree contracts — but it remains
  schema-invalid and is **deprecated**. Both surfaces are read (rather than either/or) so a contract
  mid-migration does not silently drop half its grants; duplicates collapse. **Migrate to
  `accessPolicy`.**
- **A latent bug is fixed for free.** The legacy reader classified a principal by `"@" in principal`
  — user if it had an `@`, group otherwise. Group addresses contain `@` too, so **every group was
  emitted as a BigQuery `user_by_email` entry**. `accessPolicy` principals carry an explicit
  `user:` / `group:` / `serviceAccount:` prefix, so the type is *declared* rather than guessed.
  Unprefixed legacy values keep the exact old inference, so existing emitted ACLs do not silently
  change — **declare `group:` to get a group entry.**
- **Snowflake is deliberately not unified here.** `security.access_control.grants` is Snowflake-native
  RBAC and does not map onto `accessPolicy`'s `{principal, permissions, resources}` without real
  loss (masking / row-access policies have no equivalent at all). That surface needs its own schema
  decision; it is tracked, not papered over.

See [GCP provider — access grants](./providers/gcp.md#access-grants-accesspolicy).

### Semantic layer — correctness and round-tripping

Several fixes here **change the numbers a governed query returns**. Re-check any dashboards built on
`exposes[].semantics`.

- **Double aggregation fixed.** Forge-emitted measures copied whole aggregate expressions
  (`SUM(amount)`) into `measures[].expr` next to an inferred `agg`, so both consumers aggregated
  twice — the MCP query compiler rendered `SUM(SUM(amount))` (invalid SQL on every engine) and the
  dbt MetricFlow bridge exported the same double wrap. A shared builder now splits single-aggregate
  expressions into `agg` + inner expr (`COUNT(*)` → count over 1; `COUNT(DISTINCT x)` →
  `count_distinct`, previously misfiled as plain `count`).
- **`metrics[].filter` is honored on the governed query path.** It was silently ignored by the MCP
  query compiler, so `completed_revenue = sum(amount)` filtered to `status = 'completed'` returned
  **unfiltered** numbers via the query tool while the dbt export honored the same filter — two
  consumers, two answers, one contract. The predicate is now allowlist-validated and applied
  parenthesized to the `WHERE`; a filter that fails the allowlist raises `QueryValidationError`
  without echoing the raw text. **Fail closed, never wrong.**
- **`agg: percentile` now carries a percentile.** The `0.7.6` preview schema gains
  `measures[].aggParams` (`percentile`, `useDiscretePercentile`), mirroring
  dbt-semantic-interfaces `agg_params`. The MCP compiler renders
  `PERCENTILE_CONT(p) / PERCENTILE_DISC(p) WITHIN GROUP (ORDER BY expr)` and fails closed on
  BigQuery / Athena (no grouped ordered-set percentile there); the dbt bridge maps `aggParams`
  through. Both share a pinned default of `0.5`. GA `0.7.5` is untouched.
- **Time grains have one source of truth.** The vocabulary lived in three hand-maintained copies
  that had measurably drifted (whether `hr` / `mins` were accepted depended on which module saw the
  value first). The interview path now normalizes free-form input (`daily` → `day`) instead of
  emitting enum-invalid contracts, and omits unrecognized grains rather than passing them through.
- **`defaultAggTimeDimension` is populated** by both producers — the field was write-never while the
  dbt bridge read it and silently fell back.
- **Governance round-trips through dbt.** `metrics[].owner` emits as the metric's
  `config.meta.owner`; semantics `tags` / `labels` emit as the semantic model's
  `config.meta.fluid_tags` / `fluid_labels` (namespaced so they never collide with your own dbt meta
  conventions). The manifest importer recovers all three, so the governance surface now survives
  contract → dbt → contract round trips. Verified against a real `dbt parse` (dbt-core 1.11.11 +
  duckdb).
- **`fluid import dbt` now imports the semantic layer.** Manifest `semantic_models` and `metrics`
  (dbt manifest v10+) map into `exposes[].semantics`, closing the round trip: `fluid generate` has
  exported a semantics block to MetricFlow YAML since `0.12.0`, and re-importing that project
  previously lost it. See [`fluid import`](./cli/import.md).
- **Every template product ships a queryable semantics block.** Template-mode contracts previously
  carried no `exposes[].semantics` at all — no MCP query tool (the gateway hides the query
  capability without metrics/measures/dimensions), no MetricFlow export, and a validator warning —
  until a human authored the block by hand. All five templates (`analytics`, `etl_pipeline`,
  `ml_pipeline`, `starter`, `streaming`) now derive a conservative, deterministic block from their
  columns.
- **Apache Ossie (OSI) resync.** The OSI port tracked OSI `v0.1.1` before the project moved to
  Apache Ossie (incubating). The dialect vocabulary gains `BIGQUERY` and `MAQL`, `vendor_name` is
  free-form per the spec, and `ai_context` accepts the spec's plain-string form. The
  `*.semantics.osi.yaml` sidecar is now a **spec-conformant interchange document** with the proper
  `{version, semantic_model: []}` root wrapper (it was previously a bare model dump that strict
  validators rejected, and that nothing could consume). New
  `fluid forge data-model --osi-sidecar-format json` emits the shape **dbt Core (v1.12+) reads
  natively** — drop it in your dbt project's `OSI/` directory to query the semantic model through
  dbt with no conversion step.

### Security

- **HIGH — mission run-id path traversal.** `MissionRunStore.run_dir` joined an unvalidated `run_id`
  onto the missions root, and `--resume` sourced that id from a **workspace-resident**
  `manifest.json` — attacker-controlled content in a cloned repo. `../../../../ESCAPED` resolved
  fully outside the workspace, and a manifest could also declare an identity other than the
  directory it lived in and win the newest-first sort with a chosen `started_at`. The spec trust
  model did not cover this (it pins the *spec* file, not run manifests), and a built-in spec is
  trusted with no prompt — so the exact `--resume` command the CLI prints reached the escaped write
  with no approval. Fixed at the single chokepoint both entry points funnel through: a run id is now
  an opaque **single path segment**, and the directory name is authoritative.
- **Two IAM-widening defects in shared-mode emit** (found and fixed within the packaging lane before
  release). The prefix scoping that shared mode exists to provide **failed open** when the contract
  omitted `location.path`, so a tenant's grant landed **bucket-wide on a platform-owned pool**: the
  `s3:ListBucket` narrowing applied only when a path was present, and `s3:GetObject` fell back to
  the whole bucket. Separately, an authoritative `aws_s3_bucket_policy` would have **replaced the
  pool's own policy**. Both now fail closed. On GCP, a shared bucket's IAM member conditions escape
  contract content so a crafted `path` cannot close the CEL string literal and widen the grant, and
  a shared BigQuery dataset drops its authoritative `access[]` block (it would rewrite the pool's
  whole ACL and evict other tenants) in favour of per-table
  `google_bigquery_table_iam_member`.
- **`fluid import dbt` hardened against Jinja** in recovered free-text fields.

### Fixed & internal

- **Import adoption safety.** Every IaC plugin's `discover_imports` is gated on the packaging
  resolution, so a shared pool can never be `tofu import`ed into a product's state. Leaf resources
  inside a pool stay importable.
- **One canonical shared-bucket name derivation.** A `{{ env.* }}` bucket previously declared the
  `data.aws_s3_bucket` lookup under one key and referenced it under another — a dangling reference
  that failed `tofu validate`. Both sides now route through one resolver that fails closed
  (`PackagingError` kind `shared-bucket-unresolved`) when a pool bucket cannot be resolved to a
  concrete name.
- **Backend state key.** A packaging-bearing contract defaults to
  `fluid/<safe-id>/terraform.tfstate`; contracts with no packaging block keep today's key exactly.
- **Agent-loop transport fixes.** Three defects made tool use non-functional against every shipped
  provider (a sentinel URL POSTed over HTTP, litellm's proxy MCP bridge pulling in an absent
  `fastapi`, and an Anthropic-vs-OpenAI tool-shape mismatch that produced no error and no tool
  calls). All three are fixed; the loop gains additive `tool_allowlist` and `goal_scope` parameters
  that default to today's exact behaviour.
- **Verification.** A bilateral cross-account Lake Formation + S3 policy live test on LocalStack,
  with a causal control proving the emitted bucket policy is the deciding control; and a
  cross-project BigQuery `dataset.access` live test on the BQ emulator, with the emulator's lack of
  validation/enforcement pinned executably rather than assumed.

## Compatibility

- **No breaking changes to existing contracts.** `0.7.5` remains the stable default for untagged
  contracts. `0.7.6` is bundled as **opt-in preview** — a contract must declare
  `fluidVersion: "0.7.6"` to use the `packaging` block or `measures[].aggParams`. Preview versions
  are never the silent default.
- **IaC emit is byte-identical** for every contract without a `packaging` block. That path is a
  distinct LEGACY sentinel, golden-pinned — not a re-derivation.
- **`metadata.policies` is deprecated.** It still emits, but it has never been schema-valid and
  fails `fluid validate`. Migrate to root-level `accessPolicy`. If you relied on the old
  `"@"`-based principal inference, note that unprefixed values keep the exact legacy behaviour —
  declare `group:` explicitly to get a group entry.
- **Semantic-layer numbers may change.** The double-aggregation, metric-filter, and percentile fixes
  correct results that were previously wrong (invalid SQL, unfiltered totals, or a hardcoded
  median). Re-check anything built on `exposes[].semantics`.
- **`fluid mission run` needs a configured LLM provider.** `fluid mission check` does not — it is
  zero-LLM by design and is the half you want in CI.
- **SDK / custom-scaffold:** unchanged (`data-product-forge-sdk 0.10.0`,
  `data-product-forge-custom-scaffold 0.4.0`).
- **Install:** `pip install --upgrade data-product-forge` → `0.13.0`.
