# Example: `gitlab-ci-scaffold` — generate a complete CI project

A realistic `CustomScaffold` plugin: given any fluid contract, emit a full `README.md` + `.gitlab-ci.yml` + one `config/<env>.json` per declared environment. ~150 LOC, ~25 tests (20 inherited from the conformance harness + 5 plugin-specific).

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/gitlab-ci-scaffold/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/gitlab-ci-scaffold).

## What it does

The contract is the source of truth. Change `environments` in the contract, regenerate, and the CI definition + config files adapt automatically — no per-env template editing.

Given a contract that declares its environments and clouds, the plugin emits:

```text
README.md                                  ← project README with owner/domain/envs
.gitlab-ci.yml                             ← 2-stage pipeline + 1 deploy job per env
config/dev.json                            ← per-env cloud config (provider-shaped)
config/staging.json
config/prod.json
```

Add a fourth environment to the contract, regenerate, and a fourth deploy job + config appears. Drop one, and the CI shrinks. **The contract drives the pipeline.**

### Pick your cloud

The plugin reads `environments.<env>.cloud` from the contract. The exact field shape is provider-specific (AWS has `account`, GCP has `project`, Snowflake has `account` + `warehouse`, …). Pick the one that matches your deploy target:


::: details AWS — accounts + regions
```yaml
# contract.fluid.yaml
metadata:
  id: order-events
  name: Order Events
  description: Realtime order event stream.
  owner: { email: events-team@example.com }
  domain: commerce

environments:
  dev:
    cloud: { provider: aws, account: "111111111111", region: us-east-1 }
  staging:
    cloud: { provider: aws, account: "222222222222", region: us-east-1 }
  prod:
    cloud: { provider: aws, account: "333333333333", region: us-west-2 }
```

Generated `config/dev.json`:

```json
{
  "cloud": "aws",
  "account": "111111111111",
  "region": "us-east-1"
}
```

The plugin's `_render_env_config` reads `account` and `region` directly off the `cloud` block. The 12-digit string is the AWS account ID — quoted to keep YAML from interpreting it as a number.
:::



::: details GCP — project IDs + regions
```yaml
# contract.fluid.yaml
metadata:
  id: order-events
  name: Order Events
  description: Realtime order event stream.
  owner: { email: events-team@example.com }
  domain: commerce

environments:
  dev:
    cloud: { provider: gcp, project: "order-events-dev",     region: us-central1 }
  staging:
    cloud: { provider: gcp, project: "order-events-staging", region: us-central1 }
  prod:
    cloud: { provider: gcp, project: "order-events-prod",    region: us-east1 }
```

Generated `config/dev.json`:

```json
{
  "cloud": "gcp",
  "project": "order-events-dev",
  "region": "us-central1"
}
```

GCP-shaped contracts use `project` (the GCP project ID — kebab-case string), not `account`. Region names follow GCP's convention (`us-central1`, `us-east1`, `europe-west4`, …).

> **Adapt the plugin**: the `gitlab-ci-scaffold` example in the SDK repo is written for AWS-shaped contracts (`account`). For GCP, change `_render_env_config` to emit `"project": env.get("project", "")` in place of `account`, or make the helper provider-aware. See the full source below — it's ~6 lines.
:::



::: details Snowflake — account + warehouse + role
```yaml
# contract.fluid.yaml
metadata:
  id: order-events
  name: Order Events
  description: Realtime order event stream.
  owner: { email: events-team@example.com }
  domain: commerce

environments:
  dev:
    cloud:
      provider: snowflake
      account: "myorg-dev.us-east-1"
      database: ORDERS_DEV
      schema:   PUBLIC
      warehouse: WH_XS
      role:      DATA_ENGINEER
  prod:
    cloud:
      provider: snowflake
      account: "myorg-prod.us-east-1"
      database: ORDERS_PROD
      schema:   PUBLIC
      warehouse: WH_M
      role:      DATA_PRODUCT_OWNER
```

Generated `config/dev.json`:

```json
{
  "cloud": "snowflake",
  "account": "myorg-dev.us-east-1",
  "database": "ORDERS_DEV",
  "warehouse": "WH_XS",
  "role": "DATA_ENGINEER"
}
```

Snowflake contracts carry `database` / `schema` / `warehouse` / `role` in the `cloud` block — none of which apply to AWS or GCP. The plugin's `_render_env_config` should switch on `cloud.provider` and pick the relevant keys for each provider.
:::



