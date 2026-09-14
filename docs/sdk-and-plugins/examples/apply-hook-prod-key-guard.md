# Example: `prod-key-guard` — apply-time invariant check

An apply hook that refuses to run `fluid apply --env prod` unless the `FLUID_PROD_DEPLOY_KEY` environment variable is set. Demonstrates the **third** extension-point group (`fluid_build.apply_hooks`) — runs during `fluid apply`, after the contract is loaded but before any provider executes.

This example is fully runnable. Copy the three files into a directory, `pip install -e .`, and the hook is registered globally.

## What it does

When someone runs `fluid apply --env prod`, the hook checks for `FLUID_PROD_DEPLOY_KEY` in the environment. Missing → apply aborts with a clear message. Present → apply proceeds normally. Non-prod environments are passed through untouched.

```bash
fluid apply contract.fluid.yaml --env prod
# ✗ apply hook: prod-key-guard:
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
#   This is required for prod deploys. Either:
#     • Set the env var (export FLUID_PROD_DEPLOY_KEY=...), OR
#     • Pass --force-pattern-drift if you have a specific reason to bypass the check.
exit 1
```

With the env var:

```bash
export FLUID_PROD_DEPLOY_KEY="$(read-from-secret-manager)"
fluid apply contract.fluid.yaml --env prod
# (apply proceeds normally)
```

Or with the override flag (for development, drills, or controlled break-glass):

```bash
fluid apply contract.fluid.yaml --env prod --force-pattern-drift
# ⚠ apply hook drift ignored (--force-pattern-drift):
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
# (apply proceeds)
```

## Layout

```text
prod-key-guard/
├── pyproject.toml
├── src/prod_key_guard/
│   ├── __init__.py
│   └── hook.py                ← the apply hook (32 lines)
└── tests/
    └── test_hook.py           ← 4 scenarios, ~50 lines
```

## `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "prod-key-guard"
version = "0.1.0"
description = "Apply-time guard: refuse prod deploys without FLUID_PROD_DEPLOY_KEY set"
requires-python = ">=3.10"
dependencies = []  # stdlib only

[project.optional-dependencies]
dev = ["pytest>=7.0"]

# Third entry-point group: apply hooks. Different from custom_scaffolds
# (which discovers CustomScaffold subclasses) and validators (Validator
# subclasses). An apply hook is just a function.
[project.entry-points."fluid_build.apply_hooks"]
prod-key-guard = "prod_key_guard.hook:check_prod_deploy_key"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## `src/prod_key_guard/hook.py`

```python
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

The hook is **just a function**, not a class. The entry-point contract is `(contract_dir, contract, errors) -> None`, with an optional 4th `env` parameter the CLI fills in when your signature asks for it. Append messages to `errors` to fail the apply; leave it empty to pass.

Three things to know:

- **The `env` parameter is the CLI's own signal; `DEPLOY_ENV` is the fallback.** `fluid apply --env prod` reaches the hook as `env="prod"`. `DEPLOY_ENV` is a convention env var your CI runner / deploy script exports, and it covers applies invoked without `--env`. Order matters here: `env` first means a CI job that forgets to export `DEPLOY_ENV` still gets the guard — see the note below.
- **Append, don't raise.** Raising an exception inside a hook is captured and converted to an error string automatically (the CLI defends against it), but appending to `errors` is the documented contract and produces cleaner output.
- **Be specific in error messages.** Tell the user *what's wrong*, *what to do about it*, and *what the escape hatch is*. The example above does all three; copy that shape.

::: tip Apply hooks can receive `--env`
As of CLI `0.15.0`, `fluid apply` forwards the resolved `--env` value to apply hooks that opt in via their signature (available since `0.11.0`). Declare a keyword-compatible `env` parameter (or `**kwargs`) and you receive it as `env="prod"`; a hook with a 4th positional parameter receives it positionally. Legacy `(contract_dir, contract, errors)` hooks are called exactly as before, so nothing breaks.

The value is `None` when `--env` was omitted, which is why this hook still falls back to `DEPLOY_ENV`: that covers applies invoked without the flag, and keeps the hook working under a pre-`0.11.0` CLI. Most CI systems already export something similar (`CI_ENVIRONMENT_NAME` on GitLab, `GITHUB_REF_NAME` on Actions).

Prefer `env` as the primary signal. A guard keyed only on a runner-set env var fails open: if CI forgets the `export`, the check silently passes on a prod deploy.
:::

## `tests/test_hook.py`

```python
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

