# Entry points reference

`data-product-forge` discovers external functionality through Python entry-points. As of CLI **0.10.0** the role-level groups are wired end-to-end: the `Validator` role runs inside `fluid validate`, the `CatalogAdapter` role runs inside `fluid publish`, and IaC providers are pluggable via the new `fluid_build.iac_providers` group. Each line in your `pyproject.toml` registers one plugin under one group.

| Group | Wired in? | Walker |
|---|---|---|
| `fluid_build.commands` | ✅ | `cli/bootstrap.py` |
| `fluid_build.extension_validators` | ✅ | `cli/validate.py` |
| `fluid_build.extension_schemas` | ✅ (new in 0.8.9) | `fluid_build/extension_schemas.py` (forge copilot) |
| `fluid_build.apply_hooks` | ✅ | `cli/apply.py` |
| `fluid_build.custom_scaffolds` | ✅ | `data-product-forge-custom-scaffold` engine |
| `fluid_build.providers` | ✅ | `cli/apply.py` (provider dispatch) |
| `fluid_build.validators` | ✅ (wired in 0.10.0) | `cli/validate.py` |
| `fluid_build.catalog_adapters` | ✅ (wired in 0.10.0) | `cli/publish.py` |
| `fluid_build.iac_providers` | ✅ (new in 0.10.0) | IaC emitter (entry-point pluggable) |

All role-level groups now have a live walker. `Validator` plugins are discovered by `fluid validate`, `CatalogAdapter` plugins by `fluid publish`, and entry-point-pluggable IaC providers by the IaC emitter via `fluid_build.iac_providers`.

## The four CLI-level groups

These hook into specific CLI subcommands. Discovered via `importlib.metadata.entry_points()` at CLI startup.

| Group | Hooks into | Plugin shape | Failure mode |
|---|---|---|---|
| `fluid_build.commands` | `cli/bootstrap.py::register_core_commands` (CLI startup) | `register(subparsers) -> None` | Plugin load or `register()` exception → WARN log, CLI continues |
| `fluid_build.extension_validators` | `cli/validate.py::_run_extension_validators` (during `fluid validate`) | `validate(extensions_block: dict, errors: list[str]) -> None` | Plugin exception → folded into `ValidationResult.errors`, validate continues |
| `fluid_build.extension_schemas` | `fluid_build/extension_schemas.py::iter_extension_schemas` (during `fluid forge` generate + pre-emit validate) | `get_extension_schema(fluid_version: str \| None = None) -> dict` | Plugin exception → skipped (logged by type, redacted); discovery fails open to `{}` |
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

## `fluid_build.extension_schemas` — make `contract.extensions.*` AI-native

The companion to `extension_validators` (new in CLI **0.8.9**). Where the validator *checks* a `contract.extensions.<key>` block, the schema provider *describes* it: it returns the JSON-Schema for the block so the **`fluid forge` copilot** can **generate** a valid block and **pre-validate** it before writing the contract.

Without this, the core contract schema treats `extensions` as `additionalProperties: true` — the copilot has no idea what shape your sub-key takes, so AI-authored contracts never include it. Register a schema provider and your extension is handled like a first-class contract field, with **zero per-extension CLI changes** — the entry-point group *is* the entire contract.

### Signature

```python
from typing import Any, Optional


def get_extension_schema(fluid_version: Optional[str] = None) -> dict[str, Any]:
    """Return the draft-07 JSON-Schema for your contract.extensions.<key> block.

    `fluid_version` is the target contract version (e.g. "0.7.4") so a provider
    can return a version-specific schema; ignore it if your schema is stable.
    The dict describes the data *under* the extension key.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["..."],
        "properties": {"...": {"type": "string"}},
    }
```

A zero-argument provider (`get_extension_schema()`) is also accepted.

### Registration

```toml
[project.entry-points."fluid_build.extension_schemas"]
myKey = "my_pkg.validation:get_extension_schema"
```

