# Governance & Compliance

FLUID embeds governance directly into your data product contracts — access policies, data classification, and compliance checks all defined as code alongside your schema.

## Governance Commands

### `fluid policy-check`

Validate a contract against schema-driven governance policies.

```bash
fluid policy-check contract.fluid.yaml
```

| Option | Description | Default |
|--------|-------------|---------|
| `--env <name>` | Environment overlay (`dev`, `staging`, `prod`) | — |
| `--strict` | Treat warnings as errors | `false` |
| `--category <name>` | Filter checks: `sensitivity`, `access_control`, `data_quality`, `lifecycle`, `schema_evolution` | All |
| `--output`, `-o` | Output report to file | Console |
| `--format` | `rich`, `text`, or `json` | `rich` |
| `--show-passed` | Include passed checks in output | `false` |

**Example output:**
```
┌─ Policy Check Results ─────────────────────┐
│ ✅ sensitivity     3/3 passed              │
│ ✅ access_control  2/2 passed              │
│ ⚠️  data_quality   1 warning               │
│ ✅ lifecycle       1/1 passed              │
└─────────────────────────────────────────────┘
```

### `fluid policy-compile`

Compile `accessPolicy` declarations from a FLUID contract into provider-native IAM bindings.

```bash
fluid policy-compile contract.fluid.yaml --out runtime/policy/bindings.json
```

| Option | Description | Default |
|--------|-------------|---------|
| `--env <name>` | Environment overlay | — |
| `--out <path>` | Output path for compiled bindings | `runtime/policy/bindings.json` |

### `fluid policy-apply`

Apply compiled IAM bindings to the target cloud provider.

```bash
# Dry-run (default)
fluid policy-apply runtime/policy/bindings.json --mode check

# Actually enforce
fluid policy-apply runtime/policy/bindings.json --mode enforce
```

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | `check` (dry-run) or `enforce` (apply changes) | `check` |

## Defining Policies in Contracts

### Access Policies

Define who can access each data asset:

```yaml
exposes:
  - exposeId: customer_table
    kind: table
    accessPolicy:
      - role: READER
        members:
          - user:analyst@company.com
          - group:data-team@company.com
      - role: WRITER
        members:
          - serviceAccount:etl@project.iam.gserviceaccount.com
```

### Data Classification

Tag sensitive columns for automatic masking and access control:

```yaml
contract:
  schema:
    fields:
      - name: email
        type: STRING
        sensitivity: PII
      - name: credit_card
        type: STRING
        sensitivity: Financial
      - name: country
        type: STRING
        # No sensitivity tag = publicly accessible
```

### Data Quality Rules

```yaml
contract:
  quality:
    - field: email
      rule: not_null
    - field: price
      rule: positive
    - field: created_at
      rule: not_future
```

## Governance Workflow

```bash
# 1. Write your contract with access policies
# 2. Check governance compliance
fluid policy-check contract.fluid.yaml --strict

# 3. Compile to provider-native IAM
fluid policy-compile contract.fluid.yaml

# 4. Preview what would change
fluid policy-apply runtime/policy/bindings.json --mode check

# 5. Enforce in production
fluid policy-apply runtime/policy/bindings.json --mode enforce
```

## Policy Categories

| Category | What It Checks |
|----------|---------------|
| `sensitivity` | PII tags, data classification completeness |
| `access_control` | IAM policies, least-privilege, role definitions |
| `data_quality` | NOT NULL constraints, type validation, range checks |
| `lifecycle` | Retention policies, expiration, archival rules |
| `schema_evolution` | Breaking change detection, backward compatibility |

## Sovereignty enforcement modes (since 0.15.0)

A contract's `sovereignty` block declares where its data may live. `enforcementMode` decides what a violation *does*, and since `0.15.0` one function maps the mode onto a severity, applied consistently to every mode-sensitive check:

| `enforcementMode` | Severity | Effect |
|---|---|---|
| `strict` *(the schema default)* | ❌ error | [`fluid validate`](../cli/validate.md) exits 1; [`fluid plan --check-sovereignty`](../cli/plan.md#sovereignty-gate-since-0-15-0) blocks. |
| `advisory` | ⚠️ warning | Reported, does not block — though `fluid validate --strict` still promotes warnings to errors. |
| `audit` | ℹ️ info | Logged only. |

Three defaults also moved, in the stricter direction: the engine now reads the schema's own `enforcementMode: strict`, `dataResidency: true` and `crossBorderTransfer: false`. On `0.14.1` it defaulted to the permissive inverse of all three (advisory / false / true), so a contract that declared a policy and relied on the documented defaults was evaluated under the weakest possible settings — a strict GDPR contract with exposes in `eu-west-1` and `us-east-1` printed `PASS`, because `dataResidency` silently became false and the cross-border check was never entered. Declaring those keys explicitly restores the old evaluation.

Two carve-outs are deliberate rather than oversights:

- **`deniedRegions` is an error in every mode.** An operator naming a specific prohibition outranks a mode default, and `fluid validate` and `fluid plan` must block on the same contract or a product passes one stage and fails the next.
- **An unmappable region stays a warning even under `strict`.** "Unknown" is an inability to evaluate, not a violation, so a gap in the region table below cannot fail an otherwise valid deployment.

::: warning Behavior change in 0.15.0
`enforcementMode` had failed in **both** directions at once, and correcting it moves contracts both ways.

- The jurisdiction check — the only check that reads `jurisdiction`, the field whose stated purpose is validating `binding.location` against sovereignty intent — hardcoded warning severity, so it could not block in any mode. A `strict`, EU-declared contract with every expose on `us-east-1` validated clean on `0.14.1` and **now exits 1**.
- The cross-border mismatch hardcoded error severity, so it failed the build under `advisory`. `fluid validate` routes messages by their rendered ❌ / ⚠️ / ℹ️ prefix, which the returned boolean could not override. That contract **now warns** instead of failing.

`jurisdiction: Multi-Region` needs no action. It is a catch-all alongside `Global`, and check 3 skips both: no region resolves to `Multi-Region`, because it is not a place. Both are skipped at provision time and at query time alike.
:::

### The region → jurisdiction table is derived *(since 0.15.0)*

Verdicts change on contracts nobody edited, because the table those verdicts are computed from changed. 31 hand-written regions became 121 resolved, with none left resolving to `Global` or `Unknown`:

- **AWS** resolves through botocore's shipped `endpoints.json` — the vendor's own table, all eight partitions, GovCloud and the EU Sovereign Cloud included. New AWS regions now arrive by upgrading `boto3`, not by waiting for a FLUID release.
- **GCP and Azure** resolve through CSVs vendored from `dgl/cloud-regions` (ODbL-1.0, recorded in `NOTICE`), with a corrections map filling the rows upstream ships empty, so the table is complete whether or not the optional `boto3` is installed.

Two classes of false verdict go away:

- The hand-written table put **London in the EU**. A product declaring EU-only residency and deploying to `eu-west-2` or `europe-west2` reported clean; the UK left the EU in 2020, and those now fail. A `UK`-pinned contract bound to `eu-west-2` stops being a false positive.
- The jurisdiction check **skips any region whose jurisdiction is `Global`**, and `ap-southeast-1` (Singapore), `ap-northeast-2` (Seoul) and `asia-southeast1` were all typed `Global` — pass-anything wildcards against every declared jurisdiction. They no longer are.

This is **identity, not adequacy**: the UK and Switzerland hold GDPR adequacy decisions, but a contract asking for `jurisdiction: EU` has not asked for the UK. Adequacy belongs in `transferMechanisms`, which the schema already carries.

The AWS provider also kept a second table that had drifted from the canonical one on 16 regions — `eu-west-2` was `EU` there and `UK` in the engine, and every `ap-*` collapsed to one `APAC` — so `fluid validate` and the AWS provider could reach opposite verdicts on the same contract. It now delegates to the one table.

### Where sovereignty is enforced

| Stage | What it does |
|---|---|
| [`fluid validate`](../cli/validate.md) | Runs the policy engine on every contract; severity follows `enforcementMode`. |
| [`fluid plan --check-sovereignty`](../cli/plan.md#sovereignty-gate-since-0-15-0) | Opt-in and off by default. Provider hook, then the same policy engine; *(since 0.15.0)* **exits 1 on failure** instead of printing `PASS` for a check that never ran. |
| [`fluid generate iac`](../cli/generate-iac.md) / [`fluid apply`](../cli/apply.md) | The AWS provider refuses a binding outside the contract's `allowedRegions` or its declared jurisdiction. *(since 0.15.0)* That refusal is no longer swallowed by a best-effort handler, so the run exits 1 and **no module is written**; `deniedRegions` is honoured at all for the first time. |
| [`fluid mcp output-port serve`](mcp.md#caller-jurisdiction-enforcement-since-0-15-0) | *(since 0.15.0)* A pinned `jurisdiction` becomes a query-time gate on the **verified** caller jurisdiction — enforced by default, with the escape hatches in the contract rather than in a flag. |

## CI/CD Integration

Run governance checks as a gate in your deployment pipeline:

```bash
# Fail the pipeline if any governance check is violated
fluid policy-check contract.fluid.yaml --strict --format json --output report.json
```

## See Also

- [GCP Provider](/forge_docs/providers/gcp) — GCP-specific IAM, policy tags, data masking
- [AWS Provider](/forge_docs/providers/aws) — AWS IAM policies, sovereignty, EventBridge
- [Snowflake Provider](/forge_docs/providers/snowflake) — Snowflake RBAC, warehouse grants
- [apply command](/forge_docs/cli/apply) — deploy with governance enforcement
- [CLI Reference](/forge_docs/cli/) — all available commands
- [Contributing](/forge_docs/contributing) — help improve governance features