No conformance harness inheritance — apply hooks are functions, not classes. Test what your specific hook needs to enforce.

## Run it

```bash
mkdir prod-key-guard && cd prod-key-guard
# create the files above

pip install -e ".[dev]"
pytest
# ============== 5 passed in 0.04s ===============
```

Verify the CLI picks it up. As of CLI `0.10.0`, `fluid plugins` lists installed plugins per role with their allow/block status — or query `importlib.metadata` directly:

```bash
fluid plugins                                 # human table, grouped by role
fluid plugins list --role provider --json     # machine-readable

python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='fluid_build.apply_hooks'):
    print(f'{ep.name}: {ep.value}')
"
# prod-key-guard: prod_key_guard.hook:check_prod_deploy_key
```

If the output is empty, `pip install -e .` didn't re-read your entry-points — re-run it.

End-to-end against a real apply:

```bash
# --env alone is enough: the CLI hands the flag's value to the hook.
unset FLUID_PROD_DEPLOY_KEY DEPLOY_ENV
fluid apply contract.fluid.yaml --env prod
# ✗ apply hook: prod-key-guard:
#   FLUID_PROD_DEPLOY_KEY is not set in the environment.
#   ...

export FLUID_PROD_DEPLOY_KEY="example-secret"
fluid apply contract.fluid.yaml --env prod
# (proceeds normally)

fluid apply contract.fluid.yaml --env dev
# (proceeds normally — non-prod targets are unaffected)

# The DEPLOY_ENV fallback still works for applies invoked without --env.
unset FLUID_PROD_DEPLOY_KEY
DEPLOY_ENV=prod fluid apply contract.fluid.yaml
# ✗ apply hook: prod-key-guard: ...
```

## You'll know it worked when

- `pytest` reports 5 passes against the hook.
- The `importlib.metadata` one-liner above prints `prod-key-guard: prod_key_guard.hook:check_prod_deploy_key`.
- `fluid apply --env prod` fails with the structured message **when** `FLUID_PROD_DEPLOY_KEY` is unset, with no `DEPLOY_ENV` exported.
- The same command succeeds when the deploy-key env var is set.
- `fluid apply --env dev` passes regardless of the deploy-key env var.
- `DEPLOY_ENV=prod fluid apply` (no `--env`) still fails — the fallback path works.
- `--force-pattern-drift` downgrades the error to a WARNING and allows the apply to proceed.

## Common gotchas

::: details The hook doesn't seem to run at all
Same root cause as the quickstart's troubleshooting: pip didn't re-read the entry-point. Run `pip install -e .` again after any edit to `pyproject.toml`, then re-run the `importlib.metadata` one-liner above to confirm the hook is registered.
:::

::: details `DEPLOY_ENV` is unset and my hook quietly passes when I expected it to fail
First check whether you passed `--env` — with it, the hook doesn't need `DEPLOY_ENV` at all. Without either signal it's by design: the example's contract is "opt in by passing `--env` or setting `DEPLOY_ENV`." If you want the hook to be enforcement-by-default (fail unless explicitly overridden), invert the check:

```python
deploy_env = env or os.environ.get(DEPLOY_ENV_VAR)
if deploy_env is None:
    errors.append("prod-key-guard: DEPLOY_ENV must be set to one of: dev, staging, prod")
    return
if deploy_env != "prod":
    return
# … rest of the check
```

Pick the policy your team wants. Opt-in is friendlier for local testing; enforce-by-default is safer for CI runners.
:::

