# Quickstart — your first plugin

You're going to write a tiny plugin that turns a fluid contract into a `README.md` file. About ~15 lines of Python, two TOML stanzas, one CLI command. Realistic time: **5–10 minutes** end to end (the longest part is `pip install`).

By the end you'll have:

- A working `CustomScaffold` plugin discovered automatically by `fluid generate custom-scaffold`.
- ~20 conformance tests passing against it (you write four lines, the SDK adds the rest).
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
    libraries: [{id: hi, source: {kind: entrypoint, name: hello-scaffold}}]
    patterns: [{use: hi:main}]
EOF

fluid generate custom-scaffold
```

What you should see:

```text
✓ 1 file written, 0 failed
  README.md
```

And `cat README.md`:

```markdown
# My First Product

Generated from the hello-scaffold plugin.
```

Two things to notice:

1. **The contract's `metadata.name` ("My First Product") and `metadata.description` end up in the rendered file.** The contract drives the output.
2. **Running `fluid generate custom-scaffold` twice produces the same bytes.** Determinism is a guarantee, not an accident.

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
dependencies = ["data-product-forge-sdk>=0.9,<1"]

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

The `fluid_build.custom_scaffolds` group is one of three entry-point groups the CLI walks at startup. The other two (`fluid_build.validators`, `fluid_build.apply_hooks`) are for the other plugin shapes — see [Entry points reference](./reference/entry-points.md) when you need them.

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
- **`ContractHelper`** is a read-only parser tolerant of every `fluidVersion` from `0.4` through `0.7.3`. `c.name`, `c.id`, `c.description`, `c.environment_names()`, etc. — your plugin doesn't break when the contract schema evolves.
- **`write_file_action(...)`** builds a canonical action dict with sha256 + base64-encoded content + atomic-write semantics. Returning these from `plan()` is the entire interface.

## Step 4 — write the test (just four lines, get 15 for free)

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

You should see:

```text
============== 20 passed in 0.07s ===============
```

The harness runs 20 invariants against your `plugin_class`: role declaration is correct, `plan()` is deterministic, output is idempotent, no path traversal in destinations, sha256 verification works, atomic-write semantics hold, public-API contract is intact, and more. You wrote four lines; you got 20 tests.

## Step 5 — drive it from a real contract

In a separate working directory:

```bash
mkdir -p /tmp/my-product && cd /tmp/my-product
pip install data-product-forge data-product-forge-custom-scaffold

cat > contract.fluid.yaml <<'EOF'
fluidVersion: "0.7.3"
metadata:
  id: my-first-product
  name: My First Product
  description: Generated from the hello-scaffold plugin.
  owner: { email: data-team@example.com }
  layer: Bronze         # (medallion) — Bronze / Silver / Gold
  productType: SDP      # (Data Mesh) — SDP / ADP / CDP (paired with layer)

extensions:
  customScaffold:
    libraries:
      - id: hi
        # The 'name' here matches the entry-point key in pyproject.toml.
        source: { kind: entrypoint, name: hello-scaffold }
    patterns:
      - use: hi:main
EOF

fluid generate custom-scaffold
```

You should see:

```text
✓ 1 file written, 0 failed
  README.md
```

```bash
cat README.md
```

```markdown
# My First Product

Generated from the hello-scaffold plugin.
```

## Why both `metadata.layer` and `metadata.productType`?

`fluidVersion: "0.7.3"` introduced the Data Mesh-aligned `productType` (SDP / ADP / CDP) alongside the existing medallion `layer` (Bronze / Silver / Gold). Both vocabularies are first-class — pick the one your org uses, or set both (the validator checks consistency).

Canonical mapping: Bronze↔SDP, Silver↔ADP, Gold↔CDP. Detail in the [data products section](../data-products/product-type.md).

## When it doesn't work — common gotchas

::: details The plugin doesn't seem to register
Most common cause: you forgot `pip install -e .` after editing `pyproject.toml`. Entry-points are read at install time, not at runtime — pip needs to rewrite the dist-info.

```bash
pip install -e .

# Confirm the entry-point registered. The CLI's `fluid plugins` command is
# dormant (the module exists but bootstrap doesn't register it), so use
# importlib.metadata directly:
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

::: details `fluid generate custom-scaffold` says `no plugin named 'hello-scaffold' found`
Check the contract's `source.name` matches the entry-point key, not the class name:

```toml
# pyproject.toml — the KEY is what end users reference
[project.entry-points."fluid_build.custom_scaffolds"]
hello-scaffold = "hello_scaffold.scaffold:HelloScaffold"
#  ↑ this is the name users put in source.name
```

```yaml
# contract.fluid.yaml
source: { kind: entrypoint, name: hello-scaffold }
                                  # ↑ matches the pyproject key
```

If you renamed the entry-point, re-run `pip install -e .` and try again.
:::

::: details Tests pass locally but `fluid generate` produces empty output
Your `plan()` is probably returning the action *objects* instead of dicts. The harness accepts both; the CLI requires `.to_dict()`. Add `.to_dict()` to every `write_file_action(...)` return:

```python
return [
    write_file_action(...).to_dict(),   # ← .to_dict() is required
]
```
:::

::: details `ContractHelper(contract).name` is `None`
The contract is missing `metadata.name`. Either add it to the YAML, or fall back gracefully in your plugin:

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

## Source

The plugin you built here matches the upstream example:

- Repo: [`Agenticstiger/forge-cli-sdk`](https://github.com/Agenticstiger/forge-cli-sdk)
- Path: `examples/hello-scaffold/`

Detail walkthrough with the same source: [examples/hello-scaffold](./examples/hello-scaffold.md).
