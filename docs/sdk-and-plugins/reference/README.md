# Reference

Code-first reference for the SDK + plugin system. Skim the table, jump to what you need.

| Page | When you need it |
|---|---|
| [Roles](./roles.md) | Picking which `BasePlugin` subclass to extend. Class signatures, what each role gives you for free. |
| [Entry points](./entry-points.md) | Wiring your plugin into the CLI. The entry-point groups (3 CLI hooks + 4 role-level — 5 wired, 2 on the roadmap), their signatures, failure model. |
| [Trust model](./trust-model.md) | What the CLI guarantees about plugin execution. What it deliberately doesn't defend against. How to think about plugin trust in your org. |
| [Packaging](./packaging.md) | `pyproject.toml` template, `py.typed`, conformance harness, publishing to PyPI via trusted publishing. |
| [Companion packages](./companion-packages.md) | What's on PyPI (CLI + SDK + custom-scaffold), version pinning, dual-naming, upgrade compatibility. |

If you're new, **read the [quickstart](../quickstart.md) first**. The reference assumes you've built one working plugin and want to look something up.
