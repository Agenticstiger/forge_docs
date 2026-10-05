# Quickstart — your first plugin

You're going to write a tiny plugin that turns a fluid contract into a `README.md` file. About 15 lines of Python, two TOML stanzas, one CLI command. Realistic time: **5–10 minutes** end to end (the longest part is `pip install`).

By the end you'll have:

- A working `CustomScaffold` plugin that `fluid custom-scaffold` finds by its entry-point name.
- The SDK's conformance tests passing against it (you write four lines, the SDK adds the rest).
- A clear mental model of what to change to make it produce something other than `README.md`.

## Prerequisites

- Python `>=3.10` (`python --version` confirms)
- `pip` on `PATH`
- A directory you can `cd` into

That's it. No cloud creds, no Docker, no extra services.

## Step 0 — see the result first

If you skip everything else on this page, run this in a fresh directory and watch the output:

```bash
pip install --quiet data-product-forge data-product-forge-custom-scaffold
git clone --quiet --depth 1 https://github.com/Agenticstiger/forge-cli-sdk
cd forge-cli-sdk/examples/hello-scaffold
pip install --quiet -e .

mkdir /tmp/quickstart-demo && cd /tmp/quickstart-demo

cat > contract.fluid.yaml <<'EOF'
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
EOF

fluid custom-scaffold
```

What you should see (CLI 0.18.1 prints absolute paths; `<cwd>` stands for the directory you ran it in):

```text
Resolved libraries:
  hi  (entrypoint)  version=0.1.0

✓ 1 files written, 0 failed (0.0004s)
  <cwd>/README.md
```

The engine also writes a `fluid-scaffold.lock` next to the contract.

And `cat README.md`:

```markdown
# My First Product

Generated from the hello-scaffold plugin.
```

Two things to notice:

1. **The contract's `name` ("My First Product") and `description` end up in the rendered file.** The contract drives the output.
2. **Running `fluid custom-scaffold` twice produces the same bytes.** The harness you add in Step 4 tests for this.

That's the result. Now we'll build it from scratch so you understand each piece.

## Step 1 — set up the package skeleton

```bash
mkdir my-first-plugin && cd my-first-plugin
mkdir -p src/hello_scaffold tests
touch src/hello_scaffold/__init__.py tests/__init__.py
```

You should now have:

```text
my-first-plugin/
├── src/hello_scaffold/
│   └── __init__.py     (empty)
└── tests/
    └── __init__.py     (empty)
```

## Step 2 — write `pyproject.toml`

This is where the magic happens — one entry-point line is what makes pip + forge find your plugin.

```toml
# my-first-plugin/pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hello-scaffold"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["data-product-forge-sdk>=0.10,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

# ↓↓↓ This is the discovery line. After `pip install`, the CLI knows
#     about a plugin called "hello" living at hello_scaffold.scaffold:HelloScaffold.
[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`fluid_build.custom_scaffolds` is one of several entry-point groups. Others (`fluid_build.validators`, `fluid_build.apply_hooks`, `fluid_build.providers`, `fluid_build.catalog_adapters`, …) are for the other plugin shapes. The group for scaffolds is walked by the scaffold engine's `fluid custom-scaffold` command, not by the CLI itself. See the [Entry points reference](./reference/entry-points.md) for the full set and which code discovers each.

## Step 3 — write the plugin

```python
# my-first-plugin/src/hello_scaffold/scaffold.py
"""The smallest possible CustomScaffold plugin."""

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

That's the whole plugin. Three things to know about what you didn't write:

- **`apply(actions)` is inherited** from `CustomScaffold`. The reference implementation writes files atomically with `sha256` verification and path-traversal guards. You don't override it unless you're doing something custom.
- **`ContractHelper`** is a read-only parser over the contract dict. `c.name`, `c.id`, `c.description`, `c.labels`, `c.environment_names()` and the rest return `None`, `{}` or `[]` for a missing field instead of raising, so a partial contract does not crash your plugin.
- **`write_file_action(...)`** builds a canonical action dict with sha256 + base64-encoded content + atomic-write semantics. Returning these from `plan()` is the entire interface.

## Step 4 — write the test (four lines of yours, the rest from the SDK)

```python
# my-first-plugin/tests/test_scaffold.py
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from hello_scaffold.scaffold import HelloScaffold


class TestHelloScaffold(CustomScaffoldTestHarness):
    plugin_class = HelloScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

Run it:

```bash
pip install -e ".[dev]"
pytest
```

You should see (the count depends on the SDK version; this is SDK 0.10.0):

```text
.........................                                                [100%]
25 passed in 0.08s
```

The harness runs its invariants against your `plugin_class`: the role is declared correctly, `plan()` is deterministic and its actions are JSON-serialisable, destinations are free of path traversal, sha256 verification works, the atomic-write behaviour holds, and more. You wrote four lines. `sample_contracts` must hold at least one contract: with an empty list the harness fails `test_sample_contracts_present`, so that it cannot pass against nothing.

## Step 5 — drive it from a real contract

In a separate working directory:

```bash
mkdir -p /tmp/my-product && cd /tmp/my-product
pip install data-product-forge data-product-forge-custom-scaffold

cat > contract.fluid.yaml <<'EOF'
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
EOF

fluid custom-scaffold
```

You should see the same output as in Step 0:

```text
Resolved libraries:
  hi  (entrypoint)  version=0.1.0

✓ 1 files written, 0 failed (0.0004s)
  <cwd>/README.md
