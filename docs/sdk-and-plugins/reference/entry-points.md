# Entry points reference

`data-product-forge` discovers external functionality through Python entry-points. There are **three CLI-level groups** the CLI walks today, **two role-level groups** wired into specific engines, and **two role-level groups on the SDK roadmap** (the SDK exports the role base classes, but the CLI doesn't yet walk them automatically). Each line in your `pyproject.toml` registers one plugin under one group.

| Group | Wired in 0.8.6? | Walker |
|---|---|---|
| `fluid_build.commands` | ✅ | `cli/bootstrap.py` |
| `fluid_build.extension_validators` | ✅ | `cli/validate.py` |
| `fluid_build.apply_hooks` | ✅ | `cli/apply.py` |
| `fluid_build.custom_scaffolds` | ✅ | `data-product-forge-custom-scaffold` engine |
| `fluid_build.providers` | ✅ | `cli/apply.py` (provider dispatch) |
| `fluid_build.validators` | 🛣️ roadmap | (no live walker; today register `Validator` plugins via `fluid_build.extension_validators` instead) |
| `fluid_build.catalog_adapters` | 🛣️ roadmap | (no live walker; today register `CatalogAdapter` plugins via `fluid_build.commands` + a subcommand) |

The two roadmap groups exist as **declared conventions** so plugin authors can register against them now; a future CLI release will add the auto-walking layer. Until then, register `Validator` shapes under `fluid_build.extension_validators` (the function-signature walker described below).

## The three CLI-level groups

These hook into specific CLI subcommands. Discovered via `importlib.metadata.entry_points()` at CLI startup.

| Group | Hooks into | Plugin shape | Failure mode |
|---|---|---|---|
| `fluid_build.commands` | `cli/bootstrap.py::register_core_commands` (CLI startup) | `register(subparsers) -> None` | Plugin load or `register()` exception → WARN log, CLI continues |
| `fluid_build.extension_validators` | `cli/validate.py::_run_extension_validators` (during `fluid validate`) | `validate(extensions_block: dict, errors: list[str]) -> None` | Plugin exception → folded into `ValidationResult.errors`, validate continues |
| `fluid_build.apply_hooks` | `cli/apply.py::_run_apply_hooks` (during `fluid apply`) | `hook(contract_dir: Path, contract: dict, errors: list[str]) -> None` | Plugin exception → recorded as error, apply aborts unless `--force-pattern-drift` |

## `fluid_build.commands` — add CLI subcommands

For when your plugin needs its own `fluid <name>` top-level command.

### Signature

```python
import argparse

def register(subparsers: argparse._SubParsersAction) -> None:
    """Called at CLI bootstrap. Add your subparser(s) to the subparsers group."""
    p = subparsers.add_parser("my-command", help="What it does")
    p.add_argument("--option", help="...")
    p.set_defaults(func=_run_my_command)


def _run_my_command(args, logger):
    """Your command's body."""
    logger.info("running my-command")
    return 0   # exit code
```

### Registration

```toml
[project.entry-points."fluid_build.commands"]
my-command = "my_pkg.cli:register"
```

The value is `module:callable` — pointing at the `register` function, not at a class.

### Discovery + failure

- Discovered at CLI startup by `register_core_commands()` in `cli/bootstrap.py`.
- If `ep.load()` raises (broken import, missing dependency) → logged at WARNING (prefix: `"Failed to load CLI plugin <name>: ..."`), CLI continues.
- If `register(subparsers)` raises → same WARN-and-continue.
- Plugin exception text is **redacted** with the global secret-scanner before being logged.

### Source

[`fluid_build/cli/bootstrap.py`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/bootstrap.py) — search for `fluid_build.commands` to find the loop.

## `fluid_build.extension_validators` — validate `contract.extensions.*`

For when you've defined a custom sub-key of `contract.extensions` (e.g. `contract.extensions.customScaffold`) and want to validate it as part of `fluid validate`.

This is **different from** the `fluid_build.validators` group (see below) — extension-validators run on a sub-key of `contract.extensions`, validators run on the whole contract.

### Signature

```python
from typing import Any, Dict, List


def validate(extensions: Dict[str, Any], errors: List[str]) -> None:
    """Called during `fluid validate`. `extensions` is contract.extensions.

    Inspect your own sub-key, append error strings to `errors`. Other plugins'
    sub-keys are ignored. The CLI namespaces your errors as
    `extensions.<ep-name>: <message>` automatically.
    """
    my_block = extensions.get("myKey")
    if my_block is None:
        return  # not opted in to this extension — pass through
    # ... your validation logic
    if missing_field:
        errors.append("required field 'foo' missing")
```

### Registration

```toml
[project.entry-points."fluid_build.extension_validators"]
myKey = "my_pkg.validation:validate"
```

The entry-point **name** is the sub-key your validator claims. The error namespace in CLI output is `extensions.<name>: ...`.

### Discovery + failure

- Discovered at the start of `fluid validate` by `_run_extension_validators()` in `cli/validate.py`.
- Short-circuits if `contract.extensions` is absent or empty — your validator is never called.
- If `ep.load()` or `validate()` raises → captured, redacted, recorded as a single error in the ValidationResult (`extensions: validator <name> raised: <message>`). `fluid validate` continues with other validators.
- Plugin-supplied error messages are pre-redacted before reaching `ValidationResult.errors`.

### Example

The `data-product-forge-custom-scaffold` package uses this group to validate the `contract.extensions.customScaffold` block — see [its pyproject.toml](https://github.com/Agenticstiger/data-product-forge-custom-scaffold/blob/main/pyproject.toml#L60).

## `fluid_build.apply_hooks` — runtime invariant checks at `fluid apply`

For checks that fire **during apply**, not during validate. State that depends on the runtime environment (env vars, filesystem, lockfile presence) goes here.

### Signature

```python
from pathlib import Path
from typing import Any, Dict, List


def hook(contract_dir: Path, contract: Dict[str, Any], errors: List[str]) -> None:
    """Called during `fluid apply`, after contract load, before any provider.

    `contract` is a deep copy — mutations here do NOT affect the rest of apply.

    Append messages to `errors` to fail the apply; leave it empty to pass.
    Errors are pre-redacted before logging.
    """
    # ... your logic
    if violation_detected:
        errors.append("my-hook: explain what's wrong and how to fix it")
```

### Registration

```toml
[project.entry-points."fluid_build.apply_hooks"]
my-hook = "my_pkg.hook:hook"
```

The entry-point name surfaces in the error namespace (`apply hook 'my-hook' raised: ...`) and in any tooling that reads `importlib.metadata.entry_points(group='fluid_build.apply_hooks')`.

### Discovery + failure

- Discovered at the start of `fluid apply` by `_run_apply_hooks()` in `cli/apply.py`.
- Each hook receives a fresh `copy.deepcopy(contract)`. A buggy or malicious hook cannot corrupt the contract for the rest of apply or for other hooks.
- If `ep.load()` or your hook function raises → captured as `apply hook '<name>' raised: <exception>` and added to the errors list. Apply continues evaluating other hooks before deciding to abort.
- Plugin exception text is pre-redacted before reaching logs or errors.
- After all hooks run, if any errors were appended:
  - Without `--force-pattern-drift` → `fluid apply` aborts with exit code 1.
  - With `--force-pattern-drift` → errors are downgraded to WARNINGs and apply continues. Audit-friendly: the WARN line appears in stdout/log.

### What hooks know about the target environment

**Known limitation (CLI `0.8.6`):** apply hooks do not receive `args.env` (the `--env` flag) as a parameter, env var, or contract field. The hook signature is exactly `(contract_dir, contract, errors)`. The `contract` is post-overlay (env values baked in), but no semantic "this is the prod env" signal is preserved.

Workarounds today:

- **Runner-set convention env var.** Have your CI runner / deploy script `export DEPLOY_ENV=...` (or your team's chosen name) before invoking `fluid apply`. The hook reads that env var. This is the pattern used in the [apply-hook example](../examples/apply-hook-prod-key-guard.md) and [journey](../journeys/apply-hook.md).
- **Branch on post-overlay contract values.** If your contract carries an env-distinguishing field (e.g. `metadata.deploy_target` set differently per env in the overlay), the hook can read it. Brittle — couples to contract content.
- **Future fix.** Passing `args.env` to apply hooks is a 1-line change in `cli/apply.py::_run_apply_hooks`. File a follow-up on `Agenticstiger/forge-cli` if you'd like this addressed.

### Example

The [apply-hook-prod-key-guard example](../examples/apply-hook-prod-key-guard.md) is a fully-runnable hook. The [apply-hook journey](../journeys/apply-hook.md) is the full walkthrough.

## The four role-level groups (for plugin classes)

These register plugin **classes** so the runtime knows which subclass corresponds to which user-facing name. Two are wired today; two are declared conventions waiting on a future CLI release.

| Group | Plugin class | Discovered by | Wired? |
|---|---|---|---|
| `fluid_build.custom_scaffolds` | `CustomScaffold` subclass | `data-product-forge-custom-scaffold` resolver registry | ✅ |
| `fluid_build.providers` | `InfraProvider` subclass | The provider dispatcher (in `cli/apply.py`) | ✅ |
| `fluid_build.validators` | `Validator` subclass | (planned — register under `fluid_build.extension_validators` today) | 🛣️ |
| `fluid_build.catalog_adapters` | `CatalogAdapter` subclass | (planned — register a `fluid_build.commands` subcommand today) | 🛣️ |

### Registration shape

All four follow the same pattern — the **value** is `module:ClassName` (pointing at the class, not an instance, not a function):

```toml
[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[project.entry-points."fluid_build.validators"]
steward-required = "my_validators.steward:StewardRequired"
```

Multiple registrations per group are fine — both `steward-required` and `cost-center-required` in the same package register independently.

### When to use which

| You want to… | Use |
|---|---|
| Register a `CustomScaffold` plugin discovered via `source.kind: entrypoint` in a contract | `fluid_build.custom_scaffolds` |
| Register a `Validator` plugin that runs on every `fluid validate` | `fluid_build.validators` |
| Register an `InfraProvider` for `fluid apply` to dispatch to | `fluid_build.providers` |
| Register a `CatalogAdapter` for `fluid publish --target ...` | `fluid_build.catalog_adapters` |

## All seven groups, side by side

```toml
# pyproject.toml — example registering across all six groups

# CLI-level extension points (functions)
[project.entry-points."fluid_build.commands"]
my-cmd = "my_pkg.cli:register"

[project.entry-points."fluid_build.extension_validators"]
myKey = "my_pkg.ext_validate:validate"

[project.entry-points."fluid_build.apply_hooks"]
my-hook = "my_pkg.hook:check"

# Role-level plugin registration (classes)
[project.entry-points."fluid_build.custom_scaffolds"]
my-scaffold = "my_pkg.scaffold:MyScaffold"

[project.entry-points."fluid_build.validators"]
my-rule = "my_pkg.validator:MyValidator"

[project.entry-points."fluid_build.providers"]
my-cloud = "my_pkg.provider:MyProvider"

[project.entry-points."fluid_build.catalog_adapters"]
my-catalog = "my_pkg.catalog:MyCatalogAdapter"
```

Each line is independent — register only the groups your plugin needs. A package can register against multiple groups (e.g. a scaffold + its associated validator both ship from the same plugin).

## Inspecting what's registered

A `fluid plugins list` command isn't wired up in the CLI yet (`plugins.py` exists but `bootstrap.py` doesn't register it). Use this one-liner to see what's installed across all seven groups:

```bash
# Confirm the entry-point registered. The CLI's `fluid plugins` command
# isn't wired up yet — `plugins.py` exists but isn't registered in
# bootstrap. Use importlib.metadata directly for now:
python -c "
from importlib.metadata import entry_points
for group in ('fluid_build.commands', 'fluid_build.custom_scaffolds',
              'fluid_build.validators', 'fluid_build.apply_hooks',
              'fluid_build.extension_validators', 'fluid_build.providers',
              'fluid_build.catalog_adapters'):
    eps = list(entry_points(group=group))
    if eps:
        print(f'{group}:')
        for ep in eps:
            print(f'  {ep.name} ({ep.value})')
"
```

```text
custom_scaffolds:
  - hello-scaffold (hello_scaffold.scaffold:HelloScaffold)
  - gitlab-ci      (gitlab_ci_scaffold.scaffold:GitLabCIScaffold)

validators:
  - steward-required (my_validators.steward:StewardRequired)

apply_hooks:
  - prod-key-guard (prod_key_guard.hook:check_prod_deploy_key)

providers:
  (none installed)

extension_validators:
  - customScaffold (data_product_forge_custom_scaffold.validation:validate)

commands:
  - generate-custom-scaffold (data_product_forge_custom_scaffold.cli:register)
```

This is your sanity check after `pip install` — if a plugin doesn't show up here, the entry-point didn't register (most often: forgot `pip install -e .` after editing `pyproject.toml`).

## Trust model

Plugins are uncontained Python loaded into the CLI process. The CLI defends against three failure modes automatically:

- **Crashes** — every load and invocation is wrapped in `try/except`.
- **Contract mutation** (apply hooks only) — each hook receives `copy.deepcopy(contract)`.
- **Credential leak in error messages** — plugin exception text is pre-scrubbed with `redact_secret_text` before reaching logs.

What it does **not** defend against: arbitrary `os.system` calls inside plugin code, infinite loops (no per-plugin timeout), resource exhaustion. Trust = pip trust. Full statement: [Trust model](./trust-model.md).

## Source

- Bootstrap loop: [`fluid_build/cli/bootstrap.py::register_core_commands`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/bootstrap.py)
- Extension validators loop: [`fluid_build/cli/validate.py::_run_extension_validators`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/validate.py)
- Apply hooks loop: [`fluid_build/cli/apply.py::_run_apply_hooks`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/apply.py)
- Tests pinning all three: [`tests/test_cli_plugin_hooks.py`](https://github.com/Agenticstiger/forge-cli/blob/main/tests/test_cli_plugin_hooks.py)
