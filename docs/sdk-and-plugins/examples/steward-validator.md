# Example: `steward-validator` — a custom governance rule

A `Validator` plugin that fails any contract missing a data-steward identifier. It shows how to encode a governance rule that runs at `fluid validate`.

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/steward-validator/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/steward-validator). This page differs from the upstream example in one place: it reads the contract's root `labels:` map, because a contract that declares `metadata.labels` does not pass `fluid validate` (see below).

## What it does

A contract must declare `labels["principal.steward.id"]`. Optionally, `labels["principal.steward.email"]` carries the steward's email for ops notifications. The validator emits an **error** if the id is missing, a **warning** if the email is missing, and an **error** if the email is outside `@my-org.example.com`.

Output from CLI 0.18.1 for a valid 0.7.5 contract with no steward label:

```bash
fluid validate contract.fluid.yaml
```

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
Validation completed in 0.005s

Validation Errors:
==================
 1.  STEWARD_ID_MISSING: Contract 'bronze.demo.my_first_product_v1' is missing 
the required label 'principal.steward.id'. (at labels["principal.steward.id"])
```

With a steward id and no email, the contract is valid and the finding is a warning (exit code `0`; `--strict` makes it exit `1`):

```text
✅ Valid FLUID contract (schema v0.7.5)
⚠️  1 warning(s)
Validation completed in 0.136s

Validation Warnings:
====================
 1.  STEWARD_EMAIL_MISSING: Contract 'bronze.demo.my_first_product_v1' declares 
a steward id but no email. (at labels["principal.steward.email"])
```

With the id and a `@my-org.example.com` email, the output is:

```text
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.282s
```

Once installed (`pip install steward-validator`), the rule runs on each `fluid validate` in that environment, so the rule becomes part of the CI gate without each team configuring anything.

::: warning Why `labels`, not `metadata.labels`
The contract schema closes `metadata` to `provenance`, `layer`, `productType`, `classification`, `experimental`, `owner`, `createdAt`, `businessContext` and `tags`. A contract with `metadata.labels` fails with `metadata: Additional properties are not allowed ('labels' was unexpected)`. Labels are a root-level map: `labels:` next to `id` and `name`. A validator that insists on `metadata.labels` reports an error that no valid contract can fix.
:::

## Layout

```text
steward-validator/
├── pyproject.toml
├── src/steward_validator/
│   ├── __init__.py
│   └── validator.py               ← full source below
├── tests/
│   └── test_validator.py          ← scenarios for the rule
└── demo.py
```

## `pyproject.toml`

```toml
[project]
name = "steward-validator"
version = "0.1.0"
description = "FLUID Validator example — fails contracts that don't declare a data steward"
requires-python = ">=3.10"
dependencies = ["data-product-forge-sdk>=0.10,<1"]

