# `fluid plugins`

List installed FLUID plugins per role, showing each plugin's allow/block governance status.

::: tip Where this fits
`fluid plugins` ships in `0.10.0`. It is the operator-facing window onto the plugin trust boundary — which plugins are installed, what role they fill, and whether the allow/block governance lists permit them to load. See the [SDK & Plugins trust model](/forge_docs/sdk-and-plugins/reference/trust-model.html) for the canonical governance rules.
:::

## Syntax

```bash
fluid plugins list [--json] [--role ROLE] [--detailed]
```

Bare `fluid plugins` runs `list` by default.

## Key options

| Option | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON. |
| `--role` | Limit to one role (`provider` / `validator` / `catalog` / `iac_provider` / `custom_scaffold`). |
| `--detailed` | Load ALLOWED plugins to show their declared metadata (version / author / license / url). Blocked plugins are never loaded. |

## Examples

```bash
fluid plugins
fluid plugins list
fluid plugins list --role provider
fluid plugins list --detailed
fluid plugins list --json
```

## Output (human table)

```text
🔌 Installed FLUID plugins (by role):

  provider  (4)
    • aws                          allowed
      from=data-product-forge 0.18.1
    • gcp                          allowed
      from=data-product-forge 0.18.1
    • local                        allowed
      from=data-product-forge 0.18.1
    • snowflake                    allowed
      from=data-product-forge 0.18.1
```

Each plugin takes two lines. The first is the entry-point name and its status. The second is `from=<distribution> <version>`, the installed package that provides it. With `--detailed`, plugins that declare metadata add `declares-version=`, `declares-author=`, `declares-license=`, `declares-url=` and `declares-requires_cli=` to that line.

A status, and a footer after the last role, can say more than `allowed`:

| Marker | Meaning |
| --- | --- |
| `BLOCKED (allow/block policy)` | `FLUID_PLUGINS_ALLOWLIST` or `FLUID_PLUGINS_BLOCKLIST` keeps it from loading. The footer reads `N plugin(s) blocked by FLUID_PLUGINS_ALLOWLIST / FLUID_PLUGINS_BLOCKLIST.` |
| `INCOMPATIBLE (requires_cli)` | The plugin declares a `requires_cli` the running CLI does not satisfy. With `FLUID_PLUGIN_STRICT_COMPAT=1` the CLI refuses to register it. |
| `— NOT DISPATCHED` after the role heading | The role is declared and governed, but this build has no code path that runs plugins registered under it. Listing it as `allowed` would read as active, so the heading says otherwise. In 0.18.1 that role is `custom_scaffold`. |

## Output (JSON)

`fluid plugins list --json` prints one key per role, each holding a list of plugins:

```json
{
  "apply_hook": [],
  "catalog": [],
  "command": [],
  "custom_scaffold": [],
  "extension_schema": [],
  "extension_validator": [],
  "iac_provider": [],
  "llm_provider": [],
  "modeling_technique": [],
  "provider": [
    {
      "allowed": true,
      "dispatched": true,
      "distribution": "data-product-forge 0.18.1",
      "group": "fluid_build.providers",
      "name": "aws"
    },
    ...
  ],
  "source_adapter": [],
  "validator": []
}
```

| Field | Meaning |
| --- | --- |
| `allowed` | `false` when the allow/block lists keep the plugin from loading. |
| `dispatched` | `false` when the role has no dispatch site in this build (the `NOT DISPATCHED` case above). |
| `distribution` | The installed package that provides the entry point, with its version. |
| `group` | The entry-point group the plugin was found in. |
| `name` | The entry-point name. |

## Notes

- **Roles surfaced.** The human table prints a role only when it has plugins. The JSON form lists every role, empty or not. `--help` names five roles for `--role` (`provider`, `validator`, `catalog`, `iac_provider`, `custom_scaffold`); the JSON also carries `apply_hook`, `command`, `extension_schema`, `extension_validator`, `llm_provider`, `modeling_technique` and `source_adapter`. With nothing installed in any role, the command prints `No third-party FLUID plugins installed.`
- **`--detailed` and the security boundary.** `--detailed` LOADS only ALLOWED plugins to read their declared metadata; BLOCKED plugins are NEVER loaded. That is the security boundary — a blocked plugin's code does not execute even to print its own version.
- **Spec exporters are not plugins.** The spec-export formats (`odps` / `odcs` / `odps-bitol`) are surfaced by [`fluid exporters`](./exporters.md), not by `fluid plugins`.

## Operator governance

Two operator env vars gate the code-executing entry-point groups before a plugin is loaded:

- `FLUID_PLUGINS_ALLOWLIST` — comma-separated entry-point names; if set, only these load.
- `FLUID_PLUGINS_BLOCKLIST` — comma-separated entry-point names; these never load.

A blocked plugin's code is not loaded. `fluid plugins` surfaces each plugin's allow/block status so you can confirm the gate before relying on it. A blocked *provider* then fails with [`ERR_PROVIDER_BLOCKED_BY_POLICY`](./providers.md#err-provider-blocked-by-policy) when a contract binds to it.

The version-compat gate is opt-in: `FLUID_PLUGIN_STRICT_COMPAT=1` refuses to load a plugin whose declared `requires_cli` (a PEP 440 specifier from the SDK's `PluginMetadata`) the running CLI version does not satisfy. Unset, a mismatch only warns.

## See also

- [SDK & Plugins — trust model](/forge_docs/sdk-and-plugins/reference/trust-model.html) — the canonical home for allow/block governance and the compat gate.
- [SDK & Plugins — entry points](/forge_docs/sdk-and-plugins/reference/entry-points.html) — the entry-point groups behind each role.
- [`fluid providers`](./providers.md) — the registered infrastructure providers. It lists more than the `provider` role here: the role holds only providers discovered through entry points.
- [`fluid exporters`](./exporters.md) — the spec-export formats a contract can be serialized to.
