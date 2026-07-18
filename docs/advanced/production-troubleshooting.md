# Production Troubleshooting

Symptom → diagnosis → fix runbook for fluid pipelines in production. Everything on this page is verified against CLI `v0.11.0`.

::: tip First responder
Start every incident with `fluid doctor`. It checks infrastructure, feature availability, copilot readiness, and the active state-store backend in one pass — and `--env` dumps every recognised `FLUID_*` kill switch with its current value.
:::

## First responder: `fluid doctor`

| Invocation | What you get |
|---|---|
| `fluid doctor` | Base infrastructure + feature checks |
| `fluid doctor --env` | Every recognised `FLUID_*` runtime kill switch: current value, default, one-line description |
| `fluid doctor --json` | Machine-readable output for tickets and dashboards |
| `fluid doctor --extended` | Comprehensive checks (slower) |
| `fluid doctor --scope <area>` | Acquisition-stack scoped checks |
| `fluid doctor --out-dir runtime/diag` | Where the diagnostic bundle is written (default `runtime/diag`) |

Attach the `--json` output and the diagnostic bundle to any escalation.

## Plan-binding rejections

**Symptom:** `fluid apply` refuses to run with a `PlanBindingError` before any DDL executes.

Each error carries a stable `kind` tag — a distinct, greppable CI event:

| `kind` | Diagnosis | Fix |
|---|---|---|
| `bundle-mismatch` | The plan's `bundleDigest` disagrees with the bundle on disk — the bundle was swapped after `plan` ran, or the contract was re-bundled without re-planning | Re-run `fluid bundle` **then** `fluid plan`, and apply the fresh pair |
| `plan-tamper` | The plan's `planDigest` disagrees with the recomputed digest — `plan.json` was edited between stages 6 and 7 (a missing/empty `planDigest` is treated the same) | Never hand-edit `plan.json`; regenerate with `fluid plan` |
| `bundle-missing` | The plan carries a `bundleDigest` but no bundle was supplied or auto-discovered — the gate fails closed rather than silently skipping | Pass `--bundle <path-to-tgz>` or restore the sibling `.tgz` |
| `bundle-manifest-missing` / `bundle-manifest-invalid` | The tgz has no `MANIFEST.json`, or its per-file SHAs / merkle root don't verify (truncated or corrupted archive) | Re-run `fluid bundle --format tgz` |
| `bundle-merkle-mismatch` | The merkle root recomputed from the bundle's raw bytes disagrees with the root declared in its `MANIFEST.json` | Same — rebuild the bundle; treat as possible tampering |
| `binding-mode-missing` / `binding-mode-invalid` / `binding-mode-mismatch` | The plan's `bindingMode` field is absent, unrecognised, or contradicts the presence of `bundleDigest` (e.g. `bundleDigest` stripped to dodge the bundle check) | Regenerate via `fluid plan` — the plan came from an older CLI or was edited |

::: warning `--no-verify-plan-binding` is a DR hatch, not a fix
When the bundle is genuinely unrecoverable (disaster recovery from partial artifacts), `fluid apply --no-verify-plan-binding` skips the verification — and logs at WARNING so the audit trail records it. If you reach for it during routine operations, the actual fix is regenerating the bundle+plan pair. The federation upstream-digest gate has its own separate hatch, `--no-verify-federation`.
:::

## Apply data-loss gate

**Symptom:** apply aborts telling you to re-run with `--allow-data-loss`.

| Situation | Diagnosis | Fix |
|---|---|---|
| `--mode replace` / `replace-and-build` outside `dev`, or the target has rows | The destructive-modes gate: replace modes require an explicit `--allow-data-loss` acknowledgement | Confirm the target really should be rebuilt, then re-run with `--allow-data-loss`. A pre-replace snapshot is taken, so [`fluid rollback`](../cli/rollback.md) can restore it |
| OpenTofu apply blocked with an `opentofu_data_loss_gate` event | The IaC plan wants to destroy resources that hold data | Same override. The bypass emits an audit-trail WARNING plus a structured `opentofu_destructive_gate_override` event — search your logs for that tag when auditing who overrode the gate |
| Apply refuses due to a plan/apply mode mismatch | The plan was generated for a different `--mode` than apply was invoked with | Re-run `fluid plan --mode <mode>` matching the intended apply mode |

## Build and run failures

**Symptom:** an acquisition build failed, or produced unexpected output.

Work the run-record surface under the state root (`./.fluid` by default; override with `--state-root`):

```bash
fluid runs status <product_id> --last 5             # recent runs of a product
fluid runs status <product_id> --build <build_id>   # pin a specific build
fluid runs logs <product_id> --component build      # component: build|infra|server|worker|dlq
fluid runs logs <product_id> --run-id <id> --grep ERROR --limit 200
fluid runs diff <product_id> --build <b> --run-a <baseline> --run-b <comparison>
```

`runs diff` reports the schema + row-count delta between two runs — the fastest way to confirm whether a failure changed the data shape or just the run status. All three verbs accept `--json`.

## Cursor rewind and replay-pending markers

