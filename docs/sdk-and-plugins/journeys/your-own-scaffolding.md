# You have a strict project layout, no problem

Your org has opinions: a data product lives in a repo with a specific directory structure, test framework, lint config, a Dockerfile that follows your security baseline, and a README following a template. New teams should not copy and paste from older products. They should declare a contract and get the whole skeleton.

This guide extends the pattern from [you have your own CI](./your-own-ci.md). The bundle shape is the same, but the templates render the *full project skeleton*, not just CI. Read that page first if you have not; the bundle mechanics (manifest, templates, static, git ref pinning, the render context) are the same.

By the end you will have:

- A bundle that generates `pyproject.toml`, `src/<product>/`, `tests/`, `Dockerfile`, `README.md`, `.editorconfig` and `.pre-commit-config.yaml`, driven by the contract's identity fields.
- A contract that produces a configured project from `fluid custom-scaffold`.

Realistic time end to end: **20-30 minutes**.

## The mental model

Same as the CI bundle, with more templates:

```text
your platform team's repo                      product team's repo (after generate)
┌──────────────────────────────────┐         ┌─────────────────────────────────┐
│ project-bundle/                   │         │ <product-dir>/                  │
│   ├── fluid-scaffold.yaml         │         │   ├── contract.fluid.yaml       │
│   ├── templates/                  │         │   ├── pyproject.toml            │
│   │   ├── pyproject.toml.j2       │         │   ├── src/<module>/__init__.py  │
│   │   ├── README.md.j2            │ ──→     │   ├── src/<module>/main.py      │
│   │   ├── init.py.j2              │         │   ├── tests/test_smoke.py       │
│   │   ├── main.py.j2              │         │   ├── tests/__init__.py         │
│   │   ├── test_smoke.py.j2        │         │   ├── Dockerfile                │
│   │   ├── Dockerfile.j2           │         │   ├── README.md                 │
│   │   ├── editorconfig.j2         │         │   ├── .editorconfig             │
│   │   └── pre-commit-config…j2    │         │   ├── .pre-commit-config.yaml   │
│   └── static/                     │         │   └── LICENSE                   │
│       └── LICENSE                 │         └─────────────────────────────────┘
└──────────────────────────────────┘
```

## Step 0: see the result first

