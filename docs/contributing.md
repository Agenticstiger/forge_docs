# Contributing to Fluid Forge

We welcome contributions of all kinds — bug reports, feature ideas, docs improvements, and code.

## Ways to Contribute

### Report a Bug

Open an issue at [github.com/Agenticstiger/forge-cli/issues](https://github.com/Agenticstiger/forge-cli/issues) with:

- **What happened** vs. **what you expected**
- The command you ran and its output
- `fluid version` and `fluid doctor` output
- Your contract file (redact sensitive values)

### Suggest a Feature

Start a [GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions) or open an issue tagged `enhancement`.

### Improve Documentation

The docs live in `docs/` and are built with VuePress. To preview locally:

```bash
cd forge_docs
npm ci
npm run docs:dev
```

Edit any `.md` file, save, and your browser refreshes automatically.

### Submit a Docs Pull Request

```bash
# 1. Fork & clone the docs repo
git clone https://github.com/<your-username>/forge_docs.git
cd forge_docs

# 2. Install dependencies
npm ci

# 3. Create a branch
git checkout -b docs/my-improvement

# 4. Preview or build locally
npm run docs:dev
npm run docs:build

# 5. Commit with conventional format
git commit -m "docs: update provider guide"

# 6. Push & open a PR
git push origin docs/my-improvement
```

If your docs change is the companion to a CLI change, link the related `forge-cli` PR in your docs PR description. We keep that link optional here because many docs updates are docs-only improvements.

### What we look for in docs PRs

- The page is accurate and easy to follow, and every example output is real output from the pinned CLI (trim with `...`), not written by hand.
- Links still work
- Navigation and headings still make sense
- The pages and headings the CLI links to are untouched (see [Pages the CLI links to](#pages-the-cli-links-to))
- These pass locally, with the pinned CLI on your `PATH`:

```bash
npm run docs:build
node scripts/check-dist-links.mjs
python scripts/check_cli_docs.py
python scripts/check_providers.py
```

### Keeping the docs in sync with the CLI

[`docs/.vuepress/cli-version.json`](https://github.com/Agenticstiger/forge_docs/blob/main/docs/.vuepress/cli-version.json) pins the CLI version the docs track. The [`cli-consistency`](https://github.com/Agenticstiger/forge_docs/actions/workflows/cli-consistency.yml) GitHub Actions workflow installs that exact version of `data-product-forge` from PyPI on every PR and runs `scripts/check_cli_docs.py` and `scripts/check_providers.py`. Together they verify:

1. `fluid --version` matches the pinned `supportedCliVersion`.
2. Every subcommand registered by the CLI's argparse parser has a matching `docs/cli/<name>.md` page, and every page in `docs/cli/` corresponds to a real command, unless it sits in `scripts/cli-docs-allowlist.yml` with a comment explaining why.
3. `fluid init --quickstart` emits the `fluidVersion` pinned as `quickstartScaffoldVersion`.
4. The contract versions pinned in `cli-version.json` exist in the pinned CLI's bundled schema set.
5. **Flag oracle:** each `fluid ...` invocation inside a fenced code block under `docs/` uses subcommands and flags the pinned CLI registers. The oracle reads the parser, so it proves a flag exists, not that a command's output is what the page shows. Run the commands you document.
6. **Version sweep:** no page names an older CLI or contract version as the current baseline. A line that mentions an older release on purpose carries `<!-- cli-version: historical -->` (on the line, or on its own line before a fenced block). The header of `scripts/check_cli_docs.py` explains the three scopes.
7. Every provider returned by `fluid providers --json` has a matching `docs/providers/<name>.md` page.

The oracle runs against the core CLI. A command that a companion package registers, such as `fluid custom-scaffold` from `data-product-forge-custom-scaffold`, is unknown to it, so pages that document such a command need an entry in the `flag_oracle_ok` section of `scripts/cli-docs-allowlist.yml`, scoped to that one invocation.

When a new CLI version ships:

```bash
# 1. Bump the pin
$EDITOR docs/.vuepress/cli-version.json

# 2. Install locally and run the consistency checks
pip install --upgrade "data-product-forge==$(jq -r .supportedCliVersion docs/.vuepress/cli-version.json)"
python scripts/check_cli_docs.py
python scripts/check_providers.py

# 3. The scripts will list any newly-added commands or providers — write the
#    matching docs page (or, if the command should stay hidden, add it to
#    scripts/cli-docs-allowlist.yml with a one-line reason).
```

Existing pages follow the layout in [`docs/cli/init.md`](https://github.com/Agenticstiger/forge_docs/blob/main/docs/cli/init.md) — a one-line summary, `## Syntax`, `## Key options`, `## Examples`, `## Notes`. Match that shape for new pages so the reference reads consistently.

### Pages the CLI links to

The CLI prints documentation links in its own output: the error messages, `--help` text, `fluid doctor` and the comments `fluid init` writes. Those links are a contract between this site and installed copies of the CLI, and a copy installed last month keeps printing the URL it was built with. No CI step checks them today: `scripts/check-dist-links.mjs` verifies that a page exists but states that fragment and anchor targets are not verified, and `scripts/check_cli_docs.py` does not read the CLI's link list.

Do not move or rename these pages, and do not change the text of a heading that produces one of these anchors. As of CLI 0.18.1 the links come from the literal URLs in `fluid_build` and from the route map in `fluid_build/_errors.py` (`_DOC_ROUTES` and `_DOC_FALLBACK`).

Pages:

- `getting-started/`
- `cli/`: `providers`, `secrets`, `verify-signature`, `apply`, `validate`, `contract`, `contract-validation`, `split`, `import`, `init`, `doctor`, `agents`, `market`
- `concepts/`: `sovereignty`, `contract`, `quality-sla-lineage`, `agent-policy`
- `advanced/`: `capability-warnings`, `cost-tracking`, `typed-cli-errors`, `production-troubleshooting` (the fallback for an error with no mapped topic), `airflow`, `forge-copilot-memory`
- `providers/gcp`
- `recipes/add-a-quality-rule`

Anchors on `advanced/typed-cli-errors`: `#validation-schema`, `#capability-negotiation`, `#connectivity-secrets`, `#pipeline-operations` and `#governance`.

To re-derive the list for a new CLI version, install it and run this from a clone of `forge-cli`:

```bash
git grep -ohE 'agenticstiger\.github\.io/forge_docs[^" )\\]*' -- fluid_build | sort -u
python -c "import fluid_build._errors as e; print(e._DOC_ROUTES, e._DOC_FALLBACK)"
```

The first command finds literal URLs; the second prints the routes that are composed at run time and never appear as URLs in the source.

### Build a Custom Provider

Fluid Forge is designed to be extended. See the [Custom Providers Guide](/forge_docs/providers/custom-providers) for the walkthrough and [SDK & Plugins → Roles](/forge_docs/sdk-and-plugins/reference/roles.html#infraprovider) for the role-typed class. A provider package built on `data-product-forge-sdk` looks like this:

```python
from fluid_sdk import ContractHelper, ExecutionResult, InfraProvider, provision_action


class MyProvider(InfraProvider):
    name = "my-cloud"

    def plan(self, contract):
        c = ContractHelper(contract)
        return [
            provision_action(
                op="create_table",
                resource_type="table",
                resource_id=c.id or "demo",
            ).to_dict()
        ]

    def apply(self, actions):
        return ExecutionResult(
            plugin=self.name,
            applied=len(actions),
            failed=0,
            results=[{"status": "ok", "op": action["op"]} for action in actions],
        )
```

Register it with `[project.entry-points."fluid_build.providers"]` and `my-cloud = "my_cloud.provider:MyProvider"`. After `pip install -e .`, `fluid plugins list --role provider` shows `my-cloud` and `fluid providers` lists it as `my_cloud`.

### Contribute a Forge Tool (`@forge_tool`)

Tools are what the multi-turn copilot agent calls during a run
(`discover_workspace`, `read_sample_schema`, `propose_contract`, …).
The new `@forge_tool` decorator collapses tool registration to a
single declaration where the Pydantic args-model is the source of
truth and JSON Schema is derived from it:

```python
from pydantic import BaseModel, Field
from fluid_build.cli.forge_tool import forge_tool

class FetchOrdersArgs(BaseModel):
    since: str = Field(description="ISO-8601 lower bound, e.g. 2024-01-01")
    limit: int = Field(default=100, ge=1, le=1000)

@forge_tool(
    name="fetch_orders",
    description="Page through the orders table since a given date.",
    args_schema=FetchOrdersArgs,
    workspace_root_aware=True,  # security: workspace_root is dispatcher-injected
)
def fetch_orders(args: FetchOrdersArgs, *, workspace_root):
    return _fetch_impl(workspace_root, args.since, args.limit)
```

The decorator handles registration in `FORGE_TOOL_REGISTRY`,
JSON Schema generation, args-model validation, `workspace_root`
injection (security boundary — the LLM cannot supply this field), and
the typed-error return shape that `dispatch_tool_call` consumes. See
the [Authoring Forge Tools guide](/forge_docs/advanced/forge-tools)
for the migration path from the legacy `_register` pattern, the S-013
exception-text scrubbing invariant, and the testing checklist.

## Add a Catalog Adapter

Catalog adapters are the **source-side** complement to providers: they pull metadata FROM an existing catalog (Snowflake Horizon, Databricks Unity, BigQuery, Glue, DataHub, Data Mesh Manager) and feed it into the staged forge pipeline. Each adapter follows the reusable patterns in `fluid_build/copilot/catalog/_patterns.py`.

The walkthrough lives in the forge-cli repo at [`CONTRIBUTING.md` → "Adding a Catalog Adapter"](https://github.com/Agenticstiger/forge-cli/blob/main/CONTRIBUTING.md#adding-a-catalog-adapter).

The path covers:

1. Subclass `CatalogAdapter`.
2. Honour the patterns in `_patterns.py`: soft-fail on optional reads, lazy SDK import, per-call client lifecycle, error translation with next-action suggestions, and the rest.
3. Add a typed `*Credentials` Pydantic class with `SecretStr` fields.
4. Register the optional install extra in `pyproject.toml`.
5. Wire the dispatch: `cli/forge_data_model.py` for `--source-type`, and the `_SOURCE_ADAPTERS` map in `cli/mcp/dispatch.py` for the MCP `forge_from_source` tool.
6. Write the test file; copy the closest existing adapter's test and edit it.
7. Pin the public API in `tests/test_public_api_stability.py`.
8. Document the new catalog at `docs/cli/catalogs/<name>.md` in this repo.

The existing adapters
([snowflake](cli/catalogs/snowflake.md),
[unity](cli/catalogs/unity.md),
[bigquery](cli/catalogs/bigquery.md),
[dataplex](cli/catalogs/dataplex.md),
[glue](cli/catalogs/glue.md),
[datahub](cli/catalogs/datahub.md),
[datamesh-manager](cli/catalogs/datamesh-manager.md)) are working
templates. Read one front to back before starting.

## Docs Standards

A few things that help reviewers focus on what matters in your change:

- **Examples first** — show what to run and what the reader will see, then explain. Keep tutorial, how-to, reference and explanation separate on a page.
- **Real output** — run every command you document against the pinned CLI and paste trimmed real output. Where the CLI misbehaves, write what it does ("As of 0.18.1, ...") instead of what it should do.
- **No unverifiable generalisations** — a sentence with "every", "all", "never" or a count about the product or the docs needs a check that re-derives it today. Delete the sentence otherwise.
- **Build cleanly** — `npm run docs:build` catches issues early so reviewers can focus on content.
- **Links that work** — use relative links to `.md` files for pages in this repo (`[apply](cli/apply.md)`), and current repo URLs for everything else, so nothing 404s a month from now.
- **Conventional Commits** — `feat:` / `fix:` / `docs:` / `chore:` ([reference](https://www.conventionalcommits.org/)); helps changelog automation pick up your work.

## Code of Conduct

Be respectful, constructive, and inclusive. See [CODE_OF_CONDUCT.md](https://github.com/Agenticstiger/forge-cli/blob/main/CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your work will be licensed under [Apache 2.0](https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE).

---

<p style="text-align: center; opacity: 0.7; font-size: 0.9rem;">Copyright 2025-2026 <a href="https://fluidhq.io">Agentics Transformation Limited</a> · Open source under <a href="https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE">Apache 2.0</a></p>
