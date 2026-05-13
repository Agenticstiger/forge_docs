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

## CI/CD Integration

Run governance checks as a gate in your deployment pipeline:

```bash
# Fail the pipeline if any governance check is violated
fluid policy-check contract.fluid.yaml --strict --format json --output report.json
```

## See Also

- [GCP Provider](/providers/gcp) — GCP-specific IAM, policy tags, data masking
- [AWS Provider](/providers/aws) — AWS IAM policies, sovereignty, EventBridge
- [Snowflake Provider](/providers/snowflake) — Snowflake RBAC, warehouse grants
- [apply command](/cli/apply) — deploy with governance enforcement
- [CLI Reference](/cli/) — all available commands
- [Contributing](/contributing) — help improve governance features
