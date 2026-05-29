# SDK & Plugins

`data-product-forge` already does the boring parts — `validate`, `plan`, `apply`, `publish`. This section is for everything else: when your team needs the CLI to do something specific to **your** organization.

> Your CI templates aren't the ones forge ships? Plug your own in.
> Your team's project layout is opinionated? Generate it from a contract.
> You have governance rules nobody else has? Run them at validate time.
> You want a safety check right before deploy? Add an apply hook.

You don't fork the CLI. You write a small Python package, register one entry-point, `pip install` it, and forge picks it up.

> **Quick:** [Quickstart](./quickstart.md) · [Examples](./examples/) · [Your own CI](./journeys/your-own-ci.md) · [Your own scaffolding](./journeys/your-own-scaffolding.md) · [Custom validator](./journeys/custom-validator.md) · [Apply hook](./journeys/apply-hook.md) · [Roles](./reference/roles.md) · [Entry points](./reference/entry-points.md) · [Trust model](./reference/trust-model.md) · [Packaging](./reference/packaging.md) · [Companion packages](./reference/companion-packages.md)

## What you'll be building

A plugin is a normal Python package — `pyproject.toml`, `src/`, `tests/` — with **one extra line** telling pip "here's a thing forge can discover":

```toml
[project.entry-points."fluid_build.custom_scaffolds"]
my-scaffold = "my_pkg.scaffold:MyScaffold"
```

After `pip install`, the CLI sees your plugin automatically. No registration step. No config file. No fork of `data-product-forge`.

End-to-end it looks like this:

```text
your-package
└── src/my_pkg/scaffold.py   ─┐
                              │   subclass an SDK role:
                              ▼   CustomScaffold / Validator / InfraProvider / CatalogAdapter
   ┌──────────────────────────────┐
   │ class MyScaffold(...):       │
   │     def plan(self, contract):│
   │         return [...]          │
   └──────────────────────────────┘
                              │   pyproject.toml entry-point
                              ▼
         pip install your-package
                              │
                              ▼
   ┌──────────────────────────────┐
   │   data-product-forge (CLI)   │ ──▶ discovers your plugin
   │   fluid validate / apply /   │
   │   generate / publish         │
   └──────────────────────────────┘
```

That's the whole mental model. The rest of this page is "which role do I subclass" and "which entry-point group do I use" — both small decisions.

## A complete, runnable example, top to bottom

This is everything. Paste it into a fresh directory and run.

```python
# src/hello_scaffold/scaffold.py
from fluid_sdk import ContractHelper, CustomScaffold, write_file_action


class HelloScaffold(CustomScaffold):
    name = "hello"

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            write_file_action(
                path="README.md",
                content=f"# {c.name}\n\n{c.description}\n".encode("utf-8"),
            ).to_dict(),
        ]
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hello-scaffold"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.entry-points."fluid_build.custom_scaffolds"]
hello = "hello_scaffold.scaffold:HelloScaffold"

[tool.setuptools.packages.find]
where = ["src"]
```

```bash
# Install everything you need
pip install data-product-forge data-product-forge-custom-scaffold
pip install -e .

# In any fluid project's contract.fluid.yaml:
#   extensions:
#     customScaffold:
#       libraries: [{id: hi, source: {kind: entrypoint, name: hello}}]
#       patterns: [{use: hi:main}]

fluid generate custom-scaffold
# ✓ 1 file written, 0 failed
#   README.md
```

That's it. ~15 lines of Python, two TOML stanzas, one CLI command. Read the [quickstart](./quickstart.md) for the same thing with each step explained, plus what to check when something doesn't work.

## Which role do I subclass?

Four roles, one mental model. Each role is a thin subclass of `BasePlugin` that pins a `role` tag and provides role-shaped helpers. Pick the one that matches **what you're producing**:

| You want to… | Role | Hook it into | Example |
|---|---|---|---|
| Generate files from a contract (CI configs, app code, IaC stacks, docs) | **`CustomScaffold`** | `fluid generate custom-scaffold` | [hello-scaffold](./examples/hello-scaffold.md), [gitlab-ci-scaffold](./examples/gitlab-ci-scaffold.md) |
| Enforce governance / compliance / cost rules at author-time | **`Validator`** | `fluid validate` | [steward-validator](./examples/steward-validator.md) |
| Add support for a new cloud platform or data warehouse | **`InfraProvider`** | `fluid apply` | — |
| Sync product metadata into your catalog (DataHub, Atlan, Collibra…) | **`CatalogAdapter`** | `fluid publish` | — |

Class signatures and inherited methods: [Roles reference](./reference/roles.md).

## Pick the journey that matches your problem

Each guide opens with the real problem you might have, then walks you to a working plugin end-to-end:

| You have… | Read | What you build |
|---|---|---|
| Your own CI/CD templates | [your-own-ci](./journeys/your-own-ci.md) | A scaffold bundle that emits your CI files from contract data (GitLab / GitHub Actions / Jenkins variants) |
| A strict project layout | [your-own-scaffolding](./journeys/your-own-scaffolding.md) | A scaffold for the whole project skeleton (README, tests, Dockerfile, app source) |
| Governance rules | [custom-validator](./journeys/custom-validator.md) | A `Validator` plugin (e.g. "every Gold product MUST declare a data steward") |
| A safety check that must run at apply | [apply-hook](./journeys/apply-hook.md) | An apply hook that aborts deploy when an invariant is violated (with override flag) |

## What's on PyPI today

| Package | Version | What it does | Install |
|---|---|---|---|
| [`data-product-forge`](https://pypi.org/project/data-product-forge/) | 0.8.6 | The CLI (this docs set) | `pip install data-product-forge` |
| [`data-product-forge-sdk`](https://pypi.org/project/data-product-forge-sdk/) | 0.9.0 | Plugin SDK — zero-dependency ABCs + conformance harness | `pip install data-product-forge-sdk` (import: `from fluid_sdk import …`) |
| [`data-product-forge-custom-scaffold`](https://pypi.org/project/data-product-forge-custom-scaffold/) | 0.1.0 | Reference custom-scaffold engine (Jinja+YAML or Python plugins) | `pip install data-product-forge-custom-scaffold` |

The SDK and scaffold ship as version-pinned standalone packages. A first stable cut (`1.0.0` / `0.2.0`) is planned after a validation window — feel free to consume them today, just pin the upper bound. See [Companion Packages](./reference/companion-packages.md) for the dual-naming details (PyPI: `data-product-forge-sdk`, import path: `fluid_sdk`).

## What about security?

Plugins are uncontained Python loaded into the CLI process. **Trust in a plugin = trust in whatever pip resolved when you installed it.** The CLI does not sandbox plugin code, time-limit it, or restrict what it can do.

What the CLI *does* defend against, automatically:

- **Crash containment** — a plugin that raises an exception cannot crash the CLI.
- **Contract mutation** — apply hooks get a `copy.deepcopy()` of the contract, not the live reference.
- **Credential leak in error messages** — plugin exception text is scrubbed before reaching logs.

Full statement: [Trust model](./reference/trust-model.md). Read it before installing community plugins.

## Reference

- **[Roles](./reference/roles.md)** — what each role gives you, what you override
- **[Entry points](./reference/entry-points.md)** — the entry-point groups (3 CLI hooks + 4 role-level) with signatures and failure model
- **[Trust model](./reference/trust-model.md)** — what we defend against, what we don't
- **[Packaging](./reference/packaging.md)** — `pyproject.toml` template, `py.typed`, conformance harness, publishing checklist
- **[Companion packages](./reference/companion-packages.md)** — what's on PyPI, dual-naming, version pinning

## Source repos

- **SDK:** [`Agenticstiger/forge-cli-sdk`](https://github.com/Agenticstiger/forge-cli-sdk) — also contains three runnable example plugins under `examples/`.
- **Custom-scaffold engine:** [`Agenticstiger/data-product-forge-custom-scaffold`](https://github.com/Agenticstiger/data-product-forge-custom-scaffold) — reference bundle in `tests/fixtures/reference_bundle/`.

The example walkthroughs on these pages mirror the upstream `examples/` directories — they're the truth source.