A product team runs the following. The bundle here is bound with `kind: path` so the example runs offline; a team using the platform repo from the [CI journey](./your-own-ci.md#step-7-consume-from-a-product-team-s-repo) writes a `kind: git` source with a pinned `ref` instead.

```bash
mkdir -p ~/products/order-events && cd ~/products/order-events

cat > contract.fluid.yaml <<'EOF'
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.commerce.order_events_v1
name: Order Events
description: Real-time order event stream.
domain: commerce
metadata:
  layer: Bronze
  productType: SDP
  owner: { team: commerce, email: orders-team@my-org.example.com }
exposes:
  - exposeId: order_events
    kind: table
    binding:
      platform: local
      format: parquet
      location: { path: out/order_events.parquet }
    contract:
      schema:
        - { name: order_id, type: STRING, required: true }
extensions:
  customScaffold:
    libraries:
      - id: skel
        source: { kind: path, path: ../project-bundle }
    patterns:
      - use: skel:main
EOF

fluid custom-scaffold
```

Output (trimmed; the engine prints absolute paths):

```text
Resolved libraries:
  skel  (path)  version=local

✓ 10 files written, 0 failed (0.0047s)
  .../.editorconfig
  .../.pre-commit-config.yaml
  .../Dockerfile
  .../LICENSE
  .../README.md
  .../pyproject.toml
  .../src/bronze_commerce_order_events_v1/__init__.py
  .../src/bronze_commerce_order_events_v1/main.py
  .../tests/__init__.py
  .../tests/test_smoke.py
```

The module directory `src/bronze_commerce_order_events_v1/` comes from the contract's id (`bronze.commerce.order_events_v1`), with `-` and `.` turned into `_` by a Jinja filter chain. The destination path in the manifest is itself rendered against the contract, so one template path produces a different directory for each product.

After `pip install -e .`, `pytest` in the generated project runs the smoke test and passes (`1 passed`).

## Step 1: set up the bundle

Same as the CI bundle. Reuse [steps 1-2 from your-own-ci](./your-own-ci.md#step-1-set-up-the-bundle-repo): bundle directory, `fluid-scaffold.yaml` manifest. The `templates:` list now points at project-skeleton templates instead of CI templates.

```yaml
apiVersion: fluid.dev/custom-scaffold.v1

bundle:
  name: my-org-project-skeleton
  version: 1.0.0
  description: My Org's standard data-product project layout
  author: platform-team@my-org.example.com

patterns:
  - name: main
    description: Render the full project skeleton
    supportedProductTypes: [SDP, ADP, CDP]
    requiredContractFields:
      - id
      - metadata.owner.email
    templates:
      - from: templates/pyproject.toml.j2
        to: pyproject.toml
      - from: templates/README.md.j2
        to: README.md
      - from: templates/Dockerfile.j2
        to: Dockerfile
      - from: templates/editorconfig.j2
        to: .editorconfig
      - from: templates/pre-commit-config.yaml.j2
        to: .pre-commit-config.yaml

      # The destination path is itself Jinja-rendered. The module name is
      # the product id with '-' and '.' turned into '_'.
      - from: templates/init.py.j2
        to: "src/{{ product_id | replace('-', '_') | replace('.', '_') }}/__init__.py"
      - from: templates/main.py.j2
        to: "src/{{ product_id | replace('-', '_') | replace('.', '_') }}/main.py"
      - from: templates/test_smoke.py.j2
        to: tests/test_smoke.py
      - from: templates/tests_init.py.j2
        to: tests/__init__.py
```

The `to:` field is a Jinja template: `src/{{ product_id | replace('-', '_') | replace('.', '_') }}/__init__.py` means the destination varies with contract data. Quote a `to:` value that starts with `{{`, because YAML reads an unquoted leading `{` as a flow mapping.

::: tip Bundle enforcement (engine 0.4.0)
A pattern's `variables` JSON Schema (draft-07) is enforced at plan time, and `supportedProductTypes` is checked against the contract's `metadata.productType`. The pattern fields `when` and `environments` are reserved: the engine accepts them and does not evaluate them.
:::

## Step 2: the project skeleton templates

Drop these in `templates/`. The render-context names (`product_id`, `product_name`, `description`, `owner`, `domain`, `metadata`, `product_type`, `bundle`) are listed in [the CI journey](./your-own-ci.md#step-3-pick-your-ci-system).

::: details pyproject.toml.j2 - opinionated Python package config
```jinja
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{ product_id }}"
version = "0.1.0"
description = "{{ description }}"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
authors = [
    {name = "{{ owner.email }}"},
]
keywords = [
    "data-product",
    "{{ domain | default('unknown') }}",
    "{{ metadata.layer | default('Bronze') }}",
    "{{ product_type | default('SDP') }}",
]

dependencies = [
    "pydantic>=2.0",
    "data-product-forge==0.18.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "black>=24.10.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py310"
```
:::


::: details README.md.j2 - opinionated README structure
````jinja
# {{ product_name }}

> {{ description }}

**Owner:** {{ owner.email }}
**Domain:** {{ domain | default('-') }}
**Classification:** {{ metadata.layer }} ({{ product_type }})

## What this product is

Data product `{{ product_id }}`, generated from `{{ bundle.name }}@{{ bundle.version }}`.

## Local development

```bash
pip install -e ".[dev]"
pytest
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
```

## Regenerating

This project layout is generated. To pull in template updates, bump `ref`
in `contract.fluid.yaml` and re-run `fluid custom-scaffold`, then review
`git diff`.
````
:::


::: details Dockerfile.j2 - security-baseline image
```jinja
# Auto-generated for {{ product_id }} from {{ bundle.name }}@{{ bundle.version }}
# Edit the bundle, not this file.

FROM python:3.12-slim

# Security baseline
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --no-create-home --uid 1000 app

LABEL org.opencontainers.image.title="{{ product_id }}"
LABEL org.opencontainers.image.description="{{ description }}"
LABEL my-org.owner="{{ owner.email }}"
LABEL my-org.domain="{{ domain | default('unknown') }}"
LABEL my-org.classification="{{ metadata.layer }}"

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .
USER 1000:1000

ENTRYPOINT ["python", "-m", "{{ product_id | replace('-', '_') | replace('.', '_') }}.main"]
```
:::


Every container carries the labels your platform team expects, without copy-paste from team to team.

::: details main.py.j2 - minimal entry point
```jinja
"""Entry point for {{ product_name }}.

Auto-generated stub. Replace `main()` with your product's actual logic.
"""

from __future__ import annotations

import logging


logger = logging.getLogger("{{ product_id | replace('-', '_') | replace('.', '_') }}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("starting {{ product_id }}")
    logger.info("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
:::


::: details test_smoke.py.j2 - a test that runs in CI on day one
```jinja
"""Smoke test for {{ product_name }}."""

from __future__ import annotations

from {{ product_id | replace('-', '_') | replace('.', '_') }}.main import main


def test_main_returns_zero():
    """If this fails, the product won't start in any environment."""
    assert main() == 0
```
:::


::: details init.py.j2 + tests_init.py.j2 + editorconfig.j2 + pre-commit-config.yaml.j2
```jinja
{# templates/init.py.j2 #}
"""{{ product_name }}: {{ description }}"""

__version__ = "0.1.0"
```

`templates/tests_init.py.j2` is an empty file (the `tests/__init__.py` marker).

```jinja
{# templates/editorconfig.j2 #}
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[*.{yml,yaml,toml}]
indent_size = 2
```

```jinja
{# templates/pre-commit-config.yaml.j2 #}
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.12
```
:::

## Step 3: static files

Anything that does not need rendering goes in `static/`. The engine copies it verbatim and refuses symlinks.

```bash
mkdir -p static
cp /path/to/your/LICENSE static/LICENSE
```

## Step 4: tag, push, consume

Same as the CI bundle:

```bash
# bundle author
git add fluid-scaffold.yaml templates/ static/
git commit -m "v1.0.0: initial project skeleton"
git tag v1.0.0
git push --tags origin main
```

```yaml
# product-team contract.fluid.yaml
extensions:
  customScaffold:
    libraries:
      - id: skel
        source:
          kind: git
          url:  "https://github.com/my-org/project-bundle"
          ref:  "v1.0.0"
    patterns:
      - use: skel:main
```

```bash
# product-team workspace
fluid custom-scaffold
git add . && git commit -m "Initial project skeleton from project-bundle v1.0.0"
```

## Reproducible re-generation (engine 0.4.0)

The "bump the ref and re-run" loop is fine for a clean working tree. Once a product team has hand-edited generated files, a blind re-render overwrites their changes. Custom-scaffold engine `0.4.0` adds re-generation that preserves them:

- **Lockfile.** After a successful (non-dry-run) generation the engine writes a deterministic, credential-free `fluid-scaffold.lock` to the output root. For a git source it records the **resolved commit**; for a `path` source it records `commit: local`.
- **`--pin`.** `fluid custom-scaffold --pin` resolves git sources to the locked commit instead of following the contract's `ref`, for reproducible CI.
- **`--update [--target REF]`.** Re-renders at the locked base plus the new ref and 3-way-merges the result onto your working tree via `git merge-file`. On overlapping edits it writes conflict markers and exits `4`; on a clean merge the lock advances to the new ref. It requires a `fluid-scaffold.lock`.

```bash
# CI: reproduce what the lock pinned.
fluid custom-scaffold --pin

# Pull in the platform team's v1.1.0 bundle, merging over local edits.
fluid custom-scaffold --update --target v1.1.0
```

`--pin` and `--update` act on git sources, so the verification for this page covers the flags' presence in `fluid custom-scaffold --help` and not a merge run. The merge internals live in the [custom-scaffold engine repo](https://github.com/Agenticstiger/data-product-forge-custom-scaffold).

## You'll know it worked when

- `fluid custom-scaffold` writes the project skeleton: `pyproject.toml`, `README.md`, `Dockerfile`, `.editorconfig`, `.pre-commit-config.yaml`, `src/<module>/__init__.py`, `tests/test_smoke.py`.
- The module name in `src/` is the contract id with `-` and `.` replaced by `_`.
- `pytest` passes on the generated skeleton (the smoke test imports `main()` and asserts it returns 0).
- `pip install -e ".[dev]"` succeeds, so `pyproject.toml.j2` produced valid TOML.
- Adding a template to the bundle, bumping `v1.0.0` to `v1.1.0` and re-running against the new ref pulls in the new template.

## When **not** to use this pattern

- **If product code structure varies a lot across teams.** Bundle scaffolds work when teams agree on a layout. If team A is FastAPI, team B is Apache Beam and team C is dbt, give each their own bundle, or let each team own its layout.
- **If you are tempted to put logic in templates.** Jinja loops and conditionals are fine; calling web APIs at render time is not. The engine assumes deterministic rendering. For non-deterministic logic write a Python `CustomScaffold` plugin (the [`entrypoint` source kind](../examples/hello-scaffold.md)).
- **If you want product teams to edit the generated files freely and never merge template updates.** Generate once at project creation and do not re-run, or use `--update` so their edits are merged instead of overwritten. `fluid init --template` takes the name of a built-in template (for example `customer-360`), not a bundle, so it is not a substitute.

## Common gotchas

::: details The Jinja `to:` path doesn't render
The `to:` field is rendered through Jinja against the render context (`product_id`, `bundle`, and the other names in the CI journey's table). Quote the value when it starts with `{{`:

```yaml
# correct
- from: templates/init.py.j2
  to: "{{ product_id | replace('.', '_') }}/__init__.py"

# wrong: YAML parses a leading {{ as a flow mapping
- from: templates/init.py.j2
  to: {{ product_id | replace('.', '_') }}/__init__.py
```
:::

::: details The generated module won't import
The id is turned into a directory name by the filters in your manifest. With only `replace('-', '_')`, the id `bronze.commerce.order_events_v1` renders `src/bronze.commerce.order_events_v1/__init__.py` (output from `fluid custom-scaffold --dry-run`), and a directory name with dots is not an importable module. Chain `| replace('.', '_')` as the manifest above does. Leading digits are not handled by either filter.

A manifest guard catches ids that will not work, before anything renders:

```yaml
requiredContractFields:
  - id
```

That checks presence only. Enforce the id's shape with a [`Validator` plugin](./custom-validator.md) so it fails at `fluid validate`.
:::

::: details Re-generating overwrites my changes
A plain `fluid custom-scaffold` re-renders every file from the templates. Use `fluid custom-scaffold --update --target <ref>` to merge a new bundle version onto edited files, or generate once and stop re-running.
:::

## Next

- [Your own CI](./your-own-ci.md): a separate bundle for CI/CD; teams often ship both side by side
- [Custom validator](./custom-validator.md): for governance rules, runs at `fluid validate`
- [Apply hook](./apply-hook.md): for runtime invariants right before deploy
