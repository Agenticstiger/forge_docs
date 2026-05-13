# You have a strict project layout, no problem

Your org has opinions: every data product lives in a repo with a specific directory structure, a specific test framework, specific lint config, a Dockerfile that follows your security baseline, and a README following a specific template. New teams shouldn't have to copy-paste from older products — they should declare a contract and get the whole skeleton.

This guide extends the pattern from [you have your own CI](./your-own-ci.md) — same bundle shape, but the templates render the *full project skeleton*, not just CI. Read that one first if you haven't; the bundle mechanics (manifest, templates, static, git ref pinning) are the same.

By the end you'll have:

- A bundle that generates `pyproject.toml` / `src/<product>/` / `tests/` / `Dockerfile` / `README.md` / `.editorconfig` / `.pre-commit-config.yaml` — driven by `contract.metadata`.
- A contract that produces a fully-configured project from `fluid generate custom-scaffold`.

Realistic time end-to-end: **20–30 minutes**.

## The mental model

Same as the CI bundle, with more templates:

```text
your platform-team's git repo                  product team's repo (after generate)
┌──────────────────────────────────┐         ┌─────────────────────────────────┐
│ project-bundle/                   │         │ <product-id>/                   │
│   ├── fluid-scaffold.yaml         │         │   ├── contract.fluid.yaml       │
│   ├── templates/                  │         │   ├── pyproject.toml            │
│   │   ├── pyproject.toml.j2       │         │   ├── src/<id>/__init__.py     │
│   │   ├── README.md.j2            │ ──→     │   ├── src/<id>/main.py         │
│   │   ├── src/__init__.py.j2      │         │   ├── tests/test_smoke.py      │
│   │   ├── src/main.py.j2          │         │   ├── tests/__init__.py        │
│   │   ├── tests/test_smoke.py.j2  │         │   ├── Dockerfile               │
│   │   ├── Dockerfile.j2           │         │   ├── README.md                │
│   │   ├── .editorconfig.j2        │         │   ├── .editorconfig            │
│   │   └── .pre-commit-config.j2   │         │   └── .pre-commit-config.yaml  │
│   └── static/                     │         └─────────────────────────────────┘
│       └── LICENSE                 │
└──────────────────────────────────┘
```

## Step 0 — see the result first

A product team runs:

```bash
mkdir -p ~/products/order-events && cd $_

cat > contract.fluid.yaml <<'EOF'
fluidVersion: "0.7.3"
metadata:
  id: order-events
  name: Order Events
  description: Realtime order event stream.
  owner: { email: orders-team@example.com }
  domain: commerce
  layer: Bronze
  productType: SDP
environments:
  dev:
    cloud: { provider: aws, account: "111111111111", region: us-east-1 }
extensions:
  customScaffold:
    libraries:
      - id: skel
        source: { kind: git, url: "https://github.com/my-org/project-bundle", ref: "v1.0.0" }
    patterns:
      - use: skel:main
EOF

fluid generate custom-scaffold
```

Output:

```text
✓ 9 files written, 0 failed
  pyproject.toml
  README.md
  Dockerfile
  .editorconfig
  .pre-commit-config.yaml
  src/order_events/__init__.py
  src/order_events/main.py
  tests/test_smoke.py
  tests/__init__.py
  LICENSE                          (from static/)
```

`src/order_events/` — the `metadata.id` (`order-events`) was kebab-cased into a Python-legal module name (`order_events`). That's how a single Jinja path `src/__init__.py.j2` produces `src/order_events/__init__.py` — the destination path itself is rendered against the contract too.

## Step 1 — set up the bundle

