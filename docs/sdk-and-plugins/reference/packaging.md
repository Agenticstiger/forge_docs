# Packaging

How to package a plugin for `pip install`. The shape is straightforward — modern Python packaging — but a few details are easy to get wrong on the first try.

## The minimal `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "your-plugin-name"
version = "0.1.0"
description = "What it does in one sentence"
readme = {file = "README.md", content-type = "text/markdown"}
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
authors = [
    {name = "Your Name or Team", email = "you@example.com"},
]
keywords = ["data-product-forge", "plugin"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Code Generators",
    "Typing :: Typed",
]
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "ruff", "black"]

# The one line that registers your plugin with the CLI.
# Change the group + key based on what you're building — see entry-points reference.
[project.entry-points."fluid_build.custom_scaffolds"]
your-plugin = "your_pkg.scaffold:YourScaffold"

[project.urls]
Repository = "https://github.com/your-org/your-plugin"
Issues = "https://github.com/your-org/your-plugin/issues"

[tool.setuptools.packages.find]
where = ["src"]

# Ship py.typed so downstream type-checkers see your annotations
[tool.setuptools.package-data]
your_pkg = ["py.typed"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.black]
line-length = 100
target-version = ["py310", "py311", "py312", "py313", "py314"]
```

Things to change for your plugin:

1. **`name`** — your PyPI package name (kebab-case, globally unique on PyPI).
2. **`version`** — Semantic Versioning. Start at `0.1.0`.
3. **`dependencies`** — `data-product-forge-sdk>=0.9,<1` is the only mandatory one. Add `data-product-forge-custom-scaffold` if your plugin is consumed via the custom-scaffold engine (most CustomScaffold plugins).
4. **`[project.entry-points."<group>"]`** — pick the right group per [entry-points reference](./entry-points.md). The **key** is the user-facing name; the **value** is `module:Symbol`.
5. **`[project.urls]`** — your real GitHub/GitLab URLs.

## Directory layout

```text
your-plugin/
├── pyproject.toml
├── README.md
├── LICENSE                       (Apache-2.0 text — required if you declare Apache-2.0 above)
├── CHANGELOG.md
├── src/
│   └── your_pkg/                 (snake_case Python package name)
│       ├── __init__.py
│       ├── py.typed              (empty file — PEP 561 marker)
│       └── scaffold.py           (or validator.py / hook.py)
└── tests/
    ├── __init__.py
    └── test_scaffold.py
```

Two non-obvious bits:

- **`src/` layout** — your Python package lives one level deeper than the project root. Prevents accidental imports from the project root during dev (e.g. when you `pip install -e .` then `cd` into the project and Python finds the source instead of the installed wheel).
- **`py.typed` file** — empty marker, signals to type-checkers (mypy, pyright) that this package ships type annotations. Without it, `Any` is the assumed return type of every function in your package when downstream code type-checks against it.

## Picking entry-point groups

Quick lookup:

| You're building… | Group | Value points at | Example key |
|---|---|---|---|
| `CustomScaffold` subclass | `fluid_build.custom_scaffolds` | the class | `hello-scaffold` |
| `Validator` subclass | `fluid_build.validators` | the class | `steward-required` |
| `InfraProvider` subclass | `fluid_build.providers` | the class | `mycloud` |
| `CatalogAdapter` subclass | `fluid_build.catalog_adapters` | the class | `datahub-adapter` |
| A function adding `fluid <name>` subcommand | `fluid_build.commands` | the `register()` function | `my-cmd` |
| A function validating `contract.extensions.<key>` | `fluid_build.extension_validators` | the `validate()` function | `myKey` |
| A function checking apply-time invariants | `fluid_build.apply_hooks` | the hook function | `my-hook` |

Detail: [entry-points reference](./entry-points.md).

## Local development loop

```bash
git clone https://github.com/you/your-plugin
cd your-plugin

python -m venv .venv
source .venv/bin/activate

# Install with dev extras + the CLI itself
pip install -e ".[dev]"
pip install data-product-forge data-product-forge-custom-scaffold

# Verify the entry-point registered. The CLI's `fluid plugins` command
# is dormant (the module exists but isn't wired into bootstrap), so use
# importlib.metadata directly:
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

# Run tests
pytest

# Lint + format
ruff check src/ tests/
black --check src/ tests/
```

`pip install -e .` is **editable** — code changes in `src/` are picked up immediately by the next `python` invocation. But **entry-points are baked in at install time** — if you edit `pyproject.toml`, you have to re-run `pip install -e .` for the change to register.

## Conformance harness

The SDK ships test harnesses for each role. Inherit them in your test file:

```python
# tests/test_scaffold.py
from fluid_sdk.testing import CustomScaffoldTestHarness, LOCAL_CONTRACT
from your_pkg.scaffold import YourScaffold


class TestYourScaffold(CustomScaffoldTestHarness):
    plugin_class = YourScaffold
    sample_contracts = [LOCAL_CONTRACT]
