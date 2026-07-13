# Example: `gitlab-ci-scaffold` — generate a complete CI project

A realistic `CustomScaffold` plugin: given any fluid contract, emit a full `README.md` + `.gitlab-ci.yml` + one `config/<env>.json` per declared environment. ~140 LOC, 22 passing tests (15 inherited from the conformance harness + 5 plugin-specific).

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/gitlab-ci-scaffold/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/gitlab-ci-scaffold).

## What it does

The contract is the source of truth. Change `environments` in the contract, regenerate, and the CI definition + config files adapt automatically — no per-env template editing.

Given a contract that declares its environments, the plugin emits:

```text
README.md                                  ← project README with owner/domain/envs
.gitlab-ci.yml                             ← validate + 1 deploy job per env (prod is when: manual)
config/dev.json                            ← per-env cloud config
config/staging.json
config/prod.json
```

Add a fourth environment to the contract, regenerate, and a fourth deploy job + config appears. Drop one, and the CI shrinks. **The contract drives the pipeline.**

### Contract shape

The plugin is **provider-agnostic**. It reads two free-form string labels from each environment:

- `metadata.labels."cloud.accountId"` — your cloud's identifier (GCP project ID, AWS account number, Snowflake account name, …)
- `metadata.labels."cloud.region"` — your cloud's region

That's it. The plugin doesn't know or care which cloud you're on — it just shells the two labels straight into the generated `config/<env>.json`. Use whatever values match your deploy target.

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.4"
kind: DataProduct
id: order-events
name: Order Events
description: Realtime order event stream.
domain: commerce
metadata:
  owner: { team: commerce, email: events-team@example.com }

environments:
  dev:
    metadata:
      labels:
        cloud.accountId: "order-events-dev"
        cloud.region: us-central1
  staging:
    metadata:
      labels:
        cloud.accountId: "order-events-staging"
        cloud.region: us-central1
  prod:
    metadata:
      labels:
        cloud.accountId: "order-events-prod"
        cloud.region: us-east1
```

Generated `config/dev.json`:

```json
{
  "cloud": {
    "accountId": "order-events-dev",
    "region": "us-central1"
  },
  "environment": "dev",
  "product": {
    "id": "order-events",
    "owner": "events-team@example.com"
  }
}
```

> The label name `cloud.accountId` is generic — it's a string-keyed label, not a typed cloud-binding field. AWS folks would put `"111111111111"` in there; Snowflake folks would put `"myorg.us-east-1"`. The plugin doesn't validate the format, so it works the same for any provider. If your org needs richer per-cloud metadata (warehouse, role, project number, …), add more labels and extend `_render_env_config` to read them.

## Layout

```
gitlab-ci-scaffold/
├── pyproject.toml
├── src/gitlab_ci_scaffold/
│   ├── __init__.py
│   └── scaffold.py                ← ~140 lines, full source below
├── tests/
│   └── test_scaffold.py           ← 5 domain assertions on top of the conformance harness
└── demo.py                        ← runnable demo against a 3-env CONTRACT
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



::: details Renderer 2: _render_ci — produces .gitlab-ci.yml with one deploy job per env (prod is when: manual)
```python
def _render_ci(self, c: ContractHelper) -> str:
    envs = c.environment_names()
    lines: List[str] = []
    lines.append(f"# Auto-generated GitLab CI for {c.id}")
    lines.append("# DO NOT EDIT BY HAND — regenerate via `fluid generate-custom-scaffold`")
    lines.append("")
    lines.append("stages:")
    lines.append("  - validate")
    lines.append("  - deploy")
    lines.append("")
    lines.append("validate:")
    lines.append("  stage: validate")
    lines.append("  script:")
    lines.append("    - fluid validate")
    lines.append("")
    for env in envs:
        lines.append(f"deploy:{env}:")
        lines.append("  stage: deploy")
        lines.append("  script:")
        lines.append(f"    - fluid apply --env {env}")
        if env == "prod":
            lines.append("  when: manual")
            lines.append("  only:")
            lines.append("    - main")
        else:
            lines.append("  only:")
            lines.append("    - main")
        lines.append("")
    return "\n".join(lines)
```

Note the `when: manual` branch — prod deploys are gated so they don't auto-run on merge to main. A reviewer has to click "Run" in the GitLab pipeline UI. This is the single most important production-safety convention this plugin enforces, and it's pinned by a test (`test_prod_deploy_is_manual`).
:::



::: details Renderer 3: _render_env_config — produces one config/&lt;env&gt;.json per environment
```python
def _render_env_config(self, c: ContractHelper, env_name: str) -> str:
    env = c.environments.get(env_name) or {}
    env_meta = env.get("metadata") or {}
    labels = env_meta.get("labels") or {}
    config = {
        "environment": env_name,
        "cloud": {
            "accountId": labels.get("cloud.accountId", "unknown"),
            "region": labels.get("cloud.region", "unknown"),
        },
        "product": {
            "id": c.id,
            "owner": c.owner.get("email"),
        },
    }
    return json.dumps(config, indent=2, sort_keys=True) + "\n"
```

Reads two flat string labels off `environments.<env>.metadata.labels` (`cloud.accountId`, `cloud.region`) and emits them under a structured `cloud` block, alongside `environment` and `product` identity. Both labels default to `"unknown"` if absent — the plugin never raises on a missing label, so a contract with no labels still produces a valid (if uninformative) config file.
:::


Two things to note about the design:

- **`ContractHelper` is the only contract-shape dependency.** No raw dict-walking against the contract root; the helper smooths over `fluidVersion` evolution so the plugin doesn't break when the schema moves. Per-env metadata (`env.get("metadata")`) is read directly as a plain dict — that shape (`environments.<env>.metadata.labels`) is stable across versions.
- **The renderer is plain f-strings.** No template engine required — the SDK's role is enough for most scaffolds. For more complex output (loops, conditionals, partials), see the [your-own-CI journey](../journeys/your-own-ci.md) which uses the YAML+Jinja bundle pattern.

## Tests — 22 in total

The `CustomScaffoldTestHarness` gives you 15 conformance invariants for free. The 5 plugin-specific assertions below are the full set in `tests/test_scaffold.py`:

```python
# tests/test_scaffold.py

MULTI_ENV_CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "my-data-product",
    "name": "My Data Product",
    "description": "A nightly aggregation of yesterday's events.",
    "domain": "platform",
    "metadata": {
        "owner": {"team": "platform", "email": "platform@example.com"},
    },
    "environments": {
        "dev":     {"metadata": {"labels": {"cloud.accountId": "111111111111", "cloud.region": "eu-west-1"}}},
        "staging": {"metadata": {"labels": {"cloud.accountId": "222222222222", "cloud.region": "eu-west-1"}}},
        "prod":    {"metadata": {"labels": {"cloud.accountId": "333333333333", "cloud.region": "eu-west-1"}}},
    },
    "exposes": [], "consumes": [], "builds": [],
}


class TestGitLabCIScaffold(CustomScaffoldTestHarness):
    plugin_class = GitLabCIScaffold
    sample_contracts = [MULTI_ENV_CONTRACT]

    def _action_content(self, actions, path: str) -> str:
        action = next(a for a in actions if a["params"]["path"] == path)
        return base64.b64decode(action["params"]["content_b64"]).decode("utf-8")

    def test_readme_includes_owner_and_envs(self):
        readme = self._action_content(self.get_plugin().plan(MULTI_ENV_CONTRACT), "README.md")
        assert "platform@example.com" in readme
        assert "dev, prod, staging" in readme   # environment_names() returns sorted

    def test_ci_has_one_deploy_per_env(self):
        ci = self._action_content(self.get_plugin().plan(MULTI_ENV_CONTRACT), ".gitlab-ci.yml")
        assert all(f"deploy:{e}:" in ci for e in ("dev", "staging", "prod"))

    def test_prod_deploy_is_manual(self):
        """Prod deploys must be gated `when: manual` so they don't auto-run."""
        ci = self._action_content(self.get_plugin().plan(MULTI_ENV_CONTRACT), ".gitlab-ci.yml")
        prod_idx = ci.index("deploy:prod:")
        rest = ci[prod_idx + len("deploy:prod:"):]
        next_deploy = rest.find("\ndeploy:")
        end = prod_idx + len("deploy:prod:") + next_deploy if next_deploy != -1 else len(ci)
        assert "when: manual" in ci[prod_idx:end]

    def test_env_config_carries_account_id(self):
        dev_config = json.loads(self._action_content(self.get_plugin().plan(MULTI_ENV_CONTRACT), "config/dev.json"))
        assert dev_config["cloud"]["accountId"] == "111111111111"
        assert dev_config["cloud"]["region"] == "eu-west-1"

    def test_emits_correct_file_count(self):
        # 1 README + 1 CI + 3 env configs = 5
        assert len(self.get_plugin().plan(MULTI_ENV_CONTRACT)) == 5
```

`test_prod_deploy_is_manual` is the one that's actually load-bearing: it pins the production-safety convention so a future refactor of `_render_ci` can't accidentally drop the gate.

## Run it

```bash
# in the gitlab-ci-scaffold/ directory
pip install -e ".[dev]"
pytest
# ============== 22 passed ===============
```

End-to-end against a real contract:

```bash
pip install data-product-forge data-product-forge-custom-scaffold gitlab-ci-scaffold

# In your project's contract.fluid.yaml:
#   extensions:
#     customScaffold:
#       libraries:
#         - id: ci
#           source: { kind: pypi, package: gitlab-ci-scaffold, version: ">=0.1" }
#       patterns:
#         - use: ci:gitlab-ci

fluid generate-custom-scaffold
# ✓ 5 files written, 0 failed
#   README.md
#   .gitlab-ci.yml
#   config/dev.json
#   config/staging.json
#   config/prod.json
```

## You'll know it worked when

- All 22 tests pass under `pytest`.
- The generated `.gitlab-ci.yml` has exactly one `deploy:<env>:` block per environment in your contract, and the `deploy:prod:` block carries `when: manual`.
- Adding a new `environments.staging-eu` entry to the contract and re-running `fluid generate-custom-scaffold` produces a new `config/staging-eu.json` and a new `deploy:staging-eu:` block — without editing any plugin code.
- `git diff` between two consecutive runs (no contract changes) is empty (determinism).

## When **not** to use this pattern

When the team owning the CI templates **isn't comfortable editing Python**. The YAML+Jinja bundle pattern in the [your-own-CI journey](../journeys/your-own-ci.md) lets template authors work in `.j2` files without touching the plugin source. Either pattern is fine; pick based on who's authoring.

## Next

- [Custom validator example](./steward-validator.md) — same plugin shape, different role
- [Apply-hook example](./apply-hook-prod-key-guard.md) — runs at `fluid apply`, not generation
- [Journeys → your-own-CI](../journeys/your-own-ci.md) — YAML+Jinja bundle variant
- [Reference → roles](../reference/roles.md) — what `CustomScaffold` inherits and what you override