Same as the CI bundle. Reuse [steps 1–2 from your-own-ci](./your-own-ci.md#step-1-set-up-the-bundle-repo) — bundle directory, `fluid-scaffold.yaml` manifest, etc. The only difference is the `templates:` list in the manifest now points at project-skeleton templates instead of CI templates.

```yaml
# fluid-scaffold.yaml
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
      - metadata.id
      - metadata.owner.email
      - environments
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

      # The destination path is itself Jinja-rendered — the module name
      # comes from contract.metadata.id (kebab-cased to snake_case below).
      - from: templates/init.py.j2
        to: "src/{{ contract.metadata.id | replace('-', '_') }}/__init__.py"
      - from: templates/main.py.j2
        to: "src/{{ contract.metadata.id | replace('-', '_') }}/main.py"
      - from: templates/test_smoke.py.j2
        to: tests/test_smoke.py
      - from: templates/tests_init.py.j2
        to: tests/__init__.py
```

The `to:` field is itself a Jinja template — `src/{{ contract.metadata.id | replace('-', '_') }}/__init__.py` means the destination path varies based on contract data. Anywhere the contract has a value, you can put it in the path.

## Step 2 — the project skeleton templates

Drop these in `templates/`. Most are short.


::: details pyproject.toml.j2 — opinionated Python package config
```jinja
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{ contract.metadata.id }}"
version = "0.1.0"
description = "{{ contract.metadata.description }}"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
authors = [
    {name = "{{ contract.metadata.owner.email }}"},
]
keywords = [
    "data-product",
    "{{ contract.metadata.domain | default('commerce') }}",
    "{{ contract.metadata.layer | default('Bronze') }}",
    "{{ contract.metadata.productType | default('SDP') }}",
]

dependencies = [
    "pydantic>=2.0",
    "data-product-forge=={{ fluid_cli_version | default('0.8.3') }}",
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



::: details README.md.j2 — opinionated README structure
```jinja
# {{ contract.metadata.name }}

> {{ contract.metadata.description }}

**Owner:** {{ contract.metadata.owner.email }}
**Domain:** {{ contract.metadata.domain | default('—') }}
**Classification:** {{ contract.metadata.layer }} ({{ contract.metadata.productType }})

## What this product is

Data product `{{ contract.metadata.id }}`, generated from [`my-org-project-skeleton@{{ bundle.version }}`](https://github.com/my-org/project-bundle/releases/tag/v{{ bundle.version }}).

## Environments

{% for env_name, env in contract.environments.items() %}
- **{{ env_name }}** — `{{ env.cloud.provider }}`{% if env.cloud.region %} in `{{ env.cloud.region }}`{% endif %}
{% endfor %}

## Local development

```bash
pip install -e ".[dev]"
pytest
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --env dev --dry-run
```

## Deploy

CI is generated from `my-org-ci-bundle` (separate bundle). Push to `main` triggers the deploy pipeline.

## Regenerating

This entire project layout is generated. To pull in template updates:

```bash
# bump ref in contract.fluid.yaml: skel.source.ref: v1.0.0 → v1.1.0
fluid generate custom-scaffold
git diff      # review the platform team's changes
```
```
:::



::: details Dockerfile.j2 — security-baseline image
```jinja
# Auto-generated for {{ contract.metadata.id }} from project-bundle v{{ bundle.version }}
# Edit the bundle, not this file.

FROM python:3.12-slim

# Security baseline
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --no-create-home --uid 1000 app

LABEL org.opencontainers.image.title="{{ contract.metadata.id }}"
LABEL org.opencontainers.image.description="{{ contract.metadata.description }}"
LABEL my-org.owner="{{ contract.metadata.owner.email }}"
LABEL my-org.domain="{{ contract.metadata.domain | default('unknown') }}"
LABEL my-org.classification="{{ contract.metadata.layer }}"

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .
USER 1000:1000

ENTRYPOINT ["python", "-m", "{{ contract.metadata.id | replace('-', '_') }}.main"]
```

Every container ships with the labels your platform team expects, no copy-paste from team to team.
:::



::: details main.py.j2 — minimal-but-real entry point
```jinja
"""Entry point for {{ contract.metadata.name }}.

Auto-generated stub — replace `main()` with your product's actual logic.
"""

from __future__ import annotations

import logging


logger = logging.getLogger("{{ contract.metadata.id | replace('-', '_') }}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("starting {{ contract.metadata.id }}")
    # TODO: implement your product's logic
    logger.info("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
:::



::: details test_smoke.py.j2 — a real test that runs in CI on day one
```jinja
"""Smoke test for {{ contract.metadata.name }}."""

from __future__ import annotations

from {{ contract.metadata.id | replace('-', '_') }}.main import main


def test_main_returns_zero():
    """If this fails, the product won't start in any environment."""
    assert main() == 0
```
:::



::: details init.py.j2 + tests_init.py.j2 + editorconfig.j2 + pre-commit-config.yaml.j2
```jinja
{# templates/init.py.j2 — module __init__.py #}
"""{{ contract.metadata.name }} — {{ contract.metadata.description }}."""

__version__ = "0.1.0"
```

```jinja
{# templates/tests_init.py.j2 — tests __init__.py, just a marker #}
```

```jinja
{# templates/editorconfig.j2 — your-org's editor config #}
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
{# templates/pre-commit-config.yaml.j2 — your-org's pre-commit hooks #}
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

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
```
:::


## Step 3 — static files

Anything that doesn't need rendering goes in `static/`. The custom-scaffold engine copies it verbatim. Symlinks are refused.

```bash
mkdir -p static
cat > static/LICENSE <<'EOF'
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

# ... full Apache 2.0 text ...
EOF
```

## Step 4 — tag, push, consume

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
fluid generate custom-scaffold
git add . && git commit -m "Initial project skeleton from project-bundle v1.0.0"
```

## You'll know it worked when

- `fluid generate custom-scaffold` writes the full project skeleton — pyproject.toml, README.md, Dockerfile, .editorconfig, .pre-commit-config.yaml, plus `src/<product_id>/__init__.py` and `tests/test_smoke.py`.
- The Python module name in `src/` matches the kebab-case `metadata.id` with dashes replaced by underscores (`order-events` → `order_events`).
- `pytest` passes immediately on the generated skeleton (the smoke test imports `main()` and asserts it returns 0).
- `pip install -e ".[dev]"` succeeds — your `pyproject.toml.j2` produced a valid TOML.
- Adding a new template to the bundle and bumping `v1.0.0` → `v1.1.0` → re-running `fluid generate` against the new ref pulls in the new template.

## When **not** to use this pattern

- **If product code structure varies a lot across teams.** Bundle scaffolds work when teams agree on a layout. If team A is FastAPI and team B is Apache Beam and team C is dbt — give each their own bundle. Or accept that each team owns their layout.
- **If you're tempted to put logic in templates.** Jinja loops and conditionals are fine; calling out to web APIs at render time is not. The custom-scaffold engine assumes deterministic rendering. If you need non-deterministic logic, write a Python `CustomScaffold` plugin instead (use the [`entrypoint` resolver kind](../examples/hello-scaffold.md)).
- **If you want product teams to edit the generated files freely.** This pattern works because re-generation is safe — files come from your templates, contract drives content. If product teams hand-edit the generated files, regeneration will fight them. For that case, generate once at project creation and never re-generate — use `fluid init --template <bundle>` (not custom-scaffold) for one-shot scaffolding.

## Common gotchas

::: details The Jinja `to:` path doesn't render
The `to:` field is rendered through Jinja against `contract` (and `bundle`). Your Jinja in the path must be valid Jinja with proper quoting:

```yaml
# correct — quoted, paths use forward slashes
- from: templates/init.py.j2
  to: "src/{{ contract.metadata.id | replace('-', '_') }}/__init__.py"

# wrong — YAML interprets the colon as a key separator
- from: templates/init.py.j2
  to: src/{{ contract.metadata.id }}/__init__.py
```
:::

::: details The generated module won't import
Most common cause: `metadata.id` has characters Python doesn't accept in a module name. The kebab-to-snake conversion (`'-' | replace`) catches the common case but doesn't handle leading digits, dots, etc.

A defensive bundle adds a `requiredContractFields:` pattern guard:

```yaml
requiredContractFields:
  - metadata.id
  # Additionally validated in CI:
  # ^[a-z][a-z0-9_-]+$  — bundle-level Validator plugin enforces this
```
:::

::: details Re-generating overwrites my changes
This is working as designed — bundle output is deterministic. If product teams need editable seed code (not regenerated), use `fluid init --template <bundle>` for one-shot creation instead of the custom-scaffold pattern. The `--template` route copies files once; `custom-scaffold` is the always-up-to-date mode.
:::

## Next

- [Your own CI](./your-own-ci.md) — separate bundle for CI/CD; common to ship both side-by-side
- [Custom validator](./custom-validator.md) — for governance rules, runs at `fluid validate`
- [Apply hook](./apply-hook.md) — for runtime invariants right before deploy
