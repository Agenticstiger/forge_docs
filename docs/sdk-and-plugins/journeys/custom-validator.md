# You have governance rules, no problem

Your platform/security/data-governance team has rules: every Gold data product must declare a steward; the steward's email must match `@my-org.example.com`; cost-center labels are required; classification tags must come from a controlled vocabulary. You want these rules to run **at contract-author time** — `fluid validate` — so they fail fast in the IDE, on every commit, and in CI, before anyone tries to deploy.

This guide walks through authoring a `Validator` plugin from scratch. By the end you'll have:

- A `Validator` subclass that inspects a contract and emits **structured `Finding` records** (info / warn / error / critical).
- A package on PyPI (or your private index) that any team can `pip install` and have your rules apply to **every** `fluid validate` invocation in their environment.
- A test that runs your rules against ~10 sample contracts (good and bad) — no manual QA needed.

Realistic time end-to-end: **20–30 minutes**. Plus however long it takes to settle the rules with your stakeholders, which is usually longer.

## The mental model

```text
                  on every `fluid validate` …
                              │
                              ▼
              ┌────────────────────────────────────────────┐
              │ core schema validation (built-in)          │
              │   ├── fluidVersion compatible?             │
              │   ├── metadata.id present?                 │
              │   ├── builds/transforms/exposes well-formed?│
              │   └── extensions block well-formed?        │
              └─────────────────┬──────────────────────────┘
                                ▼
              ┌────────────────────────────────────────────┐
              │ your-team's Validator plugins              │
              │   ├── SteWardRequired                      │ ← yours
              │   ├── CostCenterRequired                   │ ← yours
              │   ├── DataClassificationFromVocab          │ ← yours
              │   └── (any other validators on PyPI / pip) │
              └─────────────────┬──────────────────────────┘
                                ▼
                       findings rolled up,
                       exit code = max severity
```

Validators are **discovered automatically** at `fluid validate` startup — there's no per-product opt-in. If `pip install` resolves your validator, it runs.

## Step 0 — see the result first

For a contract that's missing the required label:

```bash
fluid validate contract.fluid.yaml
```

```text
✗ Validation failed
  Errors:
    - extensions.steward-required: STEWARD_ID_MISSING:
      Contract 'order-events' is missing the required label 'principal.steward.id'.
      → Add metadata.labels['principal.steward.id'] with the employee identifier
        of the data steward.

  Warnings:
    (none)
```

Once fixed:

```bash
fluid validate contract.fluid.yaml
```

```text
✓ Contract valid against fluidVersion 0.7.3
```

If the contract has the id but no email:

```text
⚠ Validation passed with warnings
  Warnings:
    - extensions.steward-required: STEWARD_EMAIL_MISSING:
      Contract 'order-events' declares a steward id but no email — operations
      notifications will go nowhere.
      → Add metadata.labels['principal.steward.email'] with the team / steward email.
```

Severity drives the exit code: `error` → exit 1, `warn` → exit 0 (unless `--strict` is set, in which case warnings also fail). This works automatically across CI / pre-commit / `fluid` invocations.

## Step 1 — set up the package skeleton

```bash
mkdir my-org-validators && cd my-org-validators
mkdir -p src/my_org_validators tests
touch src/my_org_validators/__init__.py tests/__init__.py
```

## Step 2 — write `pyproject.toml`

