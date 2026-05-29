# Companion packages

Three packages ship together as one platform. End users only need the CLI; plugin authors need the SDK; plugin authors who want to ship file-emitting plugins via Jinja+YAML bundles also need the custom-scaffold engine.

## Quick reference

| Package | Version | PyPI | Import path | What you reach for it for |
|---|---|---|---|---|
| **`data-product-forge`** | `0.8.6` | [pypi.org/project/data-product-forge](https://pypi.org/project/data-product-forge/) | `import fluid_build` | The CLI itself — `fluid` command, all built-in providers, the `fluid generate`/`validate`/`apply`/`publish` lifecycle |
| **`data-product-forge-sdk`** | `0.9.0` | [pypi.org/project/data-product-forge-sdk](https://pypi.org/project/data-product-forge-sdk/) | `from fluid_sdk import …` | Zero-dependency ABCs (`BasePlugin`, `CustomScaffold`, `Validator`, etc.) + conformance test harness. Plugin authors only. |
| **`data-product-forge-custom-scaffold`** | `0.1.0` | [pypi.org/project/data-product-forge-custom-scaffold](https://pypi.org/project/data-product-forge-custom-scaffold/) | `from data_product_forge_custom_scaffold import …` | Reference Jinja+YAML bundle engine. Use this when your plugin distributes templates via a git bundle (most common pattern). |

## Who installs what

| You are… | Install |
|---|---|
| **End user** consuming someone else's plugins | `pip install data-product-forge data-product-forge-custom-scaffold <plugin-package>` |
| **Plugin author** writing a new role subclass | `pip install data-product-forge-sdk` for development; the CLI itself for testing |
| **Bundle author** distributing Jinja templates to other teams | No extra install — consumers install `data-product-forge-custom-scaffold`; you just host the bundle in git |
| **Platform team** building a custom CLI subcommand | `pip install data-product-forge-sdk` if your plugin subclasses anything, otherwise no SDK needed (entry-point can be a plain function) |

## The SDK dual-naming explained

PyPI distribution: `data-product-forge-sdk`. Python import path: `fluid_sdk`.

```bash
pip install data-product-forge-sdk
```

```python
from fluid_sdk import CustomScaffold, ContractHelper, write_file_action
```

This is **deliberate**, and standard PyPI practice. Same pattern as:

- `pillow` ↔ `from PIL import Image`
- `scikit-learn` ↔ `from sklearn import …`
- `pyyaml` ↔ `import yaml`
- `attrs` ↔ `import attr`

The PyPI name reflects the product brand (`data-product-forge`). The import path stays short, version-stable, and module-friendly (`fluid_sdk` was its name before the rename and hasn't changed).

**You don't have to do anything special** — `pip install data-product-forge-sdk` makes `import fluid_sdk` work. The CLI's `requirements.txt` and your plugin's `pyproject.toml` both use the dist name; only your Python source uses the import path.

## Version pinning recommendations

### If you're consuming the CLI

```toml
dependencies = [
    "data-product-forge==0.8.6",  # pin exact for reproducibility
]
```

For production deploys, exact pin (`==`) is right. For development environments, looser bound (`>=0.8,<0.9`) is fine — minor versions are backwards-compatible.

### If you're writing a plugin

```toml
dependencies = [
    "data-product-forge-sdk>=0.9,<1",   # upper bound is important
]
```

The upper bound `<1` is critical: the SDK is on the 0.x line and minor versions may break the API. Bump your upper bound (`<1` → `<2`) only after testing against the new major version.

For the custom-scaffold engine (if you're shipping bundles that ride on it):

```toml
dependencies = [
    "data-product-forge-sdk>=0.9,<1",
    "data-product-forge-custom-scaffold>=0.1,<0.2",
]
```

### If you're a plugin author shipping to PyPI

Your **plugin** ships with a pinned SDK requirement; your **users** install your plugin and let pip resolve the SDK transitively. That means **you control which SDK version they use**.

Best practice:
1. Pin to the lowest SDK version your plugin actually needs.
2. Run CI against multiple SDK versions to confirm the lower bound is real.
3. Bump the upper bound only after testing against a new SDK release.

## Version stability commitments

### `data-product-forge` (CLI)

- **Semantic versioning since 0.8.0.** Minor versions add features and may deprecate (with warning) but won't break. Major versions can break.
- **The `0.7.x` contract schema is supported indefinitely** by the 0.8 line — contracts using `fluidVersion: 0.7.1` / `0.7.2` / `0.7.3` all validate.
- **Pre-releases** are tagged with PEP 440 suffixes (`0.8.4rc1`, `0.8.4b1`, etc.). They publish to PyPI but `pip install` skips them by default.

### `data-product-forge-sdk`

- **Currently 0.9.0 — Beta classifier.** First stable `1.0.0` planned after a validation window with the first external plugins on PyPI.
- Minor versions (0.9 → 0.10) **may** break the API; we expect them not to in practice but the classifier reflects "we reserve the right." Pin the upper bound (`<1`).
- Patch versions (0.9.0 → 0.9.1) only fix bugs; safe to consume without bumping.

### `data-product-forge-custom-scaffold`

- **Currently 0.1.0 — Beta classifier.** Same model as the SDK: first stable cut after the validation window.
- The bundle manifest format is **`fluid.dev/custom-scaffold.v1`** — a v2 would be a breaking change, and bundles would need to update their `apiVersion`. No v2 is on the roadmap.

## Where to find the source

| Package | Repo | License |
|---|---|---|
| `data-product-forge` | [`Agenticstiger/forge-cli`](https://github.com/Agenticstiger/forge-cli) | Apache-2.0 |
| `data-product-forge-sdk` | [`Agenticstiger/forge-cli-sdk`](https://github.com/Agenticstiger/forge-cli-sdk) | Apache-2.0 |
| `data-product-forge-custom-scaffold` | [`Agenticstiger/data-product-forge-custom-scaffold`](https://github.com/Agenticstiger/data-product-forge-custom-scaffold) | Apache-2.0 |

Issues, PRs, and discussions all happen on the upstream repos. The `examples/` directories on each contain runnable starting points.

## Upgrade compatibility

| You're upgrading | From → To | What might break |
|---|---|---|
| CLI | 0.8.x → 0.8.y | Nothing — patch and minor are backwards-compatible. |
| CLI | 0.8.x → 0.9.0 | (not yet released) Will be communicated via [release notes](../../RELEASE_NOTES_0.8.3.md). |
| SDK | 0.9.x → 0.9.y | Nothing — patches only fix bugs. |
| SDK | 0.9 → 0.10 | (not yet released) Possible API changes; check release notes; bump upper bound. |
| SDK | 0.9 → 1.0 | (not yet released) Will be the "stable cut." Should be a no-op if you've been on 0.9.x; if not, release notes will say. |
| Custom-scaffold | 0.1.x → 0.1.y | Nothing — patches only. |
| Custom-scaffold | 0.1 → 0.2 | Bundle manifest format unchanged (`v1`). Resolver protocol may change for plugin-bundle authors; check release notes. |

## Roadmap

(High-level — see each repo's GitHub for milestones)

- **CLI**: continued growth of the v0.7.3 schema's acquisition-pattern engines; 0.9 line will introduce contract-versioning policy work.
- **SDK**: stabilize at 1.0 after the validation window. No new roles planned; the four existing roles (`CustomScaffold` / `Validator` / `InfraProvider` / `CatalogAdapter`) cover the spec.
- **Custom-scaffold**: 0.2 line will add a `pypi` resolver kind (so bundles can be installed via `pip install` directly) and an `npm` resolver kind. Today, `path` / `git` / `entrypoint` cover the common cases.

## Reference

- [Packaging](./packaging.md) — how to ship a plugin to PyPI
- [Roles](./roles.md) — the four roles and their helpers
- [Entry points](./entry-points.md) — the six entry-point groups and when to use each
- [Trust model](./trust-model.md) — what the CLI guarantees about plugins
