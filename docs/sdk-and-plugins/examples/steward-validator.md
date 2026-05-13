# Example: `steward-validator` — a custom governance rule

A `Validator` plugin that fails any contract missing a data-steward identifier. Demonstrates how to encode governance/compliance rules that run automatically at `fluid validate`.

> **Source:** [`Agenticstiger/forge-cli-sdk` → `examples/steward-validator/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/steward-validator).

## What it does

Every fluid contract must declare `metadata.labels["principal.steward.id"]`. Optionally, `metadata.labels["principal.steward.email"]` for ops notifications. The validator emits an **error** if the id is missing, a **warning** if the email is missing.

```bash
fluid validate contract.fluid.yaml
# ✗ extensions.steward-required: error STEWARD_ID_MISSING:
#   Contract 'order-events' is missing the required label 'principal.steward.id'.
#   → Add metadata.labels['principal.steward.id'] with the employee identifier of the data steward.
```

When the contract is fixed:

```bash
fluid validate contract.fluid.yaml
# ✓ Contract valid against fluidVersion 0.7.3
```

Once installed (`pip install steward-validator`), the rule runs on **every** `fluid validate` invocation — your governance becomes part of the CI gate without each team having to configure anything.

## Layout

```
steward-validator/
├── pyproject.toml
├── src/steward_validator/
│   ├── __init__.py
│   └── validator.py               ← ~90 lines, full source below
├── tests/
│   └── test_validator.py          ← 97 lines, scenarios for the rule
└── demo.py
```

## `pyproject.toml`

```toml
[project]
name = "steward-validator"
version = "0.1.0"
description = "FLUID Validator example — fails contracts that don't declare a data steward"
requires-python = ">=3.10"
dependencies = ["data-product-forge-sdk>=0.9,<1"]

# Note the entry-point GROUP — different from CustomScaffold's:
[project.entry-points."fluid_build.validators"]
steward-required = "steward_validator.validator:StewardValidator"
```

The group is `fluid_build.validators` (for `Validator` plugins discovered at instantiation time). The CLI also has a `fluid_build.extension_validators` group for plugins that validate a sub-key of `contract.extensions` — different mechanism, covered in the [entry-points reference](../reference/entry-points.md).

## `src/steward_validator/validator.py`

```python
"""Steward Validator — fails any contract missing a data-steward identifier."""

from __future__ import annotations

from typing import Any, List, Mapping

from fluid_sdk import (
    ContractHelper,
    Finding,
    PluginMetadata,
    Validator,
)


class StewardValidator(Validator):
    """Fails the contract validation if a steward identifier is missing."""

    name = "steward-required"

    @classmethod
    def get_plugin_info(cls) -> PluginMetadata:
        return PluginMetadata(
            name=cls.name,
            role=cls.role,
            display_name="Steward Required Validator",
            description=(
                "Enforces that every contract declares "
                "metadata.labels['principal.steward.id']."
            ),
            version="0.1.0",
            author="FLUID SDK Examples",
            tags=["governance", "compliance"],
        )

    def plan(self, contract: Mapping[str, Any]) -> List[dict]:
        c = ContractHelper(contract)
        findings: List[Finding] = []

        labels = c.metadata.get("labels") or {}
        steward_id = labels.get("principal.steward.id")
        steward_email = labels.get("principal.steward.email")

        if not steward_id:
            findings.append(
                Finding(
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
                )
            )

        if steward_id and not steward_email:
            findings.append(
                Finding(
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
                )
            )

        return [f.to_action() for f in findings]
```

`Finding` is the SDK's structured-finding type. Severity is one of `info` / `warn` / `error` / `critical`. The CLI's exit code is derived from the maximum severity emitted across all validator plugins.

`Validator.plan(contract)` returns a list of `PluginAction` dicts (each `Finding.to_action()` produces one). The `Validator` base class's default `apply()` summarizes findings by severity and writes them to the validation report.

## Tests

```python
# tests/test_validator.py (excerpts)

class TestStewardValidator(PluginTestHarness):
    plugin_class = StewardValidator
    sample_contracts = [LOCAL_CONTRACT, STRICT_GOVERNANCE_CONTRACT]

    def test_missing_steward_id_is_error(self):
        plugin = self._instantiate()
        actions = plugin.plan(CONTRACT_WITHOUT_STEWARD)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert any(f["params"]["severity"] == "error" and
                   f["params"]["code"] == "STEWARD_ID_MISSING"
                   for f in findings)

    def test_missing_steward_email_is_warning(self):
        plugin = self._instantiate()
        actions = plugin.plan(CONTRACT_WITH_ID_NO_EMAIL)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert any(f["params"]["severity"] == "warn" and
                   f["params"]["code"] == "STEWARD_EMAIL_MISSING"
                   for f in findings)

    def test_fully_specified_contract_passes_clean(self):
        plugin = self._instantiate()
        actions = plugin.plan(CONTRACT_WITH_STEWARD_AND_EMAIL)
        findings = [a for a in actions if a["op"] == "emit_finding"]
        assert findings == []
```

## Run it

```bash
# In the steward-validator/ directory:
pip install -e ".[dev]"
pytest
# ============== 16 passed in 0.08s ===============
```

End-to-end against a real contract:

```bash
pip install data-product-forge steward-validator
fluid validate contract.fluid.yaml
# (auto-runs your validator alongside core schema validation)
```

If the contract lacks the steward id:

```text
✗ Validation failed
  Errors:
    - extensions.steward-required: STEWARD_ID_MISSING:
      Contract 'order-events' is missing the required label 'principal.steward.id'.

  Warnings:
    (none)
```

If only the email is missing:

```text
⚠ Validation passed with warnings
  Warnings:
    - extensions.steward-required: STEWARD_EMAIL_MISSING:
      Contract 'order-events' declares a steward id but no email — operations notifications will go nowhere.
```

## You'll know it worked when

- All tests pass under `pytest`.
- the `importlib.metadata.entry_points` one-liner above shows `steward-required` under `validators`.
- Running `fluid validate` against a contract **without** the steward id label exits non-zero with the structured error.
- Running against a contract **with** id but no email exits 0 with a warning.
- Running against a fully-specified contract exits 0, no findings.

## When **not** to use a `Validator`

If the check needs to run **at apply time** (not at author/validate time) — e.g., verifying a bundle digest hasn't drifted, or that an external secret has been resolved — use an apply hook instead. See [`apply-hook-prod-key-guard`](./apply-hook-prod-key-guard.md).

If the rule is **per-extension-block** (e.g., validating the shape of `contract.extensions.customScaffold`), use an extension validator via the `fluid_build.extension_validators` entry-point group — different mechanism, lighter weight. The [entry-points reference](../reference/entry-points.md) compares the two.

## Next

- [Apply-hook example](./apply-hook-prod-key-guard.md) — same shape but runs at `fluid apply`
- [Journeys → custom-validator](../journeys/custom-validator.md) — full walkthrough of governance plugin authoring
- [Reference → roles](../reference/roles.md) — what `Validator` inherits