```toml
# my-org-validators/pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-org-validators"
version = "0.1.0"
description = "Data-governance validators for my-org"
requires-python = ">=3.10"
dependencies = ["data-product-forge-sdk>=0.9,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

# Each validator is registered separately under the same group.
# Once installed, every `fluid validate` runs all three rules.
[project.entry-points."fluid_build.validators"]
steward-required = "my_org_validators.steward:StewardRequired"
cost-center-required = "my_org_validators.cost_center:CostCenterRequired"
classification-from-vocab = "my_org_validators.classification:ClassificationFromVocab"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Three rules → three entry-point lines, one file each. The same package can register as many validators as you like.

## Step 3 — write the first validator

```python
# src/my_org_validators/steward.py
"""StewardRequired — every contract MUST declare a steward identifier."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import ContractHelper, Finding, PluginMetadata, Validator


class StewardRequired(Validator):
    """Every contract must carry metadata.labels['principal.steward.id']."""

    name = "steward-required"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Steward Required Validator",
            description="Every contract must declare a data steward identifier.",
            version="0.1.0",
            author="my-org platform team",
            tags=["governance", "compliance"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = c.metadata.get("labels") or {}
        steward_id = labels.get("principal.steward.id")
        steward_email = labels.get("principal.steward.email")

        if not steward_id:
            findings.append(Finding(
                severity="error",
                code="STEWARD_ID_MISSING",
                message=(
                    f"Contract {c.id!r} is missing the required label "
                    f"'principal.steward.id'."
                ),
                path='metadata.labels["principal.steward.id"]',
                remediation=(
                    "Add metadata.labels['principal.steward.id'] with the "
                    "employee/user identifier of the data steward."
                ),
            ))

        if steward_id and not steward_email:
            findings.append(Finding(
                severity="warn",
                code="STEWARD_EMAIL_MISSING",
                message=(
                    f"Contract {c.id!r} declares a steward id but no email — "
                    "operations notifications will go nowhere."
                ),
                path='metadata.labels["principal.steward.email"]',
                remediation=(
                    "Add metadata.labels['principal.steward.email'] with the "
                    "team / steward email."
                ),
            ))

        if steward_email and not steward_email.endswith("@my-org.example.com"):
            findings.append(Finding(
                severity="error",
                code="STEWARD_EMAIL_DOMAIN",
                message=(
                    f"Steward email {steward_email!r} must be on the my-org "
                    f"domain (@my-org.example.com)."
                ),
                path='metadata.labels["principal.steward.email"]',
                remediation="Use the steward's official my-org email address.",
            ))

        return [f.to_action() for f in findings]
```

`Finding` is the SDK's structured-finding type. Every `severity` / `code` / `message` / `path` / `remediation` field is intentional — the CLI's output formatter uses each one. **A finding without a `remediation` is a bug** — never tell a user something's wrong without telling them how to fix it.

## Step 4 — write the second and third validators

The pattern is identical. Different rule, different `code`s.


::: details src/my_org_validators/cost_center.py — every product must declare a cost center
```python
"""CostCenterRequired — every contract MUST carry a cost-center label."""

from __future__ import annotations

import re
from typing import Any, List, Mapping

from fluid_sdk import ContractHelper, Finding, PluginMetadata, Validator


# cost centers at my-org are 4-digit codes prefixed with 'cc-'
_COST_CENTER_RE = re.compile(r"^cc-\d{4}$")


class CostCenterRequired(Validator):
    name = "cost-center-required"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Cost Center Required Validator",
            description="Every contract must declare metadata.labels['cost-center'].",
            version="0.1.0",
            tags=["governance", "finops"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = c.metadata.get("labels") or {}
        cost_center = labels.get("cost-center")

        if not cost_center:
            findings.append(Finding(
                severity="error",
                code="COST_CENTER_MISSING",
                message=f"Contract {c.id!r} is missing label 'cost-center'.",
                path='metadata.labels["cost-center"]',
                remediation=(
                    "Add metadata.labels['cost-center'] with your team's "
                    "cost-center code (format: cc-NNNN). Ask Finance if unsure."
                ),
            ))
        elif not _COST_CENTER_RE.match(cost_center):
            findings.append(Finding(
                severity="error",
                code="COST_CENTER_SHAPE",
                message=(
                    f"Cost-center {cost_center!r} doesn't match the required "
                    f"format `cc-NNNN`."
                ),
                path='metadata.labels["cost-center"]',
                remediation="Use the format `cc-` followed by 4 digits (e.g. cc-1234).",
            ))

        return [f.to_action() for f in findings]
```
:::



::: details src/my_org_validators/classification.py — controlled vocabulary for data classifications
```python
"""ClassificationFromVocab — classification labels must come from a controlled list."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import ContractHelper, Finding, PluginMetadata, Validator


