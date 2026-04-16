# FLUID Forge Contract GPT Review Checklist

Use this checklist when reviewing or self-checking a draft. Report each item as `PASS`, `FAIL`, or `QUESTION`.

## 1. Schema And Version

- `fluidVersion` is `0.7.2` unless the user explicitly requested another version
- Top-level `kind`, `id`, `name`, `metadata`, and `exposes` are present
- Each tabular expose includes `binding` and `contract.schema`
- `contract.schema` is an array of columns, not an ad hoc object

## 2. Provider Binding

- `binding.platform` is used instead of `binding.provider`
- `binding.format` matches the provider target
- Provider-specific location fields are complete:
  - `local`: `path`
  - `gcp`: `project`, `dataset`, `table`
  - `aws`: `database`, `table`, `bucket`, `path`, `region`
  - `snowflake`: `account`, `database`, `schema`, `table`
- The draft does not mix provider shapes inside one expose

## 3. Governance And Compliance

- No sovereignty, privacy, IAM, retention, or AI governance values were invented
- If the user stated governance requirements, they appear in the correct block
- `policy.agentPolicy` appears only when AI usage rules were provided
- `sovereignty` appears only when jurisdiction or region constraints were provided

## 4. Missing Assumptions

- Unknown high-impact values are called out under `Open questions`
- The draft avoids pretending ambiguous fields are resolved
- Placeholders are clearly marked as placeholders

## 5. Output Quality

- The response is labeled `Draft` if validation has not been run
- The YAML appears before commentary
- `Assumptions`, `Open questions`, and `Validation next steps` are present
- Validation commands include both `fluid validate --strict` and `fluid plan --json`

## 6. Review Behavior

- For pasted contracts, explain likely failures before rewriting
- Prefer minimal corrections when only a few fields are wrong
- If the contract is broadly under-specified, ask follow-up questions instead of fabricating a full rewrite
