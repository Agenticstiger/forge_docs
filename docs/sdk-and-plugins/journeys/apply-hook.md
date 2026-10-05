# You want a check at apply time, no problem

The check you want to enforce **can't run at validate time** — it depends on something only true at deploy. Common shapes:

- "The deployer must have a specific secret in their env."
- "The image referenced by the contract must be signed by my-org's release key."
- "The scaffold bundle this contract was generated from must not have drifted since the last `fluid custom-scaffold`."
- "Production deploys must be approved by a human in the last 24 hours."

A `Validator` plugin can't help here — it runs on contract authors, who don't have any of that state. **Apply hooks** are the tool: they run inside `fluid apply`, after the contract is loaded, before any provider executes.

This guide walks through writing one from scratch. By the end you'll have:

- An apply hook that runs every `fluid apply` and refuses to proceed if its invariant is violated.
- A documented escape hatch (`--force-pattern-drift`) for emergencies.
- Tests that exercise both the pass and fail paths.

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

1. **The base signature is `hook(contract_dir: Path, contract: Dict, errors: List[str]) -> None`.** Append to `errors` to fail; leave empty to pass. A hook can opt in to the resolved `--env` by declaring an `env` parameter (see Step 3).
2. **The contract is a deep copy.** You can read or even mutate it inside the hook — the rest of `fluid apply` sees the original. (See [trust model](../reference/trust-model.md) for why.)
3. **Plugin exceptions are trapped.** If your hook raises, the CLI converts it to a structured error and continues — a broken hook can never crash the CLI. But appending to `errors` is the cleaner contract.

## Step 0 — see the result first

For a contract that fails the hook (output from CLI 0.18.1, local-platform contract with an `overlays/prod.yaml`):

```bash
unset FLUID_PROD_DEPLOY_KEY
fluid apply contract.fluid.yaml --env prod --yes
```

```text
apply hook: prod-key-guard: FLUID_PROD_DEPLOY_KEY is not set in the environment.
  This is required for prod deploys. Either:
    • Set the env var (export FLUID_PROD_DEPLOY_KEY=...), OR
    • Pass --force-pattern-drift if you have a specific reason to bypass the check.
apply aborted by an apply-time plugin hook. Pass --force-pattern-drift to override.
```

Exit code `1`. With the env var set:

```bash
export FLUID_PROD_DEPLOY_KEY="$(read-from-secret-manager)"
fluid apply contract.fluid.yaml --env prod --yes
# (proceeds normally)
```

Override flag for emergencies (logged as a warning, so the override shows in the deploy log):

```bash
fluid apply contract.fluid.yaml --env prod --force-pattern-drift --yes
```

```text
apply hook drift ignored (--force-pattern-drift): prod-key-guard: FLUID_PROD_DEPLOY_KEY is not set in the environment.
  This is required for prod deploys. Either:
  ...
```

The apply then proceeds.

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
"""Apply-time guard: refuse prod deploys without FLUID_PROD_DEPLOY_KEY set.

Registered as an apply hook via the ``fluid_build.apply_hooks`` entry-point
group. Invoked by the CLI early in ``fluid apply``, after the contract is
loaded but before any provider executes.

Hook contract (see entry-points reference):
    hook(contract_dir: Path, contract: Dict, errors: List[str],
         env: Optional[str] = None) -> None

Append messages to ``errors`` to fail the apply; leave it empty to pass.
Plugin exceptions are trapped, redacted, and added to errors automatically
— a buggy hook cannot crash the CLI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


REQUIRED_ENV_VAR = "FLUID_PROD_DEPLOY_KEY"
# Fallback for applies that don't pass `--env`: your deploy runner / CI job
# sets DEPLOY_ENV before invoking `fluid apply`. The CLI itself does not set
# it — see the "Apply hooks can receive `--env`" note further down.
DEPLOY_ENV_VAR = "DEPLOY_ENV"


def check_prod_deploy_key(
    contract_dir: Path,
    contract: Dict[str, Any],
    errors: List[str],
    env: Optional[str] = None,
) -> None:
    """Fail prod applies when FLUID_PROD_DEPLOY_KEY isn't set."""
    # `env` is the resolved `--env` value the CLI was invoked with, or None
    # when the flag was omitted. DEPLOY_ENV is the runner-set fallback.
    target = env or os.environ.get(DEPLOY_ENV_VAR, "")
    if target != "prod":
        return  # not a prod apply — nothing to check

    if not os.environ.get(REQUIRED_ENV_VAR):
        errors.append(
            f"prod-key-guard: {REQUIRED_ENV_VAR} is not set in the environment.\n"
            f"  This is required for prod deploys. Either:\n"
            f"    • Set the env var (export {REQUIRED_ENV_VAR}=...), OR\n"
            f"    • Pass --force-pattern-drift if you have a specific reason to bypass the check."
        )