# Note the entry-point GROUP — different from CustomScaffold's:
[project.entry-points."fluid_build.validators"]
steward-required = "steward_validator.validator:StewardValidator"
```

The group is `fluid_build.validators` (for `Validator` plugins). The CLI also has a `fluid_build.extension_validators` group for plugins that validate a sub-key of `contract.extensions`. That is a different mechanism, covered in the [entry-points reference](../reference/entry-points.md).

## `src/steward_validator/validator.py`

```python
"""Steward validator: fails any contract missing a data-steward identifier."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import ContractHelper, Finding, PluginMetadata, Validator


class StewardValidator(Validator):
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

`Finding` is the SDK's structured-finding type. Severity is one of `info` / `warn` / `error` / `critical` — the `Severity` str-enum added in SDK 0.10.0, whose `Severity.coerce` treats an unrecognised severity as `error`. In `fluid validate` 0.18.1, `error` and `critical` findings fail the validation, `warn` findings are listed as warnings, and `info` findings go to the debug log only. The `remediation` text is not part of the printed output, so put the fix in the `message` when the reader needs it.

`Validator.plan(contract)` returns a list of `PluginAction` dicts (each `Finding.to_action()` produces one, with `op` equal to `emit_finding`). The CLI translates them into validation errors and warnings.

## Tests

```python
from fluid_sdk.testing import ValidatorTestHarness, LOCAL_CONTRACT
from steward_validator.validator import StewardValidator

CONTRACT_NO_STEWARD = {"id": "p1", "labels": {}}
CONTRACT_GOOD_STEWARD = {"id": "p2", "labels": {
    "principal.steward.id": "emp-12345",
    "principal.steward.email": "alice@my-org.example.com"}}
CONTRACT_STEWARD_NO_EMAIL = {"id": "p3", "labels": {"principal.steward.id": "emp-12345"}}
CONTRACT_WRONG_DOMAIN = {"id": "p4", "labels": {
    "principal.steward.id": "emp-12345",
    "principal.steward.email": "alice@gmail.com"}}


class TestStewardValidator(ValidatorTestHarness):
    plugin_class = StewardValidator
    sample_contracts = [LOCAL_CONTRACT, CONTRACT_GOOD_STEWARD]

    def _codes(self, contract):
        actions = self.get_plugin().plan(contract)
        return {a["params"]["code"] for a in actions if a["op"] == "emit_finding"}

    def test_missing_steward_id_is_error(self):
        assert "STEWARD_ID_MISSING" in self._codes(CONTRACT_NO_STEWARD)

    def test_steward_id_present_no_email_is_warning(self):
        assert self._codes(CONTRACT_STEWARD_NO_EMAIL) == {"STEWARD_EMAIL_MISSING"}

    def test_wrong_email_domain_is_error(self):
        assert self._codes(CONTRACT_WRONG_DOMAIN) == {"STEWARD_EMAIL_DOMAIN"}

    def test_fully_specified_contract_is_clean(self):
        assert self._codes(CONTRACT_GOOD_STEWARD) == set()
```

`ValidatorTestHarness` (SDK 0.10.0) runs the generic plugin invariants plus validator-specific conformance against each contract in `sample_contracts`. It fails with `test_sample_contracts_present` if that list is empty. `self.get_plugin()` returns a fresh instance of your `plugin_class`.

## Run it

```bash
# In the steward-validator/ directory:
pip install -e ".[dev]"
pytest
```

```text
.........................                                                [100%]
25 passed in 0.19s
```

End-to-end against a real contract:

```bash
pip install data-product-forge steward-validator
fluid plugins list --role validator
fluid validate contract.fluid.yaml
```

`fluid plugins list --role validator` shows the plugin and the package it came from:

```text
🔌 Installed FLUID plugins (by role):

  validator  (1)
    • steward-required             allowed
      from=my-org-validators 0.1.0
```

(Here the package was `my-org-validators`; yours shows `steward-validator`.) `fluid validate` then runs your validator alongside core schema validation.

## You'll know it worked when

- All tests pass under `pytest`.
- `fluid plugins list --role validator` shows `steward-required`.
- `fluid validate` on a contract **without** the steward id label exits `1` with `STEWARD_ID_MISSING`.
- `fluid validate` on a contract with the id but no email exits `0` with a `STEWARD_EMAIL_MISSING` warning.
- `fluid validate` on a fully specified contract exits `0` with no findings.

## When **not** to use a `Validator`

If the check needs to run **at apply time** (not at author/validate time), for example verifying that an external secret has been resolved, use an apply hook. See [`apply-hook-prod-key-guard`](./apply-hook-prod-key-guard.md).

If the rule is **per-extension-block** (for example validating the shape of `contract.extensions.customScaffold`), use an extension validator via the `fluid_build.extension_validators` entry-point group. The [entry-points reference](../reference/entry-points.md) compares the two.

## Next

- [Apply-hook example](./apply-hook-prod-key-guard.md) — same shape but runs at `fluid apply`
- [Journeys → custom-validator](../journeys/custom-validator.md) — full walkthrough of governance plugin authoring
- [Reference → roles](../reference/roles.md) — what `Validator` inherits
