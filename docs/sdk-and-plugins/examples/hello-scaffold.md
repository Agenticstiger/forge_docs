# Example: `hello-scaffold` — the minimal viable plugin

The smallest plugin that proves the contract: about 20 lines of Python, one entry-point, one file output. If you can read this page in five minutes you can author a `CustomScaffold` plugin.

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/hello-scaffold/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/hello-scaffold). The version inline below is mirrored from there — copy-paste freely.

## What it does

Given any fluid contract, `hello-scaffold` emits one `README.md` with the contract's name and description.

```bash
fluid custom-scaffold
```

```text
✓ 1 files written, 0 failed (0.0004s)
  <cwd>/README.md
```

That's it. No bundles, no Jinja, no static directory — just `plan() -> [write_file_action(...)]`.

## Files

```
hello-scaffold/
├── pyproject.toml            ← package + entry-point
├── src/hello_scaffold/
│   ├── __init__.py           ←  empty
│   └── scaffold.py           ← the plugin
├── tests/
│   └── test_scaffold.py      ← four lines; the SDK adds the conformance tests
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
dependencies = ["data-product-forge-sdk>=0.10,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

The one line that makes it work: `[project.entry-points."fluid_build.custom_scaffolds"] hello = "hello_scaffold.scaffold:HelloScaffold"`. After `pip install -e .`, `fluid custom-scaffold` finds your plugin under the name `hello`. A contract's `source: { kind: entrypoint, name: hello }` refers to this key; the class's own `name = "hello-scaffold"` attribute is not what the lookup uses.

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
- **`get_plugin_info()`** — class metadata read by `fluid plugins --detailed` (CLI 0.10.0, for ALLOWED plugins) and any registry that reads `PluginMetadata`. Defaults to a `PluginMetadata` derived from `name` + `role`. Override if you want richer metadata (see [gitlab-ci-scaffold example](./gitlab-ci-scaffold.md)).

## `tests/test_scaffold.py`

```python
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from hello_scaffold.scaffold import HelloScaffold


class TestHelloScaffold(CustomScaffoldTestHarness):
    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

Four lines of your own, and the SDK's `CustomScaffoldTestHarness` runs its conformance tests against your `plugin_class`: role declaration, plan determinism, idempotency, path-traversal rejection, sha256 verification, atomic-write semantics, and more. Override individual test methods to customise. `sample_contracts` must hold at least one contract, or the harness fails `test_sample_contracts_present`.

## Run it

```bash
# in the hello-scaffold/ directory
pip install -e ".[dev]"
pytest
```

```text
.........................                                                [100%]
25 passed in 0.08s
```

Then in any fluid project:

```bash
pip install data-product-forge data-product-forge-custom-scaffold
```

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.demo.my_first_product_v1
name: My First Product
description: Generated from the hello-scaffold plugin.
domain: demo
metadata:
  layer: Bronze          # (medallion) Bronze / Silver / Gold
  productType: SDP       # (Data Mesh) SDP / ADP / CDP, paired with layer
  owner: { team: data-team, email: data-team@example.com }
exposes:
  - exposeId: items
    kind: table
    binding:
      platform: local
      format: parquet
      location: { path: out/items.parquet }
    contract:
      schema:
        - { name: item_id, type: STRING, required: true }
extensions:
  customScaffold:
    libraries:
      - id: hi
        # 'name' matches the entry-point KEY in pyproject.toml ("hello").
        source: { kind: entrypoint, name: hello }
    patterns:
      - use: hi:main
```

```bash
fluid custom-scaffold
# ✓ 1 files written, 0 failed
#   <cwd>/README.md

cat README.md
# # My First Product
#
# Generated from the hello-scaffold plugin.
```

## You'll know it worked when

- `pytest` passes against your plugin class.
- `fluid plugins` lists `hello` under `custom_scaffold` (with the `NOT DISPATCHED` label explained in the [quickstart](../quickstart.md)), or the `importlib.metadata.entry_points(group='fluid_build.custom_scaffolds')` one-liner shows `hello`.
- `fluid custom-scaffold` writes a `README.md` whose body matches the contract's `name` and `description`.
- Running the same command twice produces byte-identical output (determinism is one of the conformance tests).

## When **not** to use this pattern

If your generation logic depends on **the templates a non-Python user can edit**, build a YAML+Jinja bundle instead of a Python plugin. See [gitlab-ci-scaffold](./gitlab-ci-scaffold.md) (which uses both Python *and* templates) and the [your-own-CI journey](../journeys/your-own-ci.md).

## Next

- **More substantial example:** [`gitlab-ci-scaffold`](./gitlab-ci-scaffold.md) — full project layout (README + `.gitlab-ci.yml` + per-env config), still under 150 LOC.
- **Validator instead:** [`steward-validator`](./steward-validator.md) — same shape, different role.
- **Apply-time check:** [`apply-hook-prod-key-guard`](./apply-hook-prod-key-guard.md) — runs at `fluid apply`, not generation.
- **Reference:** [Roles](../reference/roles.md), [Entry points](../reference/entry-points.md).
