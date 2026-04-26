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

- The page is accurate and easy to follow
- Links still work
- Navigation and headings still make sense
- `npm run docs:build` passes locally
- `python scripts/check_cli_docs.py` and `python scripts/check_providers.py` pass against the pinned CLI

### Keeping the docs in sync with the CLI

Every CLI release bumps the supported version in [`docs/.vuepress/cli-version.json`](https://github.com/Agenticstiger/forge_docs/blob/main/docs/.vuepress/cli-version.json). The [`cli-consistency`](https://github.com/Agenticstiger/forge_docs/actions/workflows/cli-consistency.yml) GitHub Actions workflow installs that exact version of `data-product-forge` from PyPI on every PR and verifies:

1. `fluid --version` matches the pinned `supportedCliVersion`.
2. Every subcommand listed by `fluid --help` has a matching `docs/cli/<name>.md` page.
3. Every page in `docs/cli/` corresponds to a real CLI command (or sits in `scripts/cli-docs-allowlist.yml` with a comment explaining why).
4. Every provider returned by `fluid providers --json` has a matching `docs/providers/<name>.md` page.

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

### Build a Custom Provider

Fluid Forge is designed to be extended. See the [Custom Providers Guide](/forge_docs/providers/custom-providers) for the full walkthrough, but the gist is:

```python
from fluid_provider_sdk import ApplyResult, BaseProvider, ProviderError

class MyProvider(BaseProvider):
    name = "my-cloud"

    def plan(self, contract):
        return [{"op": "create_table", "resource_id": "demo"}]

    def apply(self, actions):
        if not actions:
            raise ProviderError("No actions to apply")
        return ApplyResult(
            provider=self.name,
            applied=len(actions),
            failed=0,
            duration_sec=0.0,
            timestamp="",
            results=[{"status": "ok", "op": action["op"]} for action in actions],
        )
```

## Add a Catalog Adapter

Catalog adapters are the **source-side** complement to providers:
they pull metadata FROM an existing catalog (Snowflake Horizon,
Databricks Unity, BigQuery, Glue, DataHub, Data Mesh Manager) and
feed it into the staged forge pipeline. Each adapter is roughly
200 LOC and follows nine reusable patterns.

A community contributor with a weekend can ship a new one. The
walkthrough lives in the forge-cli repo at
[`CONTRIBUTING.md` → "Adding a Catalog Adapter"](https://github.com/Agenticstiger/forge-cli/blob/main/CONTRIBUTING.md#adding-a-catalog-adapter).

The path covers:

1. Subclass `CatalogAdapter` (4 abstract methods).
2. Honour the nine patterns in `_patterns.py` — soft-fail on
   optional reads, lazy SDK import, per-call client lifecycle,
   error translation with next-action suggestions, etc.
3. Add a typed `*Credentials` Pydantic class with `SecretStr`
   fields.
4. Register the optional install extra in `pyproject.toml`.
5. Wire the dispatch in `cli/forge_data_model.py` and `cli/mcp.py`.
6. Write the test file (templates: every existing adapter ships
   with one — copy the closest fit and edit).
7. Pin the public API in `tests/test_public_api_stability.py`.
8. Document the new catalog at
   `forge_docs/docs/cli/catalogs/<name>.md`.

The seven existing adapters
([snowflake](cli/catalogs/snowflake.md),
[unity](cli/catalogs/unity.md),
[bigquery](cli/catalogs/bigquery.md),
[dataplex](cli/catalogs/dataplex.md),
[glue](cli/catalogs/glue.md),
[datahub](cli/catalogs/datahub.md),
[datamesh-manager](cli/catalogs/datamesh-manager.md)) are working
templates — read one front-to-back before starting.

## Docs Standards

A few things that help reviewers focus on what matters in your change:

- **Clarity first** — practical examples and direct language help readers learn fast.
- **Build cleanly** — `npm run docs:build` catches issues early so reviewers can focus on content.
- **Links that work** — point at the published docs site and current repo URLs so nothing 404s a month from now.
- **Conventional Commits** — `feat:` / `fix:` / `docs:` / `chore:` ([reference](https://www.conventionalcommits.org/)); helps changelog automation pick up your work.

## Code of Conduct

Be respectful, constructive, and inclusive. See [CODE_OF_CONDUCT.md](https://github.com/Agenticstiger/forge-cli/blob/main/CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your work will be licensed under [Apache 2.0](https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE).

---

<p style="text-align: center; opacity: 0.7; font-size: 0.9rem;">Copyright 2025-2026 <a href="https://fluidhq.io">Agentics Transformation Pty Ltd</a> · Open source under <a href="https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE">Apache 2.0</a></p>
