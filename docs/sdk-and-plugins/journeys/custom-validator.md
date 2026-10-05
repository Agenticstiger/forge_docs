# You have governance rules, no problem

Your platform/security/data-governance team has rules: every Gold data product must declare a steward; the steward's email must match `@my-org.example.com`; cost-center labels are required; classification tags must come from a controlled vocabulary. You want these rules to run **at contract-author time** — `fluid validate` — so they fail fast in the IDE, on every commit, and in CI, before anyone tries to deploy.

This guide walks through authoring a `Validator` plugin from scratch. By the end you'll have:

- A `Validator` subclass that inspects a contract and emits **structured `Finding` records** (info / warn / error / critical).
- A package on PyPI (or your private index) that any team can `pip install`, after which your rules run on each `fluid validate` in that environment.
- A test that runs your rules against sample contracts, good and bad, with no manual QA.

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
              │   ├── StewardRequired                      │ ← yours
              │   ├── CostCenterRequired                   │ ← yours
              │   ├── DataClassificationFromVocab          │ ← yours
              │   └── (any other validators on PyPI / pip) │
              └─────────────────┬──────────────────────────┘
                                ▼
                       findings rolled up,
                       exit code = max severity
```

Validators are **discovered automatically** by `fluid validate`. There is no per-product opt-in: if the package is installed and the entry point is allowed (see `FLUID_PLUGINS_ALLOWLIST` in the [trust model](../reference/trust-model.md)), it runs.

## Step 0 — see the result first

Output from CLI 0.18.1 with the three validators from this guide installed. The contract is a valid 0.7.5 contract with a root-level `labels:` map; only the labels differ.

A contract with no labels:

```bash
fluid validate contract.fluid.yaml
```

```text
❌ Invalid FLUID contract (2 error(s)) (schema v0.7.5)
Validation completed in 0.012s

Validation Errors:
==================
 1.  COST_CENTER_MISSING: Contract 'bronze.demo.my_first_product_v1' is missing 
label 'cost-center'. (at labels["cost-center"])
 2.  STEWARD_ID_MISSING: Contract 'bronze.demo.my_first_product_v1' is missing 
the required label 'principal.steward.id'. (at labels["principal.steward.id"])
```

Exit code `1`. With every label present and valid:

```text
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.005s
```

With a steward id but no steward email, the contract passes with a warning (exit code `0`):

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.005s

Validation Warnings:
====================
 1.  STEWARD_EMAIL_MISSING: Contract 'bronze.demo.my_first_product_v1' declares 
a steward id but no email. (at labels["principal.steward.email"])
```

Severity drives the exit code: `error` and `critical` findings fail validation (exit `1`), `warn` findings are listed and exit `0`, and `fluid validate --strict` also exits `1` on warnings. `info` findings are not printed; the CLI writes them to its debug log only.

As of 0.18.1 the text output renders each finding as `<CODE>: <message> (at <path>)`. Two details to know:

- The finding's `remediation` text is not printed, in text or in `--format json`. Put the fix in the `message` if the reader needs it.
- The plugin name prefix is dropped from the text output (note the double space after `1.`). `--format json` keeps it as `[steward-required] STEWARD_EMAIL_MISSING: ...`, so parse the JSON form if a script needs to know which validator spoke.

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
dependencies = ["data-product-forge-sdk>=0.10,<1"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

# Each validator is registered separately under the same group.
# Once installed, `fluid validate` runs all three rules.
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
"""StewardRequired - every contract MUST declare a steward identifier."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import ContractHelper, Finding, PluginMetadata, Validator


class StewardRequired(Validator):
    """Every contract must carry labels['principal.steward.id']."""

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

        labels = c.labels  # the contract's top-level `labels:` map
        steward_id = labels.get("principal.steward.id")
        steward_email = labels.get("principal.steward.email")

        if not steward_id:
            findings.append(Finding(
                severity="error",
                code="STEWARD_ID_MISSING",
                message=f"Contract {c.id!r} is missing the required label 'principal.steward.id'.",
                path='labels["principal.steward.id"]',
                remediation="Add labels['principal.steward.id'] with the identifier of the data steward.",
            ))

        if steward_id and not steward_email:
            findings.append(Finding(
                severity="warn",
                code="STEWARD_EMAIL_MISSING",
                message=f"Contract {c.id!r} declares a steward id but no email.",
                path='labels["principal.steward.email"]',
                remediation="Add labels['principal.steward.email'] with the steward's email.",
            ))

        if steward_email and not steward_email.endswith("@my-org.example.com"):
            findings.append(Finding(
                severity="error",
                code="STEWARD_EMAIL_DOMAIN",
                message=f"Steward email {steward_email!r} must be on the @my-org.example.com domain.",
                path='labels["principal.steward.email"]',
                remediation="Use the steward's official my-org email address.",
            ))

        return [f.to_action() for f in findings]
```

`Finding` is the SDK's structured-finding type, with `severity`, `code`, `message`, `path` and `remediation`.

Labels live at the **root** of the contract (`labels:`, next to `id` and `name`), and `ContractHelper.labels` reads them. `metadata` is a closed block in the contract schema, so a `metadata.labels` map fails `fluid validate` with `metadata: Additional properties are not allowed ('labels' was unexpected)`. A validator that reads `metadata.labels` therefore asks for something no valid contract can contain.

The CLI prints each finding's `code`, `message` and `path` (see Step 0). Write the `message` so it says what is wrong and how to fix it, because `remediation` is not shown by `fluid validate`.

## Step 4 — write the second and third validators

The pattern is identical. Different rule, different `code`s.


::: details src/my_org_validators/cost_center.py — every product must declare a cost center
```python
"""CostCenterRequired - every contract MUST carry a cost-center label."""

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
            description="Every contract must declare labels['cost-center'].",
            version="0.1.0",
            tags=["governance", "finops"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        cost_center = c.labels.get("cost-center")

        if not cost_center:
            findings.append(Finding(
                severity="error",
                code="COST_CENTER_MISSING",
                message=f"Contract {c.id!r} is missing label 'cost-center'.",
                path='labels["cost-center"]',
                remediation=(
                    "Add labels['cost-center'] with your team's "
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
                path='labels["cost-center"]',
                remediation="Use the format `cc-` followed by 4 digits (e.g. cc-1234).",
            ))

        return [f.to_action() for f in findings]
```
:::



::: details src/my_org_validators/classification.py — controlled vocabulary for data classifications
```python
"""ClassificationFromVocab - classification labels must come from a controlled list."""

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
                "labels['data-classification'] must be one of: "
                + ", ".join(sorted(_ALLOWED_CLASSIFICATIONS))
            ),
            version="0.1.0",
            tags=["governance", "data-classification"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        classification = c.labels.get("data-classification")

        # Gold/CDP products MUST declare a classification; SDP/Bronze MAY.
        if not classification and c.product_type == "CDP":
            findings.append(Finding(
                severity="error",
                code="CLASSIFICATION_REQUIRED_FOR_CDP",
                message=(
                    f"Consumer-Aligned Data Product {c.id!r} must declare "
                    f"a data-classification label."
                ),
                path='labels["data-classification"]',
                remediation=(
                    "Add labels['data-classification'] = one of: "
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
                path='labels["data-classification"]',
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
from fluid_sdk.testing import ValidatorTestHarness, LOCAL_CONTRACT
from my_org_validators.steward import StewardRequired


# Fixture contracts. Labels sit at the contract root, next to `id` and `name`.
CONTRACT_NO_STEWARD = {"id": "p1", "labels": {}}
CONTRACT_GOOD_STEWARD = {
    "id": "p2",
    "labels": {
        "principal.steward.id": "emp-12345",
        "principal.steward.email": "alice@my-org.example.com",
    },
}
CONTRACT_STEWARD_NO_EMAIL = {
    "id": "p3",
    "labels": {"principal.steward.id": "emp-12345"},
}
CONTRACT_WRONG_DOMAIN = {
    "id": "p4",
    "labels": {
        "principal.steward.id": "emp-12345",
        "principal.steward.email": "alice@example.com",
    },
}


class TestStewardRequired(ValidatorTestHarness):
    plugin_class = StewardRequired
    # The harness refuses to run against nothing: give it at least one contract.
    sample_contracts = [LOCAL_CONTRACT, CONTRACT_GOOD_STEWARD]

    def _codes(self, contract):
        actions = self.get_plugin().plan(contract)
        return {
            a["params"]["code"] for a in actions if a["op"] == "emit_finding"
        }

    def test_missing_steward_id_is_error(self):
        assert "STEWARD_ID_MISSING" in self._codes(CONTRACT_NO_STEWARD)

    def test_steward_id_present_no_email_is_warning(self):
        assert self._codes(CONTRACT_STEWARD_NO_EMAIL) == {"STEWARD_EMAIL_MISSING"}

    def test_wrong_email_domain_is_error(self):
        assert self._codes(CONTRACT_WRONG_DOMAIN) == {"STEWARD_EMAIL_DOMAIN"}

    def test_fully_specified_contract_is_clean(self):
        assert self._codes(CONTRACT_GOOD_STEWARD) == set()
```

Run it:

```bash
pip install -e ".[dev]"
pytest
```

```text
.........................                                                [100%]
25 passed in 0.23s
```

The inherited `ValidatorTestHarness` tests plus your four scenarios all run. `self.get_plugin()` returns a fresh instance of `plugin_class`. Repeat the pattern for the other two validators.

::: warning Set `sample_contracts`
`ValidatorTestHarness` fails `test_sample_contracts_present` when `sample_contracts` is empty, because its plan and apply checks would pass against nothing. Give it at least one contract, such as `LOCAL_CONTRACT`.
:::

## Step 6 — wire it into your contracts

```bash
# In any product team's environment:
pip install data-product-forge my-org-validators

# Validators auto-discovered. No contract changes needed.
fluid validate contract.fluid.yaml
```

That's the whole user surface. Once `pip install my-org-validators` resolves on a developer's machine (or in CI), the contracts they validate run the rules. Onboarding a new team is a `pip install`.

::: danger Install private plugins from your private index
`my-org-validators` is a private name. With only PyPI configured, `pip install my-org-validators` asks a public index for it, and anyone can register that name there. A plugin runs inside `fluid validate` with the permissions of whoever runs it. Install it from your own index: one mirror that proxies PyPI, set with `--index-url` or `PIP_INDEX_URL`, with no extra index and the version pinned. pip picks the highest version across every index it is given, so a private index added next to PyPI with `--extra-index-url` does not protect the name.
:::

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
   ```yaml
   - run: pip install --index-url "<your-private-index-url>" "data-product-forge==0.18.1" "my-org-validators==<version>"
   - run: fluid validate contract.fluid.yaml --strict
     env:
       FLUID_PLUGINS_ALLOWLIST: "steward-required,cost-center-required,classification-from-vocab,local"
   ```

   `FLUID_PLUGINS_ALLOWLIST` takes entry-point names, and only the names listed load, so a package that lands in the CI environment by another route is never imported. It removes every plugin it omits, the providers `data-product-forge` ships included (`fluid plugins --role provider` shows each as `BLOCKED`), so name the provider your job binds to as well; `local` is the example here. See the [trust model](../reference/trust-model.md#operator-governance-—-allowlist-and-blocklist).

## You'll know it worked when

- `fluid plugins list --role validator` lists all three validators as `allowed` (or the `importlib.metadata.entry_points(group='fluid_build.validators')` one-liner returns them).
- A contract missing `principal.steward.id` fails `fluid validate` with `STEWARD_ID_MISSING`.
- A contract with `steward.id` but no `steward.email` passes `fluid validate` with a `STEWARD_EMAIL_MISSING` warning.
- A contract with a steward email outside `@my-org.example.com` fails.
- All three validators run when `fluid validate` runs, with no opt-in in the contract.
- `fluid validate --strict` exits `1` on a warning too. Your team decides whether to set `--strict` in CI.

## When **not** to use this pattern

- **For schema shape that the core validator already handles.** If your rule is "field X must be a string," the core JSON-Schema validation in `fluid validate` already catches it. Validators are for **policy** on top of shape.
- **For invariants that depend on runtime state.** "The deploy key env var must be set" can't be checked at validate time because the env var isn't set on the contract author's machine yet. That's an [apply hook](./apply-hook.md).
- **For checks that need network access.** A validator's `plan(contract)` receives the contract and nothing else, so it cannot see which `fluid validate` flags were passed, and `fluid validate` is meant to run offline. A rule that calls an external service (for example "verify this label is in our service catalog") belongs in CI as its own step, or in an apply hook.

## Common gotchas

::: details The validator doesn't run
Same pattern as the quickstart: `pip install -e .` after editing the entry-points block. Then run `fluid plugins list --role validator` to confirm the registration.
:::

::: details The validator runs but findings don't show up in the CLI output
`info` findings are written to the CLI's debug log and are not part of the validation output, with or without `--verbose`. Use `warn` for a finding the reader should see.
:::

::: details I want different rules in different environments
Validators run once per `fluid validate` invocation against the contract as written. If you need env-specific gating, read the contract's `environments` map (`ContractHelper.environments`) and emit findings conditionally (for example "prod environment must declare audit logging"). That map is data for your plugin: `fluid plan` and `fluid apply` do not read it, and each entry accepts only `metadata`, `exposes`, `tags` and `labels`. Or wire the check as an apply hook, which receives the resolved `--env` (the [apply-hook journey](./apply-hook.md) covers this).
:::

::: details Findings show up twice in the output
You have two validators emitting the same `code`. The JSON output prefixes each finding with the entry-point name (`[steward-required] STEWARD_ID_MISSING: ...`), but the text output drops that prefix, so two plugins that both define `STEWARD_ID_MISSING` produce two near-identical lines. Pick unique codes per rule.
:::

## Next

- [Apply hook](./apply-hook.md) — for runtime invariants that fire at deploy
- [Your own CI](./your-own-ci.md) — bundle pattern for CI templates (not validation rules)
- [Reference → Roles](../reference/roles.md) — what `Validator` inherits and what you override
- [Steward validator example](../examples/steward-validator.md) — the SDK's reference implementation of the same pattern
