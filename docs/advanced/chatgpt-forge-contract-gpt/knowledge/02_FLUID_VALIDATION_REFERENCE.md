# FLUID Validation Reference

Use validation as the gate between a good draft and a trustworthy contract.

## Primary Command

```bash
fluid validate contract.fluid.yaml --strict
```

`--strict` matters because warnings should block the claim that a contract is ready.

## JSON Report Option

```bash
fluid validate contract.fluid.yaml --strict --format json > validation-report.json
```

## What Validation Should Catch

- YAML or JSON structure errors
- Missing required top-level fields
- FLUID version mismatches
- Provider configuration problems
- Incomplete or malformed data contract definitions
- SQL or dependency issues where supported
- Security and access policy issues where supported

## How To Interpret Results

- If validation fails, the contract remains `Draft`
- If validation passes with warnings in non-strict mode, do not call it final
- In this workflow, only a strict pass is eligible for final review

## Review Habit

When a contract is reviewed in chat but not yet validated:

- call out likely failures
- include the validation command
- avoid finality language