```

Three things worth calling out:

- **`env` is the CLI's own signal; `DEPLOY_ENV` is the fallback.** `fluid apply --env prod` reaches the hook as `env="prod"`. `DEPLOY_ENV` is a convention env var your CI runner exports, and it covers applies invoked without `--env`. Checking `env` first means a CI job that forgets to export `DEPLOY_ENV` still gets the guard. A guard keyed only on a runner-set variable passes silently when the export is forgotten.
- **The error message is specific.** It tells the user what is wrong, what to do, and what the escape hatch is. Copy that shape.
- **Append, don't raise.** Raising works (the CLI catches it and reports `apply hook '<name>' raised: ...`), but appending produces cleaner output.

::: tip How a hook receives `--env`
`fluid apply` calls a legacy hook as `hook(contract_dir, contract, errors)` and forwards the resolved `--env` to hooks that opt in by declaring an `env` parameter, `**kwargs`, a 4th positional slot (under any name), or `*args` (since CLI `0.11.0`). Legacy 3-parameter hooks are called as before. The value is the argparse-validated `--env` string, or `None` when the flag was omitted, so an env-aware hook has to handle `None`.

For a hook that keeps the legacy 3-parameter shape, the other signals are a runner-exported variable such as `DEPLOY_ENV`, or a post-overlay contract value (for example a `labels` entry that differs per overlay). The second couples the hook to contract content.
:::

## Step 4 — test both paths

```python
# tests/test_hook.py
"""Tests for prod-key-guard apply hook."""

import os
from pathlib import Path

import pytest

from prod_key_guard.hook import (
    check_prod_deploy_key,
    DEPLOY_ENV_VAR,
    REQUIRED_ENV_VAR,
)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """Every test starts with a clean env — no DEPLOY_ENV, no deploy key."""
    monkeypatch.delenv(DEPLOY_ENV_VAR, raising=False)
    monkeypatch.delenv(REQUIRED_ENV_VAR, raising=False)


def test_non_prod_target_passes_without_key(monkeypatch):
    monkeypatch.setenv(DEPLOY_ENV_VAR, "dev")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_no_deploy_env_passes(monkeypatch):
    """No `--env`, and no DEPLOY_ENV: the hook can't tell what's being
    deployed — pass through. The convention here is opt-in: pass `--env` or
    set DEPLOY_ENV when you want the guard to run."""
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_prod_target_missing_key_fails(monkeypatch):
    monkeypatch.setenv(DEPLOY_ENV_VAR, "prod")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert len(errors) == 1
    assert REQUIRED_ENV_VAR in errors[0]
    assert "--force-pattern-drift" in errors[0]  # message points to the escape hatch


def test_prod_target_with_key_passes(monkeypatch):
    monkeypatch.setenv(DEPLOY_ENV_VAR, "prod")
    monkeypatch.setenv(REQUIRED_ENV_VAR, "secret-key-value")
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors)
    assert errors == []


def test_env_argument_fires_without_deploy_env():
    """`fluid apply --env prod` reaches the hook directly — no DEPLOY_ENV
    needed, so a CI job that forgets to export it can't silently skip the
    guard."""
    errors: list[str] = []
    check_prod_deploy_key(Path("/tmp"), {}, errors, env="prod")
    assert len(errors) == 1
    assert REQUIRED_ENV_VAR in errors[0]
```

Run it:

```bash
pip install -e ".[dev]"
pytest
```

```text
.....                                                                    [100%]
5 passed in 0.02s
```

## Step 5 — wire it in

```bash
# On the deployer's machine (CI runner, on-call laptop, etc):
pip install data-product-forge prod-key-guard

# The hook is auto-discovered. No contract change needed. Confirm it:
fluid plugins list --json
```

The JSON has an `apply_hook` key; the plugin shows up there:

```json
{
  "allowed": true,
  "dispatched": true,
  "distribution": "prod-key-guard 0.1.0",
  "group": "fluid_build.apply_hooks",
  "name": "prod-key-guard"
}
```

Or use the `importlib.metadata` one-liner:

```bash
python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='fluid_build.apply_hooks'):
    print(f'{ep.name}: {ep.value}')
"
# prod-key-guard: prod_key_guard.hook:check_prod_deploy_key
```

End-to-end (CLI 0.18.1, local-platform contract with an `overlays/prod.yaml`):

```bash
# This fails: no FLUID_PROD_DEPLOY_KEY in the environment.
unset FLUID_PROD_DEPLOY_KEY DEPLOY_ENV
fluid apply contract.fluid.yaml --env prod --yes
# apply hook: prod-key-guard: FLUID_PROD_DEPLOY_KEY is not set in the environment.
#   ...
# apply aborted by an apply-time plugin hook. Pass --force-pattern-drift to override.

# The check passes with the key set:
export FLUID_PROD_DEPLOY_KEY=<key>
fluid apply contract.fluid.yaml --env prod --yes
# (proceeds normally)

