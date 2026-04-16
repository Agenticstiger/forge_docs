# FLUID Plan Reference

Use planning after validation to preview resource changes and provider mismatches.

## Primary Command

```bash
fluid plan contract.fluid.yaml --provider <provider> --json > plan.json
```

Use an explicit provider when reviewing a draft so the plan is unambiguous.

## What To Review In `plan.json`

- resources to create
- resources to modify
- resources to delete
- breaking changes
- estimated cost or provider impact

## Promotion Rule

A contract should not be treated as final until:

- `fluid validate contract.fluid.yaml --strict` passes
- the plan matches the intended provider and target resources
- there are no unexpected breaking changes or provider mismatches

## Common Reasons To Revise After Planning

- wrong provider selected
- incomplete location details
- unexpected deletes
- naming mismatches between contract intent and planned resources
