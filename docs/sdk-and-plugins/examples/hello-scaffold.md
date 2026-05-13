# Example: `hello-scaffold` — the minimal viable plugin

The smallest plugin that proves the contract: 30 lines of Python, one entry-point, one file output. If you can read this page in 5 minutes you can author a `CustomScaffold` plugin.

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/hello-scaffold/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/hello-scaffold). The version inline below is mirrored from there — copy-paste freely.

## What it does

Given any fluid contract, `hello-scaffold` emits one `README.md` with the contract's name and description.

```bash
fluid generate custom-scaffold
# ✓ 1 file written
#   README.md
```

That's it. No bundles, no Jinja, no static directory — just `plan() -> [write_file_action(...)]`.

## Files

```
hello-scaffold/
├── pyproject.toml            ← 18 lines  — package + entry-point
├── src/hello_scaffold/
│   ├── __init__.py           ←  empty
│   └── scaffold.py           ← 30 lines  — the plugin
├── tests/
│   └── test_scaffold.py      ←  4 lines  — gets ~20 conformance tests free
└── demo.py                   ← runs plan() against LOCAL_CONTRACT, no CLI needed
```

## `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hello-scaffold"
version = "0.1.0"
description = "Minimal FLUID CustomScaffold example — emits one README.md from any contract"
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

The one line that makes it work: `[project.entry-points."fluid_build.custom_scaffolds"] hello = "hello_scaffold.scaffold:HelloScaffold"`. After `pip install -e .`, `fluid generate custom-scaffold` discovers your plugin under the name `hello`.

## `src/hello_scaffold/scaffold.py`

```python
"""Hello-scaffold — the smallest possible CustomScaffold plugin."""

from fluid_sdk import ContractHelper, CustomScaffold, write_file_action


class HelloScaffold(CustomScaffold):
    name = "hello-scaffold"

    def plan(self, contract):
        c = ContractHelper(contract)
        readme = (
            f"# {c.name or c.id or 'Unnamed'}\n\n"
            f"{c.description or ''}\n"
        )
        return [
            write_file_action(
                path="README.md",
                content=readme.encode("utf-8"),
                resource_id="readme",
            ).to_dict(),
        ]
```

Two methods of note (both inherited from `CustomScaffold` / `BasePlugin`, no override needed):

- **`apply(actions)`** — the reference implementation writes files atomically with sha256 verification + path-traversal guards. You get this for free.
- **`get_plugin_info()`** — class metadata used by `fluid plugins` (dormant today) and any registry that reads `PluginMetadata`. Defaults to a `PluginMetadata` derived from `name` + `role`. Override if you want richer metadata (see [gitlab-ci-scaffold example](./gitlab-ci-scaffold.md)).

## `tests/test_scaffold.py`

```python
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from hello_scaffold.scaffold import HelloScaffold


class TestHelloScaffold(CustomScaffoldTestHarness):
    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

Four lines for **~20 tests** (13 from the base PluginTestHarness + 7 from CustomScaffoldTestHarness). The harness runs against your `plugin_class` and checks: role declaration, plan-determinism, idempotency, path-traversal rejection, sha256 verification, atomic-write semantics, public-API stability, and more. Customize by overriding individual test methods.

## Run it

```bash
# in the hello-scaffold/ directory
pip install -e ".[dev]"
pytest
# ============== 20 passed in 0.07s ===============
```

Then in any fluid project:

```bash
pip install data-product-forge data-product-forge-custom-scaffold
```

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.3"
metadata:
  id: my-first-product
  name: My First Product
  description: Generated from the hello-scaffold plugin.
  owner: { email: data-team@example.com }
  layer: Bronze
  productType: SDP

extensions:
  customScaffold:
    libraries:
      - id: hi
        source: { kind: entrypoint, name: hello-scaffold }
    patterns:
      - use: hi:main
```

```bash
fluid generate custom-scaffold
# ✓ 1 file written, 0 failed
#   README.md

cat README.md
# # My First Product
#
# Generated from the hello-scaffold plugin.
```

## You'll know it worked when

- `pytest` reports 20+ passes against your plugin class.
- the `importlib.metadata.entry_points(group='fluid_build.custom_scaffolds')` one-liner (run from anywhere) shows `hello-scaffold` in the result.
- `fluid generate custom-scaffold` writes a `README.md` whose body matches the contract's `metadata.name` and `metadata.description`.
- Running the same command twice produces byte-identical output (determinism is one of the conformance tests).

## When **not** to use this pattern

If your generation logic depends on **the templates a non-Python user can edit**, build a YAML+Jinja bundle instead of a Python plugin. See [gitlab-ci-scaffold](./gitlab-ci-scaffold.md) (which uses both Python *and* templates) and the [your-own-CI journey](../journeys/your-own-ci.md).

## Next

- **More substantial example:** [`gitlab-ci-scaffold`](./gitlab-ci-scaffold.md) — full project layout (README + `.gitlab-ci.yml` + per-env config), still under 150 LOC.
- **Validator instead:** [`steward-validator`](./steward-validator.md) — same shape, different role.
- **Apply-time check:** [`apply-hook-prod-key-guard`](./apply-hook-prod-key-guard.md) — runs at `fluid apply`, not generation.
- **Reference:** [Roles](../reference/roles.md), [Entry points](../reference/entry-points.md).