# Non-prod targets are untouched:
fluid apply contract.fluid.yaml --env dev --yes
# (proceeds normally)

# Break-glass override (logged as a warning):
unset FLUID_PROD_DEPLOY_KEY
fluid apply contract.fluid.yaml --env prod --force-pattern-drift --yes
# apply hook drift ignored (--force-pattern-drift): prod-key-guard: FLUID_PROD_DEPLOY_KEY is not set in the environment.
```

## Variations — the same shape, different invariants


::: details Check that the contract's owner matches the deployer's team
```python
def check_team_match(contract_dir, contract, errors):
    declared = (contract.get("labels") or {}).get("team")
    deployer = os.environ.get("TEAM_NAME", "")
    if declared and declared != deployer:
        errors.append(
            f"team-match: contract declares team={declared!r} "
            f"but deployer is from team={deployer!r}. "
            f"Cross-team deploys require a written change request."
        )
```

Useful when CI runners are tagged with the team they belong to (`TEAM_NAME` env var injected by the runner config). The contract's `labels` map sits at the contract root.
:::



::: details Refuse deploys outside business hours unless overridden
```python
from datetime import datetime, timezone

def check_business_hours(contract_dir, contract, errors):
    # Reads the runner-set DEPLOY_ENV; add an `env=None` parameter to use --env.
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



::: details Check that the scaffold lock matches the contract's bundle ref
```python
from pathlib import Path

import yaml  # a dependency of data-product-forge


def check_scaffold_lock(contract_dir, contract, errors):
    lockfile = Path(contract_dir) / "fluid-scaffold.lock"
    if not lockfile.exists():
        return
    locked = yaml.safe_load(lockfile.read_text()) or {}
    libraries = ((contract.get("extensions") or {})
                 .get("customScaffold") or {}).get("libraries", [])
    for lib in libraries:
        wanted = (lib.get("source") or {}).get("ref")
        recorded = ((locked.get("libraries") or {})
                    .get(lib.get("id")) or {}).get("ref")
        if wanted and recorded and wanted != recorded:
            errors.append(
                f"scaffold-lock: library {lib.get('id')!r} asks for ref "
                f"{wanted!r}, but the lock was written at {recorded!r}. "
                "Re-run `fluid custom-scaffold --update`."
            )
```

`fluid custom-scaffold` writes `fluid-scaffold.lock` (YAML) with, per library, the `ref` the contract asked for and the resolved `commit`. Pairs with the [your-own-CI bundle pattern](./your-own-ci.md): a product team that bumps `ref` and forgets to regenerate is stopped before deploying.
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

- `fluid plugins list --json` (or the `importlib.metadata` one-liner above) shows `prod-key-guard` under `apply_hook`.
- All the tests pass under `pytest`.
- `fluid apply --env prod` fails with the structured message when `FLUID_PROD_DEPLOY_KEY` is unset, with no `DEPLOY_ENV` exported.
- The same command succeeds when the deploy-key env var is set.
- `fluid apply --env dev` passes regardless of the deploy-key env var (only prod is gated).
- `--force-pattern-drift` downgrades the error to a logged warning and lets the apply proceed.

## When **not** to use an apply hook

- **For contract-shape checks.** "Field X must be a regex match" runs at `fluid validate`, before anyone even thinks about applying. Use a [`Validator`](./custom-validator.md) instead.
- **For checks that the contract author should know about.** Apply hooks fire on the **deployer's** machine. If the contract author won't know about the failure until CI runs, the feedback loop is too slow — push the check earlier with a `Validator`.
- **For long-running checks.** Apply hooks have no per-hook timeout. If your hook can hang for 60 seconds on a flaky network call, apply hangs too. Either short-circuit (`requests.head(..., timeout=5)`) or move the check to a background service.

## Common gotchas

::: details The hook passes on a prod deploy
`env` is `None` when `fluid apply` ran without `--env`, and `DEPLOY_ENV` is only set if your runner exported it. With neither, the hook above cannot tell what is being deployed and passes through. That opt-in behaviour is one valid choice; if you would rather enforce by default, flip the check:

```python
deploy_env = env or os.environ.get("DEPLOY_ENV")
if deploy_env is None:
    errors.append("prod-key-guard: DEPLOY_ENV must be set to dev/staging/prod")
    return
if deploy_env != "prod":
    return
```

The hook reads the `--env` flag through its `env` parameter; see "How a hook receives `--env`" in Step 3.
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
- [Reference → Entry points](../reference/entry-points.md) — signature reference for the plugin groups
- [Reference → Trust model](../reference/trust-model.md) — what the CLI guarantees about hook execution (deep-copied contract, exception trapping, redaction)
- [Apply-hook example](../examples/apply-hook-prod-key-guard.md) — same hook in example form, with more variations
