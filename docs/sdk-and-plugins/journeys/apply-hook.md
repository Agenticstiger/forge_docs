# You want a check at apply time, no problem

The check you want to enforce **can't run at validate time** — it depends on something only true at deploy. Common shapes:

- "The deployer must have a specific secret in their env."
- "The image referenced by the contract must be signed by my-org's release key."
- "The scaffold bundle this contract was generated from must not have drifted since the last `fluid generate`."
- "Production deploys must be approved by a human in the last 24 hours."

A `Validator` plugin can't help here — it runs on contract authors, who don't have any of that state. **Apply hooks** are the tool: they run inside `fluid apply`, after the contract is loaded, before any provider executes.

This guide walks through writing one from scratch. By the end you'll have:

- An apply hook that runs every `fluid apply` and refuses to proceed if its invariant is violated.
- A documented escape hatch (`--force-pattern-drift`) for emergencies.
- A test that exercises both the pass and fail paths.

Realistic time end-to-end: **15–20 minutes**.

## The mental model

```text
fluid apply contract.fluid.yaml --env prod
                │
                ▼
   ┌──────────────────────────────────┐
   │ 1. Load contract                  │
   │ 2. Run apply hooks ◄──────── your plugin runs here
   │      ↳ each gets a DEEP COPY      │
   │        of the contract            │
   │      ↳ each can append to errors  │
   │ 3. If any errors:                 │
   │      ↳ --force-pattern-drift?     │
   │          yes → log WARNINGs       │
   │          no  → abort with exit 1  │
   │ 4. Run provider apply()           │
   │ 5. Run policy-apply, verify, …    │
   └──────────────────────────────────┘
```

Three things to know about the hook contract:

1. **Hook signature is fixed.** `hook(contract_dir: Path, contract: Dict, errors: List[str]) -> None`. Append to `errors` to fail; leave empty to pass.
2. **The contract is a deep copy.** You can read or even mutate it inside the hook — the rest of `fluid apply` sees the original. (See [trust model](../reference/trust-model.md) for why.)
3. **Plugin exceptions are trapped.** If your hook raises, the CLI converts it to a structured error and continues — a broken hook can never crash the CLI. But appending to `errors` is the cleaner contract.

## Step 0 — see the result first

For a contract that fails the hook:

```bash
unset FLUID_PROD_DEPLOY_KEY
fluid apply contract.fluid.yaml --env prod
```

```text
✗ apply hook: prod-key-guard:
  FLUID_PROD_DEPLOY_KEY is not set in the environment.
  This is required for prod deploys. Either:
    • Set the env var (export FLUID_PROD_DEPLOY_KEY=...), OR
    • Pass --force-pattern-drift if you have a specific reason to bypass the check.
```

Exit code `1`. With the env var set:

```bash
export FLUID_PROD_DEPLOY_KEY="$(read-from-secret-manager)"
fluid apply contract.fluid.yaml --env prod
# (proceeds normally)
```

Override flag for emergencies (logged at WARN, audit-able):

```bash
fluid apply contract.fluid.yaml --env prod --force-pattern-drift
# ⚠ apply hook drift ignored (--force-pattern-drift):
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
# (proceeds)
```

## Step 1 — set up the package

```bash
mkdir prod-key-guard && cd prod-key-guard
mkdir -p src/prod_key_guard tests
touch src/prod_key_guard/__init__.py tests/__init__.py
```

## Step 2 — write `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "prod-key-guard"
version = "0.1.0"
description = "Refuse prod deploys without FLUID_PROD_DEPLOY_KEY set"
requires-python = ">=3.10"
dependencies = []   # stdlib only — apply hooks are typically dep-free

[project.optional-dependencies]
dev = ["pytest>=7.0"]

# Apply hooks live in this entry-point group. The value is module:function,
# NOT module:Class — apply hooks are functions, not classes.
[project.entry-points."fluid_build.apply_hooks"]
prod-key-guard = "prod_key_guard.hook:check_prod_deploy_key"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## Step 3 — write the hook

