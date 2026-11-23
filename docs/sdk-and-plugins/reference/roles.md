# Roles reference

Four built-in roles, all subclasses of `BasePlugin`. Pick by what you're producing. Three more roles, added in SDK 0.12.0, are plain classes for plugin groups with no `plan` / `apply`: see [`AlertNotifier`, `MaintenanceAction` and `CommandPlugin`](#alertnotifier-maintenanceaction-and-commandplugin).

| Role | Role tag | What it produces | Default `apply()` does |
|---|---|---|---|
| [`CustomScaffold`](#customscaffold) | `"custom_scaffold"` | Files on disk | Atomically writes each `write_file` action with sha256 verification + path-traversal guards |
| [`Validator`](#validator) | `"validator"` | `Finding` records | Summarizes findings by severity. `fluid validate` reads the findings from `plan()` and does not call `apply()` |
| [`InfraProvider`](#infraprovider) | `"provider"` | Cloud resources | **Abstract on purpose** — you implement it (provisions per `op` in your action list); a plugin that forgets to fails loud, never a silent no-op |
| [`CatalogAdapter`](#catalogadapter) | `"catalog"` | Catalog entries | **Abstract on purpose** — you implement it (pushes to your catalog of choice); forgetting fails loud, never a silent no-op |

`InfraProvider` (role `"provider"`) and `CatalogAdapter` (role `"catalog"`) became **first-class roles** in SDK 0.10.0, with their `apply` deliberately abstract — the SDK refuses to let a half-implemented provider/catalog silently succeed.

All four inherit the same lifecycle (`plan(contract) → list[PluginAction]` → `apply(actions) → ExecutionResult`), the same conformance harness family (`PluginTestHarness` + a role-specific subharness — every role now has one), and the same crash-containment guarantees from the CLI.

## `BasePlugin`

The ABC every role subclasses. Three methods, one class attribute:

```python
from fluid_sdk import BasePlugin, PluginAction, ExecutionResult, PluginMetadata
from typing import Any, List, Mapping


class MyPlugin(BasePlugin):
    """Required attributes."""

    name: str = "my-plugin"     # ← required; surfaces via `PluginMetadata.name` for any tooling that reads it
    role: str = "..."           # ← set by each Role subclass; don't override

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        """Optional. Override for richer metadata than the default name+role."""
        ...

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        """Required. Inspect the contract; return action dicts.
        Must be deterministic — same contract ⇒ same actions, every time.
        """
        raise NotImplementedError

    def apply(self, actions: List[dict]) -> ExecutionResult:
        """Optional. Default implementation depends on role.
        Override only when you need custom apply semantics.
        """
        ...
```

`plan()` is **the** method you write for every plugin. `apply()` is usually inherited.

## `CustomScaffold`

For file-emitting plugins: CI configs, application code, IaC stacks, docs, anything that lives on disk.

```python
from fluid_sdk import CustomScaffold, ContractHelper, write_file_action


class MyScaffold(CustomScaffold):
    name = "my-scaffold"
    # role = "custom_scaffold" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            write_file_action(
                path="README.md",
                content=f"# {c.name}\n".encode("utf-8"),
                resource_id="readme",
            ).to_dict(),
            write_file_action(
                path=".gitlab-ci.yml",
                content=self._ci_yaml(c).encode("utf-8"),
                resource_id="ci",
            ).to_dict(),
        ]

    def _ci_yaml(self, c):
        return "..."  # your rendering logic
```

### What you get from `CustomScaffold`

- **Inherited `apply(actions)`** — writes files atomically (`temp file + os.replace`) with sha256 verification, path-traversal protection (rejects absolute paths and `..` segments), and idempotency (re-running with the same bytes is a no-op).
- **`write_file_action(...)`** helper — builds a canonical action dict with sha256, base64-encoded bytes, file mode, optional description, optional `depends_on` for ordering. Returning the result of `.to_dict()` from `plan()` is the entire interface.
- **`CustomScaffoldTestHarness`** — conformance tests that run against any `plugin_class` you set, no extra code needed.

### Hooks into the CLI

`fluid custom-scaffold`, the command the `data-product-forge-custom-scaffold` engine registers. The engine looks a `CustomScaffold` plugin up by its entry-point name (a contract's `source: { kind: entrypoint, name: <key> }`). `fluid generate artifacts --emit custom-scaffold` (since forge-cli 0.38.0) runs the engine from the CLI, and `fluid plugins` lists the group as dispatched.

### Examples

- Minimal: [hello-scaffold](../examples/hello-scaffold.md) (~30 LOC)
- Realistic: [gitlab-ci-scaffold](../examples/gitlab-ci-scaffold.md) (~140 LOC)

## `Validator`

For contract-inspection plugins: governance rules, compliance gates, cost guardrails, naming-policy enforcement.

```python
from fluid_sdk import Validator, ContractHelper, Finding


class MyValidator(Validator):
    name = "my-rule"
    # role = "validator" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        findings = []
        if not c.labels.get("cost-center"):
            findings.append(Finding(
                severity="error",
                code="COST_CENTER_MISSING",
                message=f"Contract {c.id!r} missing cost-center label.",
                path='labels["cost-center"]',
                remediation="Add labels['cost-center'] with your team's code.",
            ))
        return [f.to_action() for f in findings]
```

### What you get from `Validator`

- **`Finding` dataclass** — structured `severity` + `code` + `message` + `path` + `remediation`. The `severity` field accepts the [`Severity`](#typed-value-domains) str-enum (`info` / `warn` / `error` / `critical`). In `fluid validate` (0.38.0), `error` and `critical` findings fail the validation, `warn` findings are listed as warnings, and `info` findings go to the debug log only. `fluid validate` prints `code`, `message` and `path`, and does not print `remediation`.
- **Inherited `apply(actions)`** — summarizes findings by severity. `fluid validate` builds its report from `plan()`'s `emit_finding` actions and does not call `apply()`.
- **`ValidatorTestHarness`** (SDK 0.10.0) — subclass it (`class TestMyValidator(ValidatorTestHarness): plugin_class = MyValidator; sample_contracts = [LOCAL_CONTRACT]`) for the generic plugin invariants plus validator-specific conformance. Add your fixture-driven good/bad-contract assertions as additional `test_*` methods, and use `self.get_plugin()` for a fresh instance.
- **Auto-discovery at `fluid validate`** — a validator registered via the `fluid_build.validators` entry point runs on the contracts `fluid validate` checks, with no opt-in in the contract (subject to `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST`).

### Hooks into the CLI

`fluid validate <contract>` runs the installed, allowed validators.

### Examples

- [steward-validator](../examples/steward-validator.md) (~90 LOC)
- Full journey: [custom-validator](../journeys/custom-validator.md)

## `InfraProvider`

For cloud-platform plugins: you're adding support for a new cloud (or warehouse, or query engine) that forge doesn't have a built-in provider for.

```python
from fluid_sdk import ContractHelper, InfraProvider, PluginAction, ExecutionResult


class MyCloudProvider(InfraProvider):
    name = "mycloud"
    # role = "provider" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        # Translate the contract into native cloud ops.
        return [
            PluginAction(
                op="provision_dataset",
                resource_type="dataset",
                resource_id=c.id,
                params={"region": "us-east-1"},
            ).to_dict(),
            # ... more actions
        ]

    def apply(self, actions):
        # You implement this — the base class doesn't know how to talk to your cloud.
        results = []
        for action in actions:
            try:
                self._dispatch(action)
                results.append({"op": action["op"], "status": "ok"})
            except Exception as e:
                results.append({"op": action["op"], "status": "failed", "error": str(e)})
        return ExecutionResult(
            plugin=self.name,
            applied=sum(1 for r in results if r["status"] == "ok"),
            failed=sum(1 for r in results if r["status"] == "failed"),
            duration_sec=0.0,
            timestamp="",
            results=results,
        )
```

### What you get from `InfraProvider`

- **`PluginAction` dataclass** — generic action shape with `op` (the operation), `resource_type`, `resource_id`, `params`, `depends_on`. The `op` field is free-form text — your provider knows what each op means.
- **`provision_action(...)`** helper (SDK 0.10.0) — the provider-side action builder, analogous to `write_file_action` for scaffolds and `Finding.to_action()` for validators.
- **`InfraProviderTestHarness`** (SDK 0.10.0) — generic *and* provider-specific conformance (plan/apply shape, action `op` routing). Subclass it directly; there's no longer any "subclass the base harness for now" workaround.
- **`apply` is abstract on purpose** — the base class does not provide a default. A provider that forgets to implement `apply` fails loud at load/use, never a silent no-op.

### What you implement yourself

Most of it: `apply()` is *your* code talking to *your* cloud's API. The SDK provides the shape; you provide the substance.

### Hooks into the CLI

An `InfraProvider` registered under `fluid_build.providers` joins the provider registry that `fluid providers` lists and `--provider <name>` selects. Observed on CLI 0.38.0: a plugin registered with the entry-point key `my-cloud` is listed by `fluid providers` as `my_cloud`, with the dash turned into an underscore, while `fluid plugins` shows the entry-point key as written.

### Examples

- The CLI's built-in providers (`fluid_build/providers/gcp/`, `/aws/`, `/snowflake/`, `/local/`) are the canonical examples of `InfraProvider` subclasses. They're not on PyPI as separate packages, but the structure is the same — read them at [`Agenticstiger/forge-cli/fluid_build/providers/`](https://github.com/Agenticstiger/forge-cli/tree/main/fluid_build/providers).

## `CatalogAdapter`

For catalog-sync plugins: pushing contract metadata into your enterprise catalog (DataHub, Atlan, Collibra, Alation, OpenMetadata, etc.).

```python
from fluid_sdk import CatalogAdapter, ContractHelper


class MyCatalog(CatalogAdapter):
    name = "my-catalog"
    # role = "catalog" is inherited.

    def plan(self, contract):
        c = ContractHelper(contract)
        # Translate the contract into a catalog-shaped payload.
        return [{
            "op": "upsert_entity",
            "resource_type": "data-product",
            "resource_id": c.id,
            "params": {
                "name": c.name,
                "description": c.description,
                "owner": c.owner.get("email"),
                "domain": c.domain,
                # ...
            },
        }]

    def apply(self, actions):
        # POST/PUT to your catalog's REST API.
        ...
```

### What you get from `CatalogAdapter`

- **`catalog_entry_action(...)`** helper (SDK 0.10.0) — the catalog-side action builder, analogous to `write_file_action` (scaffold) and `provision_action` (provider).
- **`CatalogAdapterTestHarness`** (SDK 0.10.0) — conformance testing for a `CatalogAdapter` plugin, mirroring the other two new role harnesses. Subclass it directly.
- **`apply` is abstract on purpose** — there is no default. A catalog adapter that forgets to implement `apply` fails loud, never a silent no-op.

### Hooks into the CLI

`fluid publish` runs the installed, allowed `CatalogAdapter` plugins in addition to the catalogs named with `--target`: `plan()` and `apply()` per adapter, or `plan()` only with `--dry-run`. The adapter is not selected by `--target`; every installed adapter runs on each publish.

### Examples

- The CLI's Data Mesh Manager and `marketplace` publishers under `fluid_build/providers/` are the closest in-tree analogs. A standalone `CatalogAdapter` plugin on PyPI hasn't been published yet — when one ships, it'll be linked here.

## `AlertNotifier`, `MaintenanceAction` and `CommandPlugin`

*(SDK 0.12.0)* Three more roles describe plugin groups that have no `plan` / `apply` lifecycle. forge-cli reads a few attributes, or calls one method, on whatever an entry point loads. None of the three subclasses `BasePlugin`, and forge-cli does not require the SDK: a package may write the same attributes by hand and register it the same way. The SDK gives each a typed class with forge-cli's own names and signatures, and a conformance harness that applies the rules forge-cli applies when it loads the entry point. forge-cli stays the authority: it has rules a zero-dependency SDK cannot carry and may refuse more.

| Role | Entry-point group | First read by | What it adds |
|---|---|---|---|
| `AlertNotifier` | `fluid_build.alert_notifiers` | forge-cli 0.38.0 | A route kind for the [alerts](../../advanced/airflow.md#alerts) of generated Airflow DAGs |
| `alert_route` helper | `fluid_build.alert_defaults` | forge-cli 0.38.0 | An organisation's default alert routes |
| `MaintenanceAction` | `fluid_build.maintenance_actions` | forge-cli 0.38.0 | A step of an [Iceberg table's maintenance](../../advanced/spark-iceberg-aws.md#iceberg-table-maintenance) that returns SQL |
| `CommandPlugin` | `fluid_build.commands` | forge-cli 0.8.3 | An extra `fluid <name>` subcommand |

The alert groups and the maintenance group follow the operator's plugin policy from their first release: an entry point is read by name, never imported by `fluid --help` or by listing plugins, and `FLUID_PLUGINS_ALLOWLIST` and `FLUID_PLUGINS_BLOCKLIST` apply to the entry-point name before anything is imported. A plugin that fails to load is reported by exception type only. A built-in kind's name cannot be taken, and two packages that ship one name are both refused.

### `AlertNotifier`

A route's `kind` is `email`, `slack`, `webhook`, `pagerduty`, or the name of an entry point in `fluid_build.alert_notifiers`. A kind names an Airflow notifier (a `BaseNotifier` subclass the workers can import) and builds its keyword arguments for one alert; the DAG instantiates it when the event happens, and forge-cli never runs it.

```python
from fluid_sdk import Alert, AlertNotifier, AlertRoute

class ChatNotifier(AlertNotifier):
    notifier = "acme_alerts.notifiers:ChatNotifier"   # what the DAG imports
    requirements = ("acme-chat-alerts>=0.1",)         # what Airflow must install
    requires_connection = False
    default_connection = "acme_chat_default"

    def check(self, route: AlertRoute):
        return []   # problems with the route, each a sentence

    def kwargs(self, route: AlertRoute, alert: Alert):
        return {"message": alert.title, "chat_conn_id": route.connection or self.default_connection}
```

```toml
[project.entry-points."fluid_build.alert_notifiers"]
acme-chat = "acme_alerts.forge:ChatNotifier"
```

`kwargs` returns literals only, keyed by Python identifiers, and never `context`. A route never carries a secret: `connection` names the Airflow connection that holds the URL or key, and `check` must not quote a route value. `alert_route(...)` builds a default route for `fluid_build.alert_defaults` and raises `ValueError` for a shape forge-cli refuses, never quoting a value; `check_alert_route` returns the problems as a list. Test with `AlertNotifierTestHarness`.

### `MaintenanceAction`

An action's `kind` is the name of an entry point in `fluid_build.maintenance_actions`. `check(options)` returns the problems with the options, and `statements(table, options)` returns the SQL, each statement one `DELETE`, `UPDATE` or `MERGE` on the action's own table. forge-cli compiles them into the job config the plan binds, and its Spark runner runs them before compaction.

```python
from fluid_sdk import MaintenanceAction, sql_literal

class ErasePurpose(MaintenanceAction):
    def check(self, options):
        return [] if isinstance(options.get("purpose"), str) else ["options.purpose must be a string"]

    def statements(self, table, options):
        return [f"DELETE FROM {table} WHERE purpose = {sql_literal(options['purpose'])}"]
```

```toml
[project.entry-points."fluid_build.maintenance_actions"]
erase-purpose = "acme_pack.maintenance:ErasePurpose"
```

A statement holds no `${...}`, comment, backslash or control character, and `statements` is deterministic, because the statements are part of the plan. `sql_literal` writes a string as a literal that passes. A contract that names an option whose key looks like a secret is refused, so a kind reads its own secrets. Test with `MaintenanceActionTestHarness`.

### `CommandPlugin`

Set `name` and `help`, override `configure(parser)` and `run(args, logger)`, and name an **instance** in the entry point: forge-cli calls the loaded object with the CLI's subparsers, so the class itself is not callable that way.

```python
from fluid_sdk import CommandPlugin

class HelloCommand(CommandPlugin):
    name = "acme-hello"
    help = "Print a greeting"

    def configure(self, parser):
        parser.add_argument("--who", default="world")

    def run(self, args, logger):
        print(f"hello {args.who}")
        return 0

command = HelloCommand()
```

```toml
[project.entry-points."fluid_build.commands"]
acme = "acme_cli.command:command"
```

Test with `CommandPluginTestHarness`. The SDK's [plugin groups reference](https://github.com/Agenticstiger/forge-cli-sdk/blob/main/docs/reference/plugin-groups.md) has every attribute, the rules forge-cli applies, and runnable example packages (`acme-chat-alerts`, `acme-erasure-action`, `acme-hello-command`). Install the SDK from [PyPI](https://pypi.org/project/data-product-forge-sdk/): `pip install 'data-product-forge-sdk>=0.12,<1'`.

## Shared concepts across roles

### `ContractHelper`

Read-only parser over fluid contract dicts. Use it instead of raw dict-walking; a missing field returns `None`, `{}` or `[]`:

```python
from fluid_sdk import ContractHelper

c = ContractHelper(contract)
c.id                   # str | None
c.name                 # str | None
c.description          # str | None
c.owner                # dict (e.g. {"email": "..."})
c.domain               # str | None
c.metadata             # full metadata dict
c.labels               # the contract's root-level `labels` map
c.environments         # full environments dict
c.environment_names()  # list[str]
c.exposes              # list[ExposeSpec]
c.consumes             # list[ConsumeSpec]
c.builds               # list[BuildSpec]
c.extensions           # dict — the contract.extensions block
```

If a field is missing, the property returns `None` (or `[]` / `{}`) instead of raising. Your plugin can fail gracefully on partial contracts.

### `PluginAction`

Generic action dataclass. Roles use it differently:

| Role | Action builder | Common `op` values |
|---|---|---|
| `CustomScaffold` | `write_file_action(...)` | `write_file` |
| `Validator` | `Finding.to_action()` | `emit_finding` |
| `InfraProvider` | `provision_action(...)` | provider-specific (`provision_dataset`, `create_table`, `grant_access`, …) |
| `CatalogAdapter` | `catalog_entry_action(...)` | provider-specific (`upsert_entity`, `link_lineage`, …) |

Each role ships its own action builder (the `InfraProvider` / `CatalogAdapter` builders are new in SDK 0.10.0). You can also use raw `PluginAction(op="...", ...)` for anything not covered by the helper functions.

### `ExecutionResult`

What `apply()` returns. Carries `plugin` (the plugin's name), `role`, `applied` / `failed` counts, `duration_sec`, `timestamp`, and per-action `results`, plus `artifacts` and `warnings` lists. There is no `provider` field; `ExecutionResult(provider=...)` raises `TypeError`.

### Typed value domains

SDK 0.10.0 adds zero-dependency str-enums so plugins stop passing bare strings for the values the CLI keys behaviour off:

- **`Severity`** — `info` / `warn` / `error` / `critical`. `FAILING_SEVERITIES` is the set the CLI treats as a failure (drives the non-zero exit code). `Severity.coerce(value)` **fails safe**: an unrecognised severity is treated as `ERROR`, never silently passed through. Use it anywhere you accept a severity from untrusted input.
- **`ActionStatus`** — the status of a single applied action.
- **`Phase`** — the lifecycle phase an action runs in.

Each is a `str` subclass, so existing string-comparison code keeps working; the enum just gives you a typed, fail-safe vocabulary. The `Finding.severity` field accepts a `Severity` value.

```python
from fluid_sdk import Severity, FAILING_SEVERITIES

Severity.coerce("warn")        # Severity.WARN
Severity.coerce("nonsense")    # Severity.ERROR  ← fails safe
Severity.ERROR in FAILING_SEVERITIES   # True
```

### Plugin capabilities

`BasePlugin.capabilities()` returns a typed **`PluginCapabilities`** (SDK 0.10.0) — a structured self-description of what a plugin can do. This is distinct from the legacy provider-only `ProviderCapabilities`; `PluginCapabilities` is role-agnostic and available on every `BasePlugin` subclass.

### SDK to CLI compat declaration

`PluginMetadata` (SDK 0.10.0) carries two compat fields:

- **`sdk_protocol_version`** — the SDK protocol the plugin was built against.
- **`requires_cli`** — a PEP 440 specifier (e.g. `">=0.7.0"`) declaring which CLI versions the plugin supports.

The module-level constants back these: `SDK_PROTOCOL_VERSION` (= 1), `MIN_CLI_VERSION` (`"0.7.0"`), `MAX_CLI_VERSION` (`None`, open-ended), and the `cli_requirement()` helper (→ `">=0.7.0"`).

The split is deliberate, on the dbt `require-dbt-version` model: the **SDK declares** the compatibility it needs; the **CLI gates** on it. The host-side gate (opt-in `FLUID_PLUGIN_STRICT_COMPAT=1`) is documented in the [trust model](./trust-model.md#sdk-to-cli-version-compat-gate).

### `PluginMetadata`

Override `get_plugin_info()` if you want richer metadata than the default `PluginMetadata(name=cls.name, role=cls.role)`. `fluid plugins --detailed` (CLI 0.10.0) reads from this for every ALLOWED plugin, as do custom dashboards and IDE integrations:

```python
@classmethod
def get_plugin_info(cls):
    return PluginMetadata(
        name=cls.name,
        role=cls.role,
        display_name="GitLab CI Scaffold",
        description="...",
        version="0.1.0",
        author="...",
        tags=["ci", "gitlab"],
    )
```

## Inheriting tests

Every role has a matching `*TestHarness` in `fluid_sdk.testing`:

```python
from fluid_sdk.testing import (
    PluginTestHarness,          # base: generic invariants for any role
    CustomScaffoldTestHarness,  # adds scaffold-specific tests (atomic write, sha256, traversal)
    ValidatorTestHarness,       # validator-specific conformance
    InfraProviderTestHarness,   # provider plan/apply shape + op routing
    CatalogAdapterTestHarness,  # catalog-adapter conformance
)


class TestMyScaffold(CustomScaffoldTestHarness):
    plugin_class = MyScaffold
    sample_contracts = [LOCAL_CONTRACT]   # required: at least one contract
    # Inherits all the tests. Add your own scenarios below if needed.
```

The harness's tests come with the subclass; your own scenarios are extra `test_*` methods.

As of SDK 0.10.0, each of the four roles has a matching `*TestHarness` — subclass the role-specific one directly (`ValidatorTestHarness`, `InfraProviderTestHarness`, `CatalogAdapterTestHarness`) and add your fixture-driven scenarios as additional `test_*` methods.

## Source

- Role definitions: [`Agenticstiger/forge-cli-sdk/src/fluid_sdk/roles/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/src/fluid_sdk/roles)
- Test harnesses: [`Agenticstiger/forge-cli-sdk/src/fluid_sdk/testing/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/src/fluid_sdk/testing)

These are the truth source — when in doubt, read the class.
