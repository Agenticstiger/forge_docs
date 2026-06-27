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
    • gcp                          allowed
    • local                        allowed
    • snowflake                    allowed
```

## Output (JSON)

```json
{
  "apply_hook": [],
  "catalog": [],
  "command": [],
  "custom_scaffold": [],
  "extension_schema": [],
  "extension_validator": [],
  "iac_provider": [],
  "modeling_technique": [],
  "provider": [
    {
      "allowed": true,
      "group": "fluid_build.providers",
      "name": "aws"
    },
    {
      "allowed": true,
      "group": "fluid_build.providers",
      "name": "gcp"
    },
    {
      "allowed": true,
      "group": "fluid_build.providers",
      "name": "local"
    },
    {
      "allowed": true,
      "group": "fluid_build.providers",
      "name": "snowflake"
    }
  ],
  "source_adapter": [],
  "validator": []
}
```

## Notes

- **Roles surfaced.** The human table groups by role — `provider`, `validator`, `catalog`, `iac_provider`, `custom_scaffold`. The JSON form additionally lists the `apply_hook`, `command`, `extension_schema`, `extension_validator`, `modeling_technique`, and `source_adapter` groups.
- **`--detailed` and the security boundary.** `--detailed` LOADS only ALLOWED plugins to read their declared metadata; BLOCKED plugins are NEVER loaded. That is the security boundary — a blocked plugin's code does not execute even to print its own version.
- **Operator governance.** Two operator env vars gate every code-executing entry-point group BEFORE the plugin is loaded:
  - `FLUID_PLUGINS_ALLOWLIST` — comma-separated entry-point names; if set, only these load.
  - `FLUID_PLUGINS_BLOCKLIST` — comma-separated entry-point names; these never load.

  A blocked plugin's code never executes. `fluid plugins` surfaces each plugin's allow/block status so you can confirm the gate before relying on it.
- **Version-compat gate.** Opt-in `FLUID_PLUGIN_STRICT_COMPAT=1` refuses to load a plugin whose declared `requires_cli` (a PEP 440 specifier from the SDK's `PluginMetadata`) the running CLI version does not satisfy. Default (unset) is warn-only.
- **Spec exporters are not plugins.** The spec-export formats (`odps` / `odcs` / `odps-bitol`) are surfaced by [`fluid exporters`](./exporters.md), not by `fluid plugins`.

## See also

- [SDK & Plugins — trust model](/forge_docs/sdk-and-plugins/reference/trust-model.html) — the canonical home for allow/block governance and the compat gate.
- [SDK & Plugins — entry points](/forge_docs/sdk-and-plugins/reference/entry-points.html) — the entry-point groups behind each role.
- [`fluid providers`](./providers.md) — the registered infrastructure providers (a subset of the `provider` role).
- [`fluid exporters`](./exporters.md) — the spec-export formats a contract can be serialized to.