```python
# src/prod_key_guard/hook.py
"""Apply-time guard: refuse prod deploys without FLUID_PROD_DEPLOY_KEY set."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_ENV_VAR = "FLUID_PROD_DEPLOY_KEY"


def check_prod_deploy_key(
    contract_dir: Path,
    contract: Dict[str, Any],
    errors: List[str],
) -> None:
    """Fail prod applies when FLUID_PROD_DEPLOY_KEY isn't set."""
    # DEPLOY_ENV is a convention env var the deploy runner sets — not
    # something fluid itself populates. See the "Known limitation"
    # callout below for the full explanation.
    if os.environ.get("DEPLOY_ENV", "") != "prod":
        return  # not a prod apply — nothing to enforce

    if not os.environ.get(REQUIRED_ENV_VAR):
        errors.append(
            f"prod-key-guard: {REQUIRED_ENV_VAR} is not set in the environment.\n"
            f"  This is required for prod deploys. Either:\n"
            f"    • Set the env var (export {REQUIRED_ENV_VAR}=...), OR\n"
            f"    • Pass --force-pattern-drift if you have a specific reason "
            f"to bypass the check."
        )
```

Three things worth calling out:

- **`DEPLOY_ENV` is a convention env var, not something the CLI populates.** Your deploy runner / CI job exports it before invoking `fluid apply`. The CLI doesn't pass `args.env` into hooks today (see "Known limitation" below).
- **The error message is specific.** It tells the user what's wrong, what to do, and what the escape hatch is. Copy that shape — never tell the user "something is wrong" without saying how to fix it.
- **Append, don't raise.** Raising works (the CLI catches it), but appending produces cleaner output.

::: warning Known limitation — apply hooks don't see `--env`
CLI `0.8.6` calls apply hooks as `hook(contract_dir, contract, errors)`. There is no parameter, env var, or attribute that carries the `--env` flag's value into the hook. The `contract` is post-overlay (env-specific values baked in), but the hook has no semantic "this is the prod env" signal.