::: details Multi-cloud — different clouds per environment
```yaml
# contract.fluid.yaml — dev runs in GCP, prod in AWS
environments:
  dev:
    cloud: { provider: gcp, project: "order-events-dev", region: us-central1 }
  prod:
    cloud: { provider: aws, account: "333333333333",     region: us-west-2 }
```

A contract can declare different `provider:` values per environment — useful for "test on the cheap cloud, ship on the expensive one" patterns. Make sure your plugin's `_render_env_config` handles both shapes.
:::


The plugin and its tests in the SDK repo are written against the **AWS** shape; that's the canonical form throughout the rest of this page.

## Layout

```
gitlab-ci-scaffold/
├── pyproject.toml
├── src/gitlab_ci_scaffold/
│   ├── __init__.py
│   └── scaffold.py                ← ~140 lines, full source below
├── tests/
│   └── test_scaffold.py           ← 97 lines, plugin-specific scenarios
└── demo.py                        ← runnable demo against LOCAL_CONTRACT
```

## `src/gitlab_ci_scaffold/scaffold.py`

The file has three parts: identity, the `plan()` method (the heart of every CustomScaffold), and three private rendering helpers. The `plan()` is the interesting bit; the renderers are folded into collapsibles below.

```python
"""GitLab CI scaffold — generates a full project layout from a fluid contract."""

from __future__ import annotations

import json
from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    CustomScaffold,
    PluginMetadata,
    write_file_action,
)


class GitLabCIScaffold(CustomScaffold):
    """Generates README.md, .gitlab-ci.yml, and per-env config files."""

    name = "gitlab-ci"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="GitLab CI Scaffold",
            description="Generates a complete GitLab CI scaffold from a fluid contract.",
            version="0.1.0",
            author="FLUID SDK Examples",
            tags=["ci", "gitlab", "scaffold"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        actions: List[dict] = []

        # 1. The project README.
        actions.append(
            write_file_action(
                path="README.md",
                content=self._render_readme(c).encode("utf-8"),
                description="Project README",
            ).to_dict()
        )

        # 2. The CI definition.
        actions.append(
            write_file_action(
                path=".gitlab-ci.yml",
                content=self._render_ci(c).encode("utf-8"),
                description="GitLab CI definition",
            ).to_dict()
        )

        # 3. One config file per environment.
        for env_name in c.environment_names():
            actions.append(
                write_file_action(
                    path=f"config/{env_name}.json",
                    content=self._render_env_config(c, env_name).encode("utf-8"),
                    description=f"Config for environment {env_name!r}",
                ).to_dict()
            )

        return actions

    # The three private renderers below are mechanical f-strings.
    # Click to expand if you want the full source.
    # ↓
```


::: details Renderer 1: _render_readme — produces a Markdown README from contract identity + envs
```python
def _render_readme(self, c: ContractHelper) -> str:
    owner = c.owner.get("email", "unknown")
    envs = ", ".join(c.environment_names()) or "(none declared)"
    return (
        f"# {c.name or c.id or 'Unnamed'}\n\n"
        f"{c.description or ''}\n\n"
        f"## Project metadata\n\n"
        f"- **Owner:** {owner}\n"
        f"- **Domain:** {c.domain or 'unknown'}\n"
        f"- **Environments:** {envs}\n\n"
        f"## CI / CD\n\n"
        f"This project ships a `.gitlab-ci.yml` with one `deploy:` job per environment.\n"
        f"Push to `main` to trigger.\n"
    )
```
:::



::: details Renderer 2: _render_ci — produces .gitlab-ci.yml with one deploy job per env
```python
def _render_ci(self, c: ContractHelper) -> str:
    envs = c.environment_names()
    lines = [
        f"# Auto-generated GitLab CI for {c.id}",
        "# DO NOT EDIT BY HAND — regenerate via `fluid generate custom-scaffold`",
        "",
        "stages: [validate, deploy]",
        "",
        "validate:",
        "  stage: validate",
        "  script:",
        "    - fluid validate contract.fluid.yaml",
        "",
    ]
    for env_name in envs:
        lines.extend([
            f"deploy:{env_name}:",
            "  stage: deploy",
            "  script:",
            f"    - fluid apply contract.fluid.yaml --env {env_name} --yes",
            "  rules:",
            "    - if: $CI_COMMIT_BRANCH == \"main\"",
            "",
        ])
    return "\n".join(lines)
```
:::



