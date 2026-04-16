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

### Build a Custom Provider

Fluid Forge is designed to be extended. See the [Custom Providers Guide](/providers/custom-providers) for the full walkthrough, but the gist is:

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

## Docs Standards

- **Clarity first** — prefer practical examples and direct wording
- **Build cleanly** — run `npm run docs:build` before opening the PR
- **Keep links current** — prefer the published docs site and current repo URLs
- **Commits** — use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`

## Code of Conduct

Be respectful, constructive, and inclusive. See [CODE_OF_CONDUCT.md](https://github.com/Agenticstiger/forge-cli/blob/main/CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your work will be licensed under [Apache 2.0](https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE).

---

<p style="text-align: center; opacity: 0.7; font-size: 0.9rem;">Copyright 2025-2026 <a href="https://fluidhq.io">Agentics Transformation Pty Ltd</a> · Open source under <a href="https://github.com/Agenticstiger/forge-cli/blob/main/LICENSE">Apache 2.0</a></p>