**Workarounds today:**
- Have your CI runner / deploy script `export DEPLOY_ENV=...` (or your team's convention) before invoking `fluid apply`. The hook reads that env var.
- Inspect post-overlay contract values — e.g. if your contract sets `region` per env, the hook can branch on the resolved region. Brittle (couples to contract content).
- File a follow-up on `Agenticstiger/forge-cli` asking for `args.env` to be passed to hooks. It's a 1-line fix in `cli/apply.py::_run_apply_hooks`.

This guide uses the runner-set env var pattern throughout.
:::

## Step 4 — test both paths

```python
# tests/test_hook.py
"""Apply-hook tests — pass and fail paths."""

from pathlib import Path

import pytest

from prod_key_guard.hook import REQUIRED_ENV_VAR, check_prod_deploy_key


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """Every test starts with a clean env — no DEPLOY_ENV, no deploy key."""
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv(REQUIRED_ENV_VAR, raising=False)


def test_non_prod_target_always_passes(monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "dev")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_no_deploy_env_passes_through(monkeypatch):
    """If DEPLOY_ENV is unset, the hook can't tell what's being deployed —
    pass through. Opt-in semantics; flip the check if you want enforce-by-default."""
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_prod_with_key_passes(monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "prod")
    monkeypatch.setenv(REQUIRED_ENV_VAR, "secret-deploy-key")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_prod_without_key_fails(monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "prod")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert len(errors) == 1
    assert REQUIRED_ENV_VAR in errors[0]
    assert "--force-pattern-drift" in errors[0]  # message points to the escape
```

Run it:

```bash
pip install -e ".[dev]"
pytest
# ============== 4 passed in 0.04s ===============
```

## Step 5 — wire it in

```bash
# On the deployer's machine (CI runner, on-call laptop, etc):
pip install data-product-forge prod-key-guard

# Hook auto-discovered — no contract change needed. Verify with the
# importlib.metadata one-liner (the CLI's plugins-list command isn't
# wired up yet):
python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='fluid_build.apply_hooks'):
    print(f'{ep.name}: {ep.value}')
"
# prod-key-guard: prod_key_guard.hook:check_prod_deploy_key
```

End-to-end:

```bash
# Convention: your deploy runner sets DEPLOY_ENV. For local testing,
# set it on the same line as the apply.

# This should fail — no FLUID_PROD_DEPLOY_KEY in env.
unset FLUID_PROD_DEPLOY_KEY
DEPLOY_ENV=prod fluid apply contract.fluid.yaml --env prod
# ✗ apply hook: prod-key-guard:
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
#   ...

# Pass the check with the key set:
export FLUID_PROD_DEPLOY_KEY=...
DEPLOY_ENV=prod fluid apply contract.fluid.yaml --env prod
# (proceeds normally)

# Break-glass override (audited via WARN log):
DEPLOY_ENV=prod fluid apply contract.fluid.yaml --env prod --force-pattern-drift
# ⚠ apply hook drift ignored (--force-pattern-drift):
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
```

## Variations — the same shape, different invariants


::: details Check that the contract's owner matches the deployer's team
```python
def check_team_match(contract_dir, contract, errors):
    declared = (contract.get("metadata") or {}).get("team")
    deployer = os.environ.get("TEAM_NAME", "")
    if declared and declared != deployer:
        errors.append(
            f"team-match: contract declares team={declared!r} "
            f"but deployer is from team={deployer!r}. "
            f"Cross-team deploys require a written change request."
        )
```

Useful when CI runners are tagged with the team they belong to (`TEAM_NAME` env var injected by the runner config).
:::



::: details Refuse deploys outside business hours unless overridden
```python
from datetime import datetime, timezone

def check_business_hours(contract_dir, contract, errors):
    # Same DEPLOY_ENV convention as the headline example.
    if os.environ.get("DEPLOY_ENV", "") != "prod":
        return
    now = datetime.now(timezone.utc)
    # Mon–Fri, 8am–5pm UTC
    if now.weekday() >= 5 or not (8 <= now.hour < 17):
        errors.append(
            "business-hours: prod deploys are restricted to weekdays 8-17 UTC. "
            "Pass --force-pattern-drift if this is a genuine incident response."
        )
```

`--force-pattern-drift` is the audit-friendly escape: it's logged at WARN, so the override is visible in the deploy log.
:::



::: details Check the bundle digest hasn't drifted
```python
import json, hashlib

def check_bundle_digest(contract_dir, contract, errors):
    lockfile = contract_dir / "fluid-custom-scaffold.lock.json"
    if not lockfile.exists():
        return
    locked = json.loads(lockfile.read_text())
    libs = ((contract.get("extensions") or {})
            .get("customScaffold") or {}).get("libraries", [])
    for lib in libs:
        lib_id = lib.get("id")
        locked_sha = (locked.get("libraries") or {}).get(lib_id, {}).get("digest")
        # Re-resolve via data_product_forge_custom_scaffold.resolvers,
        # then hashlib.sha256 over the resolved tree, then compare.
        # ... (full version in the custom-scaffold repo)
```

Pairs naturally with the [your-own-CI bundle pattern](./your-own-ci.md) — every product team can opt into bundle-digest-drift detection by `pip install`-ing this hook.
:::



::: details Refuse deploys against a contract owned by a deleted account
```python
import requests

def check_owner_active(contract_dir, contract, errors):
    owner = ((contract.get("metadata") or {}).get("owner") or {}).get("email")
    if not owner:
        return
    # Cheap HEAD against your internal directory service
    r = requests.head(f"https://directory.my-org.example.com/users/{owner}",
                      timeout=5)
    if r.status_code == 404:
        errors.append(
            f"owner-active: contract owner {owner!r} is not active in the "
            f"directory. Update metadata.owner before deploying."
        )
```

If the network call is too slow for a hot apply path, cache the lookup or only run it on prod. Apply hooks don't have a per-hook timeout — if the network hangs, the whole apply hangs.
:::


## You'll know it worked when

- The `importlib.metadata` one-liner above (Step 5) shows `prod-key-guard` under `apply_hooks`.
- All 4 tests pass under `pytest`.
- `DEPLOY_ENV=prod fluid apply --env prod` fails with the structured message when `FLUID_PROD_DEPLOY_KEY` is unset.
- The same command succeeds when the deploy-key env var is set.
- `DEPLOY_ENV=dev fluid apply --env dev` passes regardless of the deploy-key env var (only prod is gated).
- `--force-pattern-drift` downgrades the error to a WARN and lets the apply proceed (and the WARN line appears in stdout for audit purposes).

## When **not** to use an apply hook

- **For contract-shape checks.** "Field X must be a regex match" runs at `fluid validate`, before anyone even thinks about applying. Use a [`Validator`](./custom-validator.md) instead.
- **For checks that the contract author should know about.** Apply hooks fire on the **deployer's** machine. If the contract author won't know about the failure until CI runs, the feedback loop is too slow — push the check earlier with a `Validator`.
- **For long-running checks.** Apply hooks have no per-hook timeout. If your hook can hang for 60 seconds on a flaky network call, apply hangs too. Either short-circuit (`requests.head(..., timeout=5)`) or move the check to a background service.

## Common gotchas

::: details `DEPLOY_ENV` is empty in the hook
If your deploy runner didn't `export DEPLOY_ENV=...` before calling `fluid apply`, your hook can't tell what's being deployed. The example's opt-in pattern (pass through when unset) is one valid choice; if you'd rather enforce-by-default, flip the check:

```python
deploy_env = os.environ.get("DEPLOY_ENV")
if deploy_env is None:
    errors.append("prod-key-guard: DEPLOY_ENV must be set to dev/staging/prod")
    return
if deploy_env != "prod":
    return
```

If you want the hook to read the `--env` flag fluid was invoked with — you can't, as of `0.8.6`. See the "Known limitation" callout earlier on this page.
:::

::: details I want a different override flag, not `--force-pattern-drift`
You can't add new CLI flags from a plugin (that would be a CLI-commands extension, not an apply hook). The single override flag the CLI exposes is `--force-pattern-drift`, and it downgrades **all** hook errors to WARNs. If you need per-hook override semantics, encode it in the hook itself:

```python
if errors and os.environ.get("MY_HOOK_OVERRIDE"):
    return  # hook self-overrides via env var
```

This is the cleanest way to give one hook its own escape without touching the CLI.
:::

::: details My hook works in tests but doesn't fire in `fluid apply`
Same pattern as everywhere else: `pip install -e .` after editing `pyproject.toml`. Entry-points are read at install time. Then re-run the `importlib.metadata` one-liner from Step 5 to confirm.
:::

::: details The hook's error message is unreadable in CI output
The CLI prints apply-hook errors verbatim, so newlines and indentation are preserved. Multi-line messages (like the example above) render well in interactive terminals but can look weird in CI log aggregators that flatten newlines. If your messages must work in flat-log mode, use `\n  • ` separators sparingly and put the most important info first.
:::

## Next

- [Custom validator](./custom-validator.md) — for checks that can run at `fluid validate` instead
- [Your own CI](./your-own-ci.md) — bundle pattern for scaffolds, often paired with apply hooks for drift detection
- [Reference → Entry points](../reference/entry-points.md) — full signature reference for all three plugin groups
- [Reference → Trust model](../reference/trust-model.md) — what the CLI guarantees about hook execution (deep-copied contract, exception trapping, redaction)
- [Apply-hook example](../examples/apply-hook-prod-key-guard.md) — same hook in example form, with more variations