::: details Renderer 3: _render_env_config — produces one config/&lt;env&gt;.json per environment
```python
def _render_env_config(self, c: ContractHelper, env_name: str) -> str:
    env = (c.environments.get(env_name) or {}).get("cloud", {})
    return json.dumps({
        "cloud": env.get("provider", "unknown"),
        "account": env.get("account", ""),
        "region": env.get("region", ""),
    }, indent=2, sort_keys=True)
```

This is the AWS-shaped renderer. For GCP-shaped contracts (`project` instead of `account`), see the "Pick your cloud" collapsibles near the top of this page.
:::


Two things to note about the design:

- **`ContractHelper` is the only contract-shape dependency.** No raw dict-walking; the helper is version-tolerant across `fluidVersion 0.4` through `0.7.3` so your plugin doesn't break when the schema evolves.
- **The renderer is plain f-strings.** No template engine required — the SDK's role is enough for most scaffolds. For more complex output (loops, conditionals, partials), see the [your-own-CI journey](../journeys/your-own-ci.md) which uses the YAML+Jinja bundle pattern.

## Tests — ~25 in total

The conformance harness gives you 20 invariants for free (13 from `PluginTestHarness` + 7 from `CustomScaffoldTestHarness`). The 3 excerpts below show the plugin-specific scenarios; the upstream example adds ~5 more for full coverage:

```python
# tests/test_scaffold.py (excerpts)

class TestGitLabCIScaffold(CustomScaffoldTestHarness):
    plugin_class = GitLabCIScaffold
    sample_contracts = [LOCAL_CONTRACT]

    # === Scenarios specific to this plugin (added by you) ===

    def test_emits_one_config_per_environment(self):
        plugin = self._instantiate()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        config_paths = [a["params"]["path"] for a in actions
                        if a["params"]["path"].startswith("config/")]
        assert config_paths == ["config/dev.json", "config/staging.json", "config/prod.json"]

    def test_no_environments_means_no_config_files(self):
        plugin = self._instantiate()
        actions = plugin.plan({"metadata": {"id": "x"}, "environments": {}})
        assert all("config/" not in a["params"]["path"] for a in actions)

    def test_ci_yaml_has_deploy_per_env(self):
        plugin = self._instantiate()
        actions = plugin.plan(MULTI_ENV_CONTRACT)
        ci = next(a for a in actions if a["params"]["path"] == ".gitlab-ci.yml")
        body = ci["params"]["content_b64"]  # base64-encoded bytes
        import base64
        decoded = base64.b64decode(body).decode()
        assert "deploy:dev:" in decoded
        assert "deploy:staging:" in decoded
        assert "deploy:prod:" in decoded
```

## Run it

```bash
# in the gitlab-ci-scaffold/ directory
pip install -e ".[dev]"
pytest
# ============== 25 passed in 0.11s ===============
```

End-to-end against a real contract:

```bash
pip install data-product-forge data-product-forge-custom-scaffold

# In your project's contract.fluid.yaml:
#   extensions:
#     customScaffold:
#       libraries:
#         - id: ci
#           source: { kind: entrypoint, name: gitlab-ci }
#       patterns:
#         - use: ci:main

fluid generate custom-scaffold
# ✓ 5 files written, 0 failed
#   README.md
#   .gitlab-ci.yml
#   config/dev.json
#   config/staging.json
#   config/prod.json
```

## You'll know it worked when

- All ~25 tests pass under `pytest`.
- The generated `.gitlab-ci.yml` has exactly one `deploy:<env>:` block per environment in your contract.
- Adding a new `environments.staging-eu` entry to the contract and re-running `fluid generate custom-scaffold` produces a new `config/staging-eu.json` and a new `deploy:staging-eu:` block — without editing any plugin code.
- `git diff` between two consecutive runs (no contract changes) is empty (determinism).

## When **not** to use this pattern

When the team owning the CI templates **isn't comfortable editing Python**. The YAML+Jinja bundle pattern in the [your-own-CI journey](../journeys/your-own-ci.md) lets template authors work in `.j2` files without touching the plugin source. Either pattern is fine; pick based on who's authoring.

## Next

- [Custom validator example](./steward-validator.md) — same plugin shape, different role
- [Apply-hook example](./apply-hook-prod-key-guard.md) — runs at `fluid apply`, not generation
- [Journeys → your-own-CI](../journeys/your-own-ci.md) — YAML+Jinja bundle variant
- [Reference → roles](../reference/roles.md) — what `CustomScaffold` inherits and what you override