The entry-point **name** is the `contract.extensions` sub-key the schema describes — match the name you registered under `fluid_build.extension_validators` so the same block is both generated and validated.

### Discovery + failure

- Enumerated by `iter_extension_schemas()` in `fluid_build/extension_schemas.py`. The `fluid forge` copilot injects every discovered schema into the modeler prompt (so the LLM can propose a valid block under `source_summary.proposed_extensions`), keeps only proposals that validate against the schema, and runs the matching `extension_validators` on the emitted block **before** the contract is written — so a malformed block is repaired, not shipped.
- Per-plugin isolation: a provider that fails to load, raises, or returns a non-`dict` is skipped — logged by exception **type** only (so a secret-bearing message can't leak) — and never drops the other providers. Discovery fails open to `{}`.
- A no-op when no provider is installed: the copilot prompt is byte-identical to before, so contracts that don't use extensions are unaffected.

### Example

`data-product-forge-custom-scaffold` advertises the schema for `contract.extensions.customScaffold` from the same module that validates it — see [its `validation.py`](https://github.com/Agenticstiger/data-product-forge-custom-scaffold/blob/main/src/data_product_forge_custom_scaffold/validation.py). The SDK ships a reference `iter_extension_schemas()` helper (`from fluid_sdk import iter_extension_schemas`) for plugin authors and conformance tests.

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

**Known limitation (CLI `0.10.0`):** apply hooks do not receive `args.env` (the `--env` flag) as a parameter, env var, or contract field. The hook signature is exactly `(contract_dir, contract, errors)`. The `contract` is post-overlay (env values baked in), but no semantic "this is the prod env" signal is preserved.

Workarounds today:

- **Runner-set convention env var.** Have your CI runner / deploy script `export DEPLOY_ENV=...` (or your team's chosen name) before invoking `fluid apply`. The hook reads that env var. This is the pattern used in the [apply-hook example](../examples/apply-hook-prod-key-guard.md) and [journey](../journeys/apply-hook.md).
- **Branch on post-overlay contract values.** If your contract carries an env-distinguishing field (e.g. `metadata.deploy_target` set differently per env in the overlay), the hook can read it. Brittle — couples to contract content.
- **Future fix.** Passing `args.env` to apply hooks is a 1-line change in `cli/apply.py::_run_apply_hooks`. File a follow-up on `Agenticstiger/forge-cli` if you'd like this addressed.

### Example

The [apply-hook-prod-key-guard example](../examples/apply-hook-prod-key-guard.md) is a fully-runnable hook. The [apply-hook journey](../journeys/apply-hook.md) is the full walkthrough.

## The four role-level groups (for plugin classes)

These register plugin **classes** so the runtime knows which subclass corresponds to which user-facing name. As of CLI 0.10.0 all four are wired to a live walker.

| Group | Plugin class | Discovered by | Wired? |
|---|---|---|---|
| `fluid_build.custom_scaffolds` | `CustomScaffold` subclass | `data-product-forge-custom-scaffold` resolver registry | ✅ |
| `fluid_build.providers` | `InfraProvider` subclass | The provider dispatcher (in `cli/apply.py`) | ✅ |
| `fluid_build.validators` | `Validator` subclass | `fluid validate` (wired in 0.10.0) | ✅ |
| `fluid_build.catalog_adapters` | `CatalogAdapter` subclass | `fluid publish` (wired in 0.10.0) | ✅ |
| `fluid_build.iac_providers` | IaC provider | The IaC emitter (new in 0.10.0) | ✅ |

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

## All eight groups, side by side

```toml
# pyproject.toml — example registering across all eight groups

# CLI-level extension points (functions)
[project.entry-points."fluid_build.commands"]
my-cmd = "my_pkg.cli:register"

[project.entry-points."fluid_build.extension_validators"]
myKey = "my_pkg.ext_validate:validate"

[project.entry-points."fluid_build.extension_schemas"]
myKey = "my_pkg.ext_validate:get_extension_schema"

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

As of CLI **0.10.0**, [`fluid plugins`](/forge_docs/cli/plugins.html) lists installed plugins per role with their allow/block status — it's the primary way to confirm a plugin registered:

```bash
fluid plugins                  # human table, grouped by role
fluid plugins list --role provider
fluid plugins list --detailed  # loads ALLOWED plugins to show declared metadata
fluid plugins list --json      # machine-readable, every group keyed
```

```text
🔌 Installed FLUID plugins (by role):

  provider  (4)
    • aws                          allowed
    • gcp                          allowed
    • local                        allowed
    • snowflake                    allowed
```

The `--json` form emits an object keyed by every group (`apply_hook`, `catalog`, `command`, `custom_scaffold`, `extension_schema`, `extension_validator`, `iac_provider`, `modeling_technique`, `provider`, `source_adapter`, `validator`), each value a list of `{name, group, allowed}`.

If you'd rather not shell out, the `importlib.metadata` one-liner is an equivalent fallback:

```bash
python -c "
from importlib.metadata import entry_points
for group in ('fluid_build.commands', 'fluid_build.custom_scaffolds',
              'fluid_build.validators', 'fluid_build.apply_hooks',
              'fluid_build.extension_validators', 'fluid_build.extension_schemas',
              'fluid_build.providers', 'fluid_build.catalog_adapters',
              'fluid_build.iac_providers'):
    eps = list(entry_points(group=group))
    if eps:
        print(f'{group}:')
        for ep in eps:
            print(f'  {ep.name} ({ep.value})')
"
```

Either is your sanity check after `pip install` — if a plugin doesn't show up, the entry-point didn't register (most often: forgot `pip install -e .` after editing `pyproject.toml`).

## Plugin governance

CLI **0.10.0** gates **every code-executing entry-point group BEFORE load** with two operator env vars:

- **`FLUID_PLUGINS_ALLOWLIST`** — comma-separated entry-point names; if set, only these load.
- **`FLUID_PLUGINS_BLOCKLIST`** — comma-separated entry-point names; these never load.

A blocked plugin's code never executes. Governed groups: `providers`, `validators`, `catalog_adapters`, `commands`, `apply_hooks`, `extension_schemas`, `extension_validators`, `modeling_techniques`, `source_adapters`, `iac_providers`. `fluid plugins` surfaces each plugin's allow/block status.

An opt-in compat gate, **`FLUID_PLUGIN_STRICT_COMPAT=1`**, additionally refuses to load any plugin whose declared `requires_cli` (a PEP 440 specifier from the SDK's `PluginMetadata`) the running CLI version does not satisfy. Default (unset) is warn-only. See the [trust model](./trust-model.md#operator-governance-allowlist-and-blocklist) for the full operator story.

## Trust model

Plugins are uncontained Python loaded into the CLI process. The CLI defends against three failure modes automatically:

- **Crashes** — every load and invocation is wrapped in `try/except`.
- **Contract mutation** (apply hooks only) — each hook receives `copy.deepcopy(contract)`.
- **Credential leak in error messages** — plugin exception text is pre-scrubbed with `redact_secret_text` before reaching logs.

What it does **not** defend against: arbitrary `os.system` calls inside plugin code, infinite loops (no per-plugin timeout), resource exhaustion. Trust = pip trust. Full statement: [Trust model](./trust-model.md).

## Source

- Bootstrap loop: [`fluid_build/cli/bootstrap.py::register_core_commands`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/bootstrap.py)
- Extension validators loop: [`fluid_build/cli/validate.py::_run_extension_validators`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/validate.py)
- Extension schema discovery: [`fluid_build/extension_schemas.py::iter_extension_schemas`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/extension_schemas.py)
- Apply hooks loop: [`fluid_build/cli/apply.py::_run_apply_hooks`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/apply.py)
- Tests pinning all three: [`tests/test_cli_plugin_hooks.py`](https://github.com/Agenticstiger/forge-cli/blob/main/tests/test_cli_plugin_hooks.py)