```

```bash
cat README.md
```

```markdown
# My First Product

Generated from the hello-scaffold plugin.
```

## Why both `metadata.layer` and `metadata.productType`?

Contract schema 0.7.3 introduced the Data Mesh-aligned `productType` (SDP / ADP / CDP) alongside the medallion `layer` (Bronze / Silver / Gold). Set the one your org uses, or both. When both are present `fluid validate` checks them against each other: `layer: Bronze` with `productType: CDP` fails with `metadata consistency: metadata.layer='Bronze' and metadata.productType='CDP' are inconsistent`.

Canonical mapping: Bronze↔SDP, Silver↔ADP, Gold↔CDP. Detail in the [data products section](../data-products/product-type.md).

## When it doesn't work — common gotchas

::: details The plugin doesn't seem to register
Most common cause: you forgot `pip install -e .` after editing `pyproject.toml`. Entry-points are read at install time, not at runtime — pip needs to rewrite the dist-info.

```bash
pip install -e .

# Confirm the entry-point registered. `fluid plugins` lists installed
# plugins per role with allow/block status:
fluid plugins                                 # or: fluid plugins list --json
fluid plugins list --detailed                 # also shows declared metadata

# Or query importlib.metadata directly:
python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='fluid_build.custom_scaffolds'):
    print(f'{ep.name}: {ep.value}')
"
# Should print: hello: hello_scaffold.scaffold:HelloScaffold
```

If that doesn't fix it, double-check the entry-point line in `pyproject.toml` — the value side has to be `module.path:ClassName` exactly. A common typo:

```toml
# wrong — points at the module, not the class
hello = "hello_scaffold.scaffold"

# right — module:ClassName
hello = "hello_scaffold.scaffold:HelloScaffold"
```
:::

::: details `fluid custom-scaffold` says `no plugin named 'hello-scaffold' found`
The full message is:

```text
❌ Unexpected error: no plugin named 'hello-scaffold' found under entry-point 
group 'fluid_build.custom_scaffolds'. Install the package that provides it, then
re-run. Available plugins: ['hello']
```

The contract's `source.name` has to match the entry-point **key** in `pyproject.toml`, not the class name or the plugin's `name` attribute. The message lists the keys it can see:

```toml
# pyproject.toml — the KEY is what contracts reference
[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"
#  ↑ this is the name users put in source.name
```

```yaml
# contract.fluid.yaml
source: { kind: entrypoint, name: hello }
                                  # ↑ matches the pyproject key
```

If you renamed the entry-point, re-run `pip install -e .` and try again.
:::

::: details `fluid plugins` shows my scaffold as `NOT DISPATCHED`
`fluid plugins` lists a `custom_scaffold` plugin under a `custom_scaffold  (1)  — NOT DISPATCHED` heading and ends with `custom_scaffold: declared and governed, but this build has no dispatch site — plugins registered under it are never invoked.` That describes the CLI itself: nothing in `fluid` walks the `fluid_build.custom_scaffolds` group. The `fluid custom-scaffold` command comes from `data-product-forge-custom-scaffold`, and that engine looks your plugin up by entry-point name when it runs. Observed on CLI 0.18.1 with engine 0.4.1: a plugin carrying this label rendered its files normally. The engine applies the same `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST` policy itself before it loads the plugin, and `fluid plugins` still shows the allow/block status and the package that installed it.
:::

::: details Should `plan()` return action objects or dicts?
Return dicts: call `.to_dict()` on every `write_file_action(...)`. `plan()` is documented to return a list of action dicts, and the harness checks that they are JSON-serialisable. On CLI 0.18.1 with engine 0.4.1, a plugin that returned the action objects unconverted still wrote its file, so a missing `.to_dict()` is not what makes output empty; look at the entry-point and `source.name` first.

```python
return [
    write_file_action(...).to_dict(),
]
```
:::

::: details `ContractHelper(contract).name` is `None`
The contract is missing its root `name`. Either add it to the YAML, or fall back gracefully in your plugin:

```python
title = c.name or c.id or "Unnamed"
```

Most contract fields are optional — `ContractHelper` returns `None` for anything missing rather than raising. That's deliberate, so plugins can fail gracefully on partial contracts.
:::

## What's next

You wrote a `CustomScaffold` that emits one file from contract data. Three directions you can go:

- **More substantial:** [`gitlab-ci-scaffold` example](./examples/gitlab-ci-scaffold.md) — same shape, but emits a full project (README + `.gitlab-ci.yml` + per-env config), and the contract drives the env list.
- **A different role:** [`steward-validator` example](./examples/steward-validator.md) — same shape, but it runs at `fluid validate` and emits structured findings instead of files.
- **Apply-time invariants:** [apply-hook example](./examples/apply-hook-prod-key-guard.md) — runs right before `fluid apply` does anything destructive.

When you're ready to ship the plugin to PyPI, read [Packaging](./reference/packaging.md) — covers `py.typed`, classifiers, and trusted-publishing.

Once installed, `fluid plugins --detailed` surfaces a plugin's declared metadata, and operators can gate which plugins load with `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST` — see the [trust model](./reference/trust-model.md#operator-governance-—-allowlist-and-blocklist).

## Source

The plugin you built here matches the upstream example:

- Repo: [`Agenticstiger/forge-cli-sdk`](https://github.com/Agenticstiger/forge-cli-sdk)
- Path: `examples/hello-scaffold/`

Detail walkthrough with the same source: [examples/hello-scaffold](./examples/hello-scaffold.md).
