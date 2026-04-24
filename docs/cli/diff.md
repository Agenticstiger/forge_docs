# `fluid diff`

Stage 5 of the 11-stage pipeline. Detect configuration drift between the desired contract state and deployed resources.

## Syntax

```bash
fluid diff CONTRACT
```

## Key options

| Option | Description |
| --- | --- |
| `--state` | Previous `apply_report.json`. Required for hard-fail drift gating (see below). |
| `--env` | Apply an environment overlay. |
| `--out` | Output file for the drift report (default `runtime/diff.json`). |
| `--exit-on-drift` | Exit with code `1` when drift is detected **and** a `--state` baseline was supplied. |
| `--provider` | Override the provider. If unset and `FLUID_PROVIDER` isn't exported, `diff` auto-detects from `contract.binding.platform` (same as `apply` / `plan` / `verify`). |

## Examples

### Basic drift check

```bash
fluid diff contract.fluid.yaml
fluid diff contract.fluid.yaml --env prod
fluid diff contract.fluid.yaml --out runtime/diff.json
```

### CI-gated drift detection

```bash
# First apply — saves the state we'll diff against next time
fluid apply runtime/plan.json --report runtime/apply-report.json --yes

# Subsequent CI runs — compare against the saved state
fluid diff contract.fluid.yaml \
  --state runtime/apply-report.json \
  --exit-on-drift
# exit 1 on drift, exit 0 if clean
```

## `--exit-on-drift` semantics

The exit-on-drift gate has one important conditional: it only fires when a `--state` baseline was supplied.

| State supplied? | Drift detected? | `--exit-on-drift` behaviour |
| --- | --- | --- |
| No | (every desired resource is "new") | Logged as `diff_exit_on_drift_skipped` with a pointer to `--state`; **exit 0**. |
| Yes | No | Clean; **exit 0**. |
| Yes | Yes | **Exit 1**. |

**Why:** most providers don't implement live inventory yet, so without `--state` the `actual_resources` set is empty and every desired resource appears as `added`. Under a naïve exit-on-drift that would make every first-ever pipeline run fail at stage 5 — which is wrong. The gate is meant to detect **unexpected** changes against a known baseline, not "we don't know the baseline yet".

If you want hard-fail drift gating in CI, wire the last apply's `apply_report.json` as `--state` to enable real drift comparison.

## Provider auto-detection

`fluid diff` reads `contract.binding.platform` to infer the provider when neither `--provider` nor the `FLUID_PROVIDER` env var is set. Explicit flags still win:

1. `--provider <name>` (highest priority)
2. `FLUID_PROVIDER=<name>` env var
3. `contract.binding.platform` (auto-detected fallback)

The auto-detection is logged as `diff_provider_inferred platform=<name> source=contract.binding.platform`.

## Notes

- The report written to `--out` contains three buckets: `added`, `removed`, `unchanged` — plus the full `desired_actions` list for post-hoc analysis.
- `--exit-on-drift` composes cleanly with `fluid diff --state <prior-apply> --exit-on-drift` in Jenkins / GitHub Actions — it gives you a deploy-blocking drift check without a custom parser.
