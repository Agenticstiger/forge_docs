# Snowflake Quickstart

This is the canonical first-time Snowflake path for Fluid Forge.

Use it in two stages:

- **Minimal starter path:** native SQL with the [`examples/snowflake/smoke`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/smoke) contract so you can get to a first successful deployment quickly.
- **Enterprise recommended path:** a dbt-snowflake workflow like [`examples/snowflake/billing_history`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/billing_history), with explicit environment-specific warehouse, database, schema, and role settings.

## Recommended Snowflake Defaults

For team environments, make these explicit in each environment:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_ROLE`

For production and CI, prefer non-password auth in this order:

- key-pair auth via `SNOWFLAKE_PRIVATE_KEY_PATH`
- OAuth via `SNOWFLAKE_OAUTH_TOKEN`
- SSO via `SNOWFLAKE_AUTHENTICATOR` for interactive local use

Password auth is still supported as a fallback, but it should not be the default automation path.

## Minimal Starter Path

Start with the smoke example when you want the smallest path that still proves the full deployment cycle:

```bash
git clone https://github.com/Agenticstiger/forge-cli.git
cd forge-cli/examples/snowflake/smoke
```

Export your Snowflake settings:

```bash
export SNOWFLAKE_ACCOUNT="your-account"
export SNOWFLAKE_USER="your-user"
export SNOWFLAKE_WAREHOUSE="DEV_TRANSFORM_WH"
export SNOWFLAKE_DATABASE="DEV_ANALYTICS"
export SNOWFLAKE_SCHEMA="COMMUNITY_SMOKE"
export SNOWFLAKE_ROLE="TRANSFORMER"
export SNOWFLAKE_PRIVATE_KEY_PATH="/secure/path/to/snowflake_user_key.p8"
export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="optional-passphrase"
```

If you are doing an ad-hoc local smoke test and do not have key-pair or OAuth configured yet, password auth still works as a fallback. For non-interactive runs, use key-pair or OAuth rather than browser SSO.

Run the happy path:

```bash
fluid auth status snowflake
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml --strict
```

What each command is doing:

- `fluid auth status snowflake` validates the same Snowflake connection model the provider uses for real execution.
- `fluid validate` checks the contract shape against the FLUID schema.
- `fluid plan` previews the Snowflake objects and SQL actions before execution.
- `fluid apply` creates the database/schema/table path and runs the embedded SQL build.
- `fluid verify --strict` checks the deployed Snowflake table against the contract schema and fails on drift.

## Enterprise Recommended Path

For production teams, prefer a dbt-snowflake workflow:

- keep transformation logic in dbt
- keep Snowflake runtime settings explicit per environment
- use key-pair or OAuth for automation instead of password auth
- run `validate`, `plan`, `apply`, and `verify` in CI
- keep governance and access policy checks in the same contract review flow

The repo example for that pattern is [`examples/snowflake/billing_history`](https://github.com/Agenticstiger/forge-cli/tree/main/examples/snowflake/billing_history).

Recommended review/deploy sequence:

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
fluid policy-check contract.fluid.yaml
fluid policy-compile contract.fluid.yaml --env dev --out runtime/policy/bindings.json
fluid apply contract.fluid.yaml --yes
fluid verify contract.fluid.yaml --strict
fluid test contract.fluid.yaml
```

## Governance Notes

Use the commands this way:

- `fluid policy-check` validates governance declarations in the contract.
- `fluid policy-compile` turns `accessPolicy` rules into Snowflake RBAC bindings.
- `fluid policy-apply` applies those compiled bindings.
- Snowflake governance during `apply` covers object-level controls such as descriptions, tags, and masking policies.
- `fluid verify` checks deployed schema and drift. It is not a full RBAC or entitlement audit.

## Where To Go Next

- Provider reference: [Snowflake Provider](/providers/snowflake)
- Team review flow: [Snowflake Team Collaboration](/walkthrough/snowflake)
- Local-first onboarding: [Getting Started](/getting-started/)