::: details I want the hook to read the --env flag fluid apply was invoked with
You can. Add a keyword-compatible `env` parameter (or `**kwargs`) to your hook and the CLI forwards the resolved `--env` value; a 4th positional parameter works too, and hooks that keep the legacy `(contract_dir, contract, errors)` signature are called unchanged. The hook above already does this — `check_prod_deploy_key(contract_dir, contract, errors, env=None)` branches on `env` and falls back to `DEPLOY_ENV` only when the flag was omitted. For testing in isolation:

```bash
python -c "
from prod_key_guard.hook import check_prod_deploy_key
from pathlib import Path
errs = []
check_prod_deploy_key(Path('/tmp'), {}, errs, env='prod')
print(errs)
"
```
:::

::: details I want the same check at validate time, not apply time
Use a `Validator` plugin instead. See [steward-validator](./steward-validator.md) for the shape. Validators run earlier in the lifecycle — at `fluid validate`, before anyone has tried to deploy.

The trade-off: validators run in CI / pre-commit / IDE on the **contract author's** machine. Apply hooks run only on the **deployer's** machine (or the deploy runner). For "the deployer must have a secret" semantics, apply hook is the right tool — the contract author won't have the secret.
:::

## Variations


::: details Check that a contract field matches an env var
Useful for "this contract claims it's owned by team X — verify that the deployer is from team X via a `TEAM_NAME` env var".

```python
def check_team_match(contract_dir, contract, errors):
    declared = (contract.get("metadata") or {}).get("team")
    deployer = os.environ.get("TEAM_NAME", "")
    if declared and declared != deployer:
        errors.append(
            f"team-match: contract declares team={declared!r} "
            f"but deployer is from team={deployer!r}."
        )
```
:::



::: details Check that the bundle digest hasn't drifted
Most useful when you're publishing a scaffold bundle that several teams consume — if any of them runs `fluid apply` against a stale checkout, fail loudly.

Sketch — full implementation depends on which resolvers you're using:

```python
import hashlib, json

def check_bundle_digest(contract_dir, contract, errors):
    lockfile = contract_dir / "fluid-custom-scaffold.lock.json"
    if not lockfile.exists():
        return
    locked = json.loads(lockfile.read_text())
    libraries = ((contract.get("extensions") or {})
                 .get("customScaffold") or {}).get("libraries", [])
    for lib in libraries:
        lib_id = lib.get("id")
        # Re-resolve via data_product_forge_custom_scaffold.resolvers
        # then hashlib.sha256 over the resolved tree, then compare.
        # ...
```

The full pattern lives in the `data-product-forge-custom-scaffold` repo's tests.
:::



::: details Refuse apply if a required tag isn't on the contract
```python
def check_required_tags(contract_dir, contract, errors):
    required = {"data-classification", "cost-center"}
    labels = ((contract.get("metadata") or {}).get("labels") or {})
    missing = required - set(labels)
    if missing:
        errors.append(f"required-tags: missing labels: {sorted(missing)}")
```

This kind of check could ALSO be a `Validator`. Difference:

- As a **validator**: contract authors see the error in `fluid validate`, before they try to apply. Good for catching the omission early.
- As an **apply hook**: only the deployer sees the error. Useful if the tags are dynamic (e.g. injected by CI) and only meaningful at apply time.
:::


## When **not** to use an apply hook

If the check is **about contract shape** (regex, presence, value), do it at validate time via a `Validator` plugin instead — the contract author gets feedback before they hit `apply`. Apply hooks are for **runtime invariants** that depend on the workspace state (env vars, filesystem, lockfiles), not contract content alone.

## Next

- [Journey → apply-hook](../journeys/apply-hook.md) — full walkthrough of authoring an apply hook from scratch
- [Entry points reference](../reference/entry-points.md) — comparison of all three groups with signatures
- [Trust model](../reference/trust-model.md) — what the CLI guarantees about plugin execution (apply hooks run in-process, contract is deep-copied, exception text is redacted)