# my-org's enterprise data-classification taxonomy
_ALLOWED_CLASSIFICATIONS = frozenset({
    "public",
    "internal",
    "confidential",
    "restricted",
    "regulated",
})


class ClassificationFromVocab(Validator):
    name = "classification-from-vocab"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Data Classification Vocabulary Check",
            description=(
                "metadata.labels['data-classification'] must be one of: "
                + ", ".join(sorted(_ALLOWED_CLASSIFICATIONS))
            ),
            version="0.1.0",
            tags=["governance", "data-classification"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = c.metadata.get("labels") or {}
        classification = labels.get("data-classification")

        # Gold/CDP products MUST declare a classification; SDP/Bronze MAY.
        if not classification and c.metadata.get("productType") == "CDP":
            findings.append(Finding(
                severity="error",
                code="CLASSIFICATION_REQUIRED_FOR_CDP",
                message=(
                    f"Consumer-Aligned Data Product {c.id!r} must declare "
                    f"a data-classification label."
                ),
                path='metadata.labels["data-classification"]',
                remediation=(
                    "Add metadata.labels['data-classification'] = one of: "
                    + ", ".join(sorted(_ALLOWED_CLASSIFICATIONS))
                ),
            ))

        if classification and classification not in _ALLOWED_CLASSIFICATIONS:
            findings.append(Finding(
                severity="error",
                code="CLASSIFICATION_NOT_IN_VOCAB",
                message=(
                    f"Classification {classification!r} is not in the enterprise "
                    f"vocabulary."
                ),
                path='metadata.labels["data-classification"]',
                remediation=(
                    "Use one of: " + ", ".join(sorted(_ALLOWED_CLASSIFICATIONS))
                ),
            ))

        return [f.to_action() for f in findings]
```
:::


## Step 5 — test against good and bad contracts

```python
# tests/test_steward.py
from fluid_sdk.testing import PluginTestHarness, LOCAL_CONTRACT
from my_org_validators.steward import StewardRequired


# Fixture contracts the harness will exercise the validator against
CONTRACT_NO_STEWARD = {
    "metadata": {"id": "p1", "labels": {}},
}
CONTRACT_GOOD_STEWARD = {
    "metadata": {
        "id": "p2",
        "labels": {
            "principal.steward.id": "emp-12345",
            "principal.steward.email": "alice@my-org.example.com",
        },
    },
}
CONTRACT_STEWARD_NO_EMAIL = {
    "metadata": {
        "id": "p3",
        "labels": {"principal.steward.id": "emp-12345"},
    },
}
CONTRACT_WRONG_DOMAIN = {
    "metadata": {
        "id": "p4",
        "labels": {
            "principal.steward.id": "emp-12345",
            "principal.steward.email": "alice@gmail.com",
        },
    },
}


class TestStewardRequired(PluginTestHarness):
    plugin_class = StewardRequired
    # Inherits the standard conformance suite from PluginTestHarness
    # (a Validator-specific subharness is on the roadmap).

    # === Plugin-specific scenarios (you write these) ===

    def test_missing_steward_id_is_error(self):
        actions = self._instantiate().plan(CONTRACT_NO_STEWARD)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert any(
            f["params"]["severity"] == "error"
            and f["params"]["code"] == "STEWARD_ID_MISSING"
            for f in findings
        )

    def test_steward_id_present_no_email_is_warning(self):
        actions = self._instantiate().plan(CONTRACT_STEWARD_NO_EMAIL)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert any(
            f["params"]["severity"] == "warn"
            and f["params"]["code"] == "STEWARD_EMAIL_MISSING"
            for f in findings
        )

    def test_wrong_email_domain_is_error(self):
        actions = self._instantiate().plan(CONTRACT_WRONG_DOMAIN)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert any(
            f["params"]["severity"] == "error"
            and f["params"]["code"] == "STEWARD_EMAIL_DOMAIN"
            for f in findings
        )

    def test_fully_specified_contract_is_clean(self):
        actions = self._instantiate().plan(CONTRACT_GOOD_STEWARD)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert findings == []
```

Run it:

```bash
pip install -e ".[dev]"
pytest
# ============== 17 passed in 0.06s ============   (13 inherited from PluginTestHarness + 4 plugin-specific)
```

Repeat the test pattern for the other two validators. Each adds ~50 LOC of tests and gets 13 conformance tests for free.

## Step 6 — wire it into your contracts

```bash
# In any product team's environment:
pip install data-product-forge my-org-validators

# Validators auto-discovered. No contract changes needed.
fluid validate contract.fluid.yaml
```

That's the whole user surface. Once `pip install my-org-validators` resolves on a developer's machine (or in CI), every contract they validate runs the rules. Onboarding new teams is `pip install`.

## Distributing across the org

Three places this typically gets installed:

1. **Developer machines** — `my-org-validators` is part of the standard data-platform dev environment (pyenv pip, devcontainer image, etc).
2. **Pre-commit** — add a hook that runs `fluid validate` on every commit:
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: local
       hooks:
         - id: fluid-validate
           name: fluid validate
           entry: fluid validate
           language: system
           files: contract\.fluid\.ya?ml$
   ```
3. **CI** — the bundle from [your-own-ci](./your-own-ci.md) already has a `validate` stage. Add `my-org-validators` to the `pip install` line:
   ```jinja
   - run: pip install "data-product-forge=={{ fluid_cli_version }}" my-org-validators
   - run: fluid validate contract.fluid.yaml --strict
   ```

## You'll know it worked when

- The `importlib.metadata.entry_points(group='fluid_build.validators')` one-liner returns all three validators.
- A contract missing `principal.steward.id` fails `fluid validate` with the structured error message.
- A contract with `steward.id` but no `steward.email` passes `fluid validate` with a structured warning.
- A contract with a steward email outside `@my-org.example.com` fails.
- All three validators run on every `fluid validate` invocation — no opt-in needed in the contract.
- `fluid validate --strict` makes warnings fail too (your team can decide whether to set `--strict` in CI).

## When **not** to use this pattern

- **For schema shape that the core validator already handles.** If your rule is "field X must be a string," the core JSON-Schema validation in `fluid validate` already catches it. Validators are for **policy** on top of shape.
- **For invariants that depend on runtime state.** "The deploy key env var must be set" can't be checked at validate time because the env var isn't set on the contract author's machine yet. That's an [apply hook](./apply-hook.md).
- **For checks that need network access.** `fluid validate` is expected to be offline-friendly. If your rule needs to call an external service (e.g. "verify this label is in our service catalog"), gate it behind `fluid validate --probe` (which **is** allowed to make network calls) and use a `Validator` that's a no-op when `--probe` isn't set.

## Common gotchas

::: details The validator doesn't run
Same pattern as the quickstart: `pip install -e .` after editing the entry-points block. Then re-run the `importlib.metadata.entry_points` one-liner to confirm. registration.
:::

::: details The validator runs but findings don't show up in the CLI output
The CLI groups findings by severity. `info` findings only appear with `--verbose`. If you wanted them visible by default, use `warn` instead.
:::

::: details I want different rules in different environments
Validators don't know about environments — they run once per `fluid validate` invocation against the static contract. If you need env-specific gating, structure the rule to read `contract.environments.<env>` and conditionally emit findings (e.g. "prod environment must declare audit logging"). Or wire it as an apply hook with a runner-set `DEPLOY_ENV` convention (the [apply-hook journey](./apply-hook.md) covers this).
:::

::: details Findings show up twice in the output
You have two validators emitting the same `code`. Validator names are namespaced by entry-point key (`extensions.<ep-name>: <code>`), but if two plugins both define `STEWARD_ID_MISSING`, the user sees two near-identical errors. Pick unique codes per rule.
:::

## Next

- [Apply hook](./apply-hook.md) — for runtime invariants that fire at deploy
- [Your own CI](./your-own-ci.md) — bundle pattern for CI templates (not validation rules)
- [Reference → Roles](../reference/roles.md) — what `Validator` inherits and what you override
- [Steward validator example](../examples/steward-validator.md) — the SDK's reference implementation of the same pattern