```

Four lines, 20 conformance tests run automatically. The harnesses available today:

- `PluginTestHarness` — generic; runs on any role (13 tests)
- `CustomScaffoldTestHarness` — scaffold-specific atomic writes, sha256, traversal (7 tests, inherits the 13 above)

Role-specific subharnesses for `Validator`, `InfraProvider`, and `CatalogAdapter` are on the SDK roadmap. Until they land, subclass `PluginTestHarness` for those roles and add your own role-specific assertions as additional `test_*` methods. See `src/fluid_sdk/testing/role_harnesses.py` for the pattern.

Add your plugin-specific scenarios as additional methods on the same class. They run alongside the inherited tests.

## CI / GitHub Actions template

A minimal CI workflow for an SDK plugin:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install ruff "black==24.10.0"
      - run: ruff check src/ tests/
      - run: black --check src/ tests/

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine check dist/*
```

Matches the matrix the SDK + scaffold packages run on PyPI publish.

## Publishing to PyPI

Recommended path: GitHub Actions + **trusted publishing** (no long-lived tokens).

### One-time setup

1. Reserve the project name on PyPI (or TestPyPI if you want to rehearse first).
2. Configure trusted publishing at `https://pypi.org/manage/project/your-plugin/settings/publishing/`:
   - **Owner:** your GitHub org/user
   - **Repository name:** your plugin's repo
   - **Workflow filename:** `release.yml`
   - **Environment:** (blank, or `release` if you want an approval gate)

### Publish on tag push

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags: ["v*.*.*"]

permissions:
  contents: write   # for the GitHub Release
  id-token: write   # for PyPI trusted publishing (OIDC)

jobs:
  release:
    runs-on: ubuntu-latest
    environment: pypi
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Tag a release:

```bash
git tag v0.1.0
git push origin v0.1.0
# Workflow runs → publishes to PyPI
```

For pre-releases (`rc1`, `b1`, `a1`, `.dev1`): same workflow. PyPI marks them as pre-releases via PEP 440 — `pip install your-plugin` skips them; `pip install --pre your-plugin` or `pip install your-plugin==0.2.0rc1` opts in.

## Versioning policy

Semantic versioning. For SDK plugins specifically:

- **`0.x.y`** — pre-1.0; minor versions can break the API. Pin upper bound (`>=0.x,<0.<x+1>`).
- **`1.x.y`** — stable. Minor versions add features; patch versions fix bugs; major versions break the API.

For the SDK dependency, pin to `data-product-forge-sdk>=0.9,<1` (until the SDK ships 1.0; bump the upper bound when it does).

For the CLI dependency (if your plugin needs runtime CLI features), pin to the minor line: `data-product-forge>=0.8,<0.9`.

## Changelog

Use the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Even for v0.x plugins. The CLI's release workflow uses your `CHANGELOG.md` to write the GitHub Release body — if you don't have one, the body falls back to git log, which is less useful.

```markdown
# Changelog

## [Unreleased]

## [0.1.0] — 2026-05-12

### Added
- Initial release.
- Supports fluidVersion 0.7.1, 0.7.2, 0.7.3.

### Notes
- Beta classifier; minor versions may break the API until 1.0.
```

## Common gotchas

::: details Entry-point doesn't register
You forgot `pip install -e .` after editing `pyproject.toml`. Entry-points are read at install time, not at runtime. The fix is one command. the `importlib.metadata.entry_points` one-liner above is your sanity check (the CLI's `fluid plugins` command is dormant).
:::

::: details Type-checkers complain `Module 'fluid_sdk' has no attribute …`
The SDK ships `py.typed`. If `from fluid_sdk import CustomScaffold` resolves at runtime but mypy/pyright say "no attribute", verify you're on `data-product-forge-sdk>=0.9.0`. Earlier dev versions of the SDK had inconsistent typing.

Your own package should also ship `py.typed` so downstream type-checkers see your annotations — see the layout section above.
:::

::: details `twine check` fails with "long_description must be valid markdown"
Your `README.md` has a syntax issue, or you forgot the `content-type`:

```toml
readme = {file = "README.md", content-type = "text/markdown"}
```

Without `content-type`, PyPI defaults to plain text and the rendered project page looks bad.
:::

::: details Tests pass locally, fail in CI on Python 3.13
Usually a missing `from __future__ import annotations` (changes how `X | Y` types are evaluated at runtime) or use of a deprecated stdlib API. The SDK pins to `>=3.10` so syntax-level features should be available; runtime behavior changes per version.

When in doubt, reproduce the failure with `pyenv install 3.13 && pyenv shell 3.13 && pytest`.
:::

::: details PyPI rejects the upload with "File already exists"
You tagged the same version twice. PyPI doesn't allow re-uploads — bump the patch (`0.1.0` → `0.1.1`) and tag again. For mistakes within minutes of upload, you can yank the version via the PyPI web UI; for changes after that, just bump.
:::

## Source

These packaging conventions are mirrored from the SDK + custom-scaffold's own `pyproject.toml`:

- [SDK pyproject.toml](https://github.com/Agenticstiger/forge-cli-sdk/blob/main/pyproject.toml)
- [Custom-scaffold pyproject.toml](https://github.com/Agenticstiger/data-product-forge-custom-scaffold/blob/main/pyproject.toml)

If your plugin shape differs from any of the above, the upstream `pyproject.toml`s are the truth source.