**Symptom:** a file appears at `.fluid/<product_id>/runtime/replay-pending.json`.

An upstream source-aligned product's cursor moved **backward** (a reprocess), and the runners marked every downstream product that `consumes[]` it as dirty — "loud drift" instead of a silently stale downstream. The marker records what happened:

```json
{
  "upstream_product_id": "bronze.crm.customers",
  "upstream_build_id": "main_build",
  "old_cursor_value": "2026-04-30T00:00:00Z",
  "new_cursor_value": "2026-04-15T00:00:00Z",
  "detected_at": "2026-05-02T12:30:00Z",
  "reason": "upstream cursor rewound 15 days"
}
```

**Fix:** re-run the marked downstream product's build so it re-reads the rewound window, then delete the marker file. Leaving the marker in place is harmless to execution but means your team loses the drift signal for the next rewind.

## Secrets and credentials

| Symptom | Diagnosis | Fix |
|---|---|---|
| `SecretResolutionError` at apply/build time | A `${SECRET:...}` reference couldn't be resolved from the backend | `fluid secrets verify <ref>` to confirm the ref exists; `printf '%s' "$VALUE" \| fluid secrets login <ref>` to (re)store it. Values are read from stdin or an interactive prompt only — never argv |
| A stored secret is stale or leaked | Rotation needed | `printf '%s' "$NEW" \| fluid secrets rotate <ref>` (supports `--expires-at <ISO-8601>`) |
| `CredentialError`: "Encrypted credential store … cannot be decrypted with the current key" | The Fernet key at the recorded key path no longer matches the ciphertext — the key was regenerated, or the store was copied from another host. The store is **deliberately not wiped**: the ciphertext is still recoverable with the original key | Back up first (`cp <store> <store>.bak`), then either restore the original key, or supply it via `FLUID_ENCRYPTION_KEY` / `FLUID_ENCRYPTION_PASSPHRASE`, or — accepting the loss — remove the store and re-enter credentials |

## OpenTofu failures

| Symptom | Diagnosis | Fix |
|---|---|---|
| "tofu X.Y.Z is older than the required minimum 1.6.0" | The runner has an outdated `tofu` (or only `terraform`) on PATH | Upgrade from opentofu.org, or let the CLI provision a pinned, SHA-256-verified build: `fluid apply --ensure-opentofu` |
| `` `tofu apply` exceeded the 1800s wall-clock limit `` (exit code 124) | A large first apply (or a hung provider call) hit the per-subprocess timeout | Raise `FLUID_TOFU_TIMEOUT_SECONDS`; if it recurs on a small change set, investigate provider-side throttling instead of raising the cap further |
| Apply blocked before `tofu apply` with a plan-binding error | Same integrity gate as the native engine — the OpenTofu path re-verifies `plan.json` digests too | See [plan-binding rejections](#plan-binding-rejections) |

## LLM / copilot authentication failures

**Symptom:** an LLM-driven command (e.g. `fluid forge`) fails with a 401 / invalid-key error, typically right after a provider key rotation.

```bash
fluid ai status      # which provider + model + key source is configured
fluid ai test        # quick connectivity test against the configured provider
fluid ai test --provider anthropic --model <model>   # test an override before saving it
fluid ai setup       # re-run setup to store the rotated key
```

Update the key at whichever source `fluid ai status` reports — the provider env var (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, …) or the stored configuration — then confirm with `fluid ai test`. See [LLM providers & backends](./llm-providers.md) for the resolution order.

## Where logs live

| Setting | Effect |
|---|---|
| `FLUID_LOG_FILE=<path>` (or `--log-file`) | Write logs to a file in addition to stderr |
| `FLUID_LOG_FORMAT=json` | Structured JSON logs — the right setting for shipping to a log aggregator |
| `FLUID_LOG_LEVEL=DEBUG` | Verbose logging (credential-bearing values are redacted by the logging filter) |
| `fluid runs logs …` | Per-component run logs from the `./.fluid` state root |
| `fluid doctor --out-dir runtime/diag` | Diagnostic bundle location |

## Retention sweep

Run-state accumulates under the state root; sweep it on a schedule:

```bash
fluid retention sweep                     # sweep ./.fluid with a structured summary
fluid retention sweep --state-root /data/pipelines/.fluid --json
```

If a replay is later requested past the swept horizon it fails with `StaleReplayError` (the manifest is gone) — see [Typed CLI Errors](./typed-cli-errors.md). Balance the sweep cadence against how far back you realistically replay.

## See also

- [Operating in CI](./operating-in-ci.md) — the pipeline these failures occur in
- [Typed CLI Errors](./typed-cli-errors.md) — the 15-class error catalog and exit codes
- [`fluid doctor`](../cli/doctor.md) / [`fluid runs`](../cli/runs.md) / [`fluid retention`](../cli/retention.md) / [`fluid secrets`](../cli/secrets.md) — command references
- [`fluid rollback`](../cli/rollback.md) — restoring a pre-replace snapshot
- [Environment variables](./environment-variables.md) — the canonical `FLUID_*` index
