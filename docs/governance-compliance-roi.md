---
title: "Governance, Compliance & the Business Case"
description: "The audit-and-trust story for the people who sign off on data products: how governance is declared in the contract, gated in CI, enforced by the apply and checked by verify, with a per-provider enforcement matrix and a qualitative business case."
---

# Governance, Compliance & the Business Case

**Governance in Fluid Forge is not a phase you bolt on after the data ships.** It's declared in the same `contract.fluid.yaml` as the schema — who may read it (`accessPolicy`), which AI models may read it (`exposes[].policy.agentPolicy`), and where the data may physically live (`sovereignty`) — checked in CI *before* anything deploys, provisioned as each cloud's own controls where the provider supports them, and checked against the live platform by `fluid verify` afterwards. This page is the audit-and-trust story written for the people who sign off on it.

> **Why it matters**
> For a CDO or compliance lead, the question is never "does the tool have a governance feature?" — it's "can I prove, on demand, who could read what, why it was allowed, and that nothing changed between review and deploy?" Forge answers that with artifacts you already control: a versioned contract that declares the rules, a CI gate that rejects violations before they ship, a plan bound by digest to what apply runs, and a `verify` report that compares the live platform with the contract. Who read what is in your cloud's own audit log, under the identities the contract granted. Governance becomes something you *ship and prove*, not an audit you scramble to pass.

::: tip Two ways to read this page
**Executives (CDO, governance, security leads):** skim [The trust story in one line](#the-trust-story-in-one-line), [the enforcement matrix](#the-honest-provider-enforcement-matrix), and [the business case](#the-business-case-qualitative). That's the brief.
**Engineers & security reviewers:** [What governance lives in the contract](#what-governance-lives-in-the-contract), [the compliance mapping](#mapping-forge-to-compliance-frameworks), and [how policy gets applied](#how-policy-gets-applied-the-cli-path) give you the exact fields and commands that prove each row.
This mirrors the dual-audience framing in [why.md](/forge_docs/why.html).
:::

## The trust story in one line

`fluid validate → fluid plan → fluid apply`, bound by cryptographic digests.

`fluid plan` emits a `bundleDigest` and a `planDigest` into `plan.json`. `fluid apply` re-verifies *both* before it runs a single line of DDL. A `plan.json` that was tampered with between review and deploy is rejected outright — the apply never starts. That is the difference between governance that is *shift-left* (the breaking change or the unauthorized grant surfaces at `fluid validate` in code review) and governance that is an *after-the-fact audit* (you discover the drift weeks later, in production, at 3am).

The same contract that earns *human* trust — schema, sensitivity, freshness SLOs, lineage, access rules — is exactly what an AI agent needs to consume the product safely. One artifact, two consumers, the same declared rules. (See the consumer companion page, [Consume a data product](/forge_docs/data-products/consume.html).)

## What governance lives in the contract

Five declarations carry the governance surface. All are reviewed, versioned and validated with the schema. What each one becomes depends on the cloud; the [enforcement matrix](#the-honest-provider-enforcement-matrix) has the detail.

| Declaration | Field | What it governs | Enforced by |
|---|---|---|---|
| **Access** | `accessPolicy.grants[]` | *Who* (people and service principals) may do what — `read`, `select`, `write`, `admin`, … | `fluid apply`: dataset IAM members on GCP. On AWS access is the binding's Lake Formation grants. Not emitted on Snowflake |
| **Column restrictions** | `exposes[].policy.authz.columnRestrictions` | Which readers may not see which columns | `fluid apply`: Data Catalog policy tags on GCP, Lake Formation excluded columns on AWS; checked by `fluid verify` |
| **Sensitivity and masking** | `schema[].sensitivity`, `exposes[].policy.privacy.masking` | *What's sensitive*, and how its values are treated before they land | `fluid policy-check` requires masking for `pii`/`phi` columns; the DuckDB acquisition runner applies masking at landing; `fluid verify` fails cleartext; the MCP output port redacts tagged columns |
| **Agent access** | `exposes[].policy.agentPolicy` | *Which AI models* may read *this expose*, for which use cases, with what token caps | `fluid mcp output-port serve`, on each tool call |
| **Sovereignty** | `sovereignty` | *Where* data may live — jurisdiction, allowed/denied regions, cross-border transfer | `fluid validate` and `fluid plan --check-sovereignty`; `fluid generate iac` and `fluid apply` on AWS and GCP |

> **Honesty note — placement matters.** `agentPolicy` lives **per-expose** at `exposes[].policy.agentPolicy`, so each expose carries its own AI-access boundary. A contract that puts `agentPolicy` at the **contract root** fails schema validation. Likewise, there is **no top-level `security:` block** in the current schema (v0.7.5) — the contract root is closed, and a `security:` key fails `fluid validate`. If a draft you inherit has either, it never passed validation.

→ Full treatment: [Governance & Policy](/forge_docs/concepts/governance-policy.html) (access, sensitivity, sovereignty, audit) and [Agent Policy](/forge_docs/concepts/agent-policy.html) (the per-expose AI gate + runtime enforcement).

## Mapping Forge to compliance frameworks

> **Why it matters**
> Your auditors don't care which YAML key Forge uses. They care which *control* it supports. This table is the translation layer between your compliance obligations and the contract fields that back them — the rows you can paste into an adoption brief or a SOC 2 readiness doc.

`sovereignty.regulatoryFramework` records which regimes govern the product, from a fixed enum (`GDPR`, `CCPA`, `CPRA`, `HIPAA`, `PIPEDA`, `LGPD`, `PDPA`, `POPIA`, `DPA`, `APPI`). The codes are declarative: no code switches on a rule of its own, and `SOX` or `SOC2` fail `fluid validate`. The controls an auditor asks about come from the fields below.

| Obligation | Forge supports these controls | Contract field + command |
|---|---|---|
| **GDPR** (residency, minimisation) | Residency refused outside the declared jurisdiction; PII columns must declare masking; masked values land treated | `sovereignty` (`jurisdiction`, regions, `crossBorderTransfer`), checked by `fluid validate` and, on AWS and GCP, `fluid apply`; `sensitivity: pii` + `policy.privacy.masking`, checked by `fluid policy-check` and `fluid verify` |
| **HIPAA** (PHI access) | PHI columns must declare masking; column restrictions keep named readers off them; encryption at rest with a managed key (0.7.6 preview) | `sensitivity: phi`, `policy.authz.columnRestrictions`, `binding.encryption.kms`; checked by `fluid policy-check` and `fluid verify` |
| **CCPA / CPRA** | As for GDPR: tagging, masking at landing, access grants | `sensitivity`, `policy.privacy.masking`, `accessPolicy.grants[]` |
| **Change management** (SOX, SOC 2 evidence) | The reviewed plan is what runs: `fluid apply` refuses a `plan.json` whose digest no longer matches; a plan that destroys data needs `--allow-data-loss`; `fluid verify` reports drift from the contract | `fluid plan` → `fluid apply plan.json`, `fluid verify --strict` |
| **Agent access logging** | The MCP output port writes a `data_access` record for each allow and deny, with the policy digest that decided it | `exposes[].policy.agentPolicy`; records under `FLUID_AUDIT_ROOT` |

> **Framing, deliberately:** Forge **supports these controls** — it gives you the declarations, the CI gate, and the native audit trail that an auditor asks for. It does **not** *certify* you compliant. Compliance is an organizational outcome; Forge is the tooling that makes the technical evidence cheap to produce and hard to fake.

→ Detail: [`sovereignty.regulatoryFramework`](/forge_docs/concepts/governance-policy.html#compliance-frameworks).

## The honest provider enforcement matrix

> **Why it matters**
> This is the table that gets a tool thrown out of a procurement review when it's wrong. Enforcement is not uniform across clouds: the same field is a native control on one cloud and is not read on another. Here is what `fluid apply` provisions on 0.18.1, field by field.

| Capability | AWS | GCP / BigQuery | Snowflake |
|---|---|---|---|
| **Access grants** | ✅ `binding.governance.lakeFormation.grants`. `accessPolicy.grants` is not emitted; `fluid validate` warns when an aws binding has no Lake Formation grants | ✅ `accessPolicy.grants` as non-authoritative `google_bigquery_dataset_iam_member` (since 0.17.0) | ❌ Not emitted from contract fields |
| **Column restrictions** (`columnRestrictions`, 0.7.5) | ✅ Lake Formation excluded columns on each `SELECT` grant; verified by `fluid verify` | ✅ Data Catalog policy tags with fine-grained readers (since 0.17.0); verified by `fluid verify` | ❌ Not read |
| **Row filters** | ✅ `aws_lakeformation_data_cells_filter` from `binding.governance.lakeFormation` | ❌ Row-level security not emitted | ❌ Not read from contract fields |
| **Masking at landing** (`policy.privacy.masking`) | ✅ DuckDB-landed data is treated before it lands (since 0.16.5); `fluid verify` fails cleartext | ✅ Same, including the BigQuery load file; `fluid verify` fails cleartext | ❌ Not read |
| **Platform dynamic masking** | ❌ Lake Formation controls access; it does not mask values | ❌ No BigQuery data policy emitted | ❌ No masking policy emitted |
| **Retention** (`lifecycle.expire`, 0.7.6 preview) | ✅ S3 lifecycle rule; verified | ✅ Expiring daily partitions; verified | ❌ Not read |
| **Encryption at rest** (`binding.encryption.kms`, 0.7.6 preview) | ✅ SSE-KMS with a product key, alias or ARN; verified | ✅ Cloud KMS key ring and key per dataset; verified | ❌ Not read |
| **Residency** (`sovereignty`) | ✅ `validate`, and the planner refuses an out-of-policy region | ✅ `validate`, and `generate iac`/`apply` refuse an out-of-policy placement, including regions a resource inherits by default | `validate` only |

Read the cells carefully:

- **Snowflake reads none of the governance fields.** The Snowflake emitter writes grants, masking and row access policies only from a top-level `security:` block, which the schema rejects, so a valid contract produces none of them. `fluid validate` does not warn about this as of 0.18.1. Manage Snowflake access outside the contract for now.
- **AWS access is the binding's, not `accessPolicy`'s.** The AWS emitter does not write `accessPolicy.grants`. Declare readers under `binding.governance.lakeFormation.grants`; column restrictions then narrow those grants.
- **Not built on GCP:** VPC Service Controls, BigQuery row-level security and BigQuery data policies are not emitted as of 0.18.1. Policy tags come from `fluid apply`, not from `fluid policy apply`.
- **Masking is at landing, not at query time.** No cloud gets a dynamic masking policy. Values are treated when the DuckDB acquisition runner writes them, and an embedded-SQL build that would land a masked expose is refused. See [masking at landing](/forge_docs/advanced/source-aligned-acquisition.html#masking-at-landing).
- **What is proven.** forge-cli's tests run the governed GCP modules through `tofu validate` and through `tofu plan`/`apply` against an in-process BigQuery stand-in, and the Lake Formation grants against moto. A run against real BigQuery on 4 Oct 2026 verified retention, CMEK keys and policy tags with `fluid verify`, and a denied principal was refused the restricted column. The Lake Formation half has been proven against moto only.

Where native enforcement is missing, route agent reads through the [MCP output-port gate](/forge_docs/concepts/agent-policy.html#enforcement-modes), and check what actually deployed with `fluid verify`.

→ Per-field detail: [Governance & Policy → What gets emitted per cloud](/forge_docs/concepts/governance-policy.html#what-gets-emitted-per-cloud) · [AWS](/forge_docs/providers/aws.html) · [Snowflake](/forge_docs/providers/snowflake.html) · [GCP](/forge_docs/providers/gcp.html).

## The audit trail

> **Why it matters**
> "Show me who accessed this product last quarter" should be a query, not a project. The reads are already in your cloud's audit log under the identities the contract granted; Forge adds the decisions it makes itself.

What Forge records:

| Event | Record | Where |
|---|---|---|
| Agent read through `fluid mcp output-port serve` | A `data_access` record per decision, allow and deny, with `modelId`, `useCase`, `reason` and the `policyDigest` of the rules that decided it | `~/.fluid/store/audit/` or `FLUID_AUDIT_ROOT`; optionally forwarded to `FLUID_MCP_AUDIT_WEBHOOK_URL` |
| `fluid apply` | Structured log events; OpenLineage run events when `OPENLINEAGE_URL` is set (applies through OpenTofu); a run report to a Command Center deployment when the publish config is present (since 0.17.0) | Your log pipeline, your lineage backend, your Command Center |
| `fluid verify` | A JSON report of each check, with `--out` | A file you keep with the build |

Forge does not write to BigQuery audit logs, CloudTrail or Snowflake `ACCESS_HISTORY`, and there is no cross-cloud record format. Direct reads land in those logs as they always do.

A deny record names its reason, from a closed vocabulary such as `in-deniedUseCases` or `not-in-allowedModels`, so a denied agent read is as auditable as an allowed one.

→ Detail: [Agent Policy → Audit event schema](/forge_docs/concepts/agent-policy.html#audit-event-schema) and [Governance & Policy → Audit trail](/forge_docs/concepts/governance-policy.html#audit-trail).

## How policy gets applied (the CLI path)

> **Why it matters**
> The policy path is designed so the *safe* operations need no cloud credentials at all — your CI can gate every PR on policy correctness without ever touching production IAM. Deployment is a separate, explicit, opt-in step.

The policy commands, and the one that provisions:

| Command | What it does | Touches the cloud? |
|---|---|---|
| `fluid policy check` | Lints sensitivity, access control, data quality, lifecycle and schema evolution; exits 1 on a blocking finding | **No** — safe pre-commit / CI gate |
| `fluid validate` | Schema, sovereignty, and refusals of policies a binding cannot apply | **No** |
| `fluid policy compile` | Writes `accessPolicy.grants[]` as provider-shaped bindings JSON for review | **No** |
| `fluid apply` | Provisions the grants, policy tags, Lake Formation permissions, keys and lifecycle rules the contract declares | **Yes** |
| `fluid policy apply` | Stage 8 of the generated pipeline. As of 0.18.1 it provisions nothing on any provider: GCP reports the bindings, AWS and Snowflake print a warning. It registers acquisition policies for the acquisition runtime | **No** |

```bash
fluid policy check contract.fluid.yaml            # CI gate — no cloud calls
fluid policy compile contract.fluid.yaml          # contract → bindings JSON, for review
fluid apply contract.fluid.yaml --yes             # provisions the controls
fluid verify contract.fluid.yaml --strict         # checks them on the live platform
```

→ Detail: [`fluid policy check`](/forge_docs/cli/policy-check.html) · [`fluid policy apply`](/forge_docs/cli/policy-apply.html) · [agent enforcement modes](/forge_docs/cli/tasks/agent-governance.html).

## The business case (qualitative)

> **Why it matters**
> The line item on your adoption brief isn't "buy a governance tool." It's "stop paying the five-tool drift tax." Here's the value, framed honestly — no invented ROI percentages, no benchmark claims, no customer counts. Just *why*.

- **Five tools to one.** Shipping a trustworthy data product today usually means five tools and five languages — the model (dbt), the infrastructure (Terraform), the schedule (Airflow), the access rules (OPA), the masking rules (a warehouse UI). That's five places for the same product to disagree. Forge collapses them into one `contract.fluid.yaml`.
- **Fewer drift incidents.** When the schema changes, you change *one* file and re-apply — instead of editing four systems in lockstep and hoping they agree.
- **Fewer 3am pages.** A breaking change or an unauthorized grant surfaces at `fluid validate` / `fluid policy check` in code review — not after a pipeline fails in production.
- **No per-cloud rewrite.** One base contract runs on `local` (DuckDB), AWS (Athena/Glue), GCP (BigQuery) or Snowflake: a per-cloud overlay changes only the binding (platform, format, location and, on 0.7.6, principals). See [Switch clouds](/forge_docs/recipes/switch-clouds.html).
- **Governance shifted left, into code review.** `accessPolicy`, `agentPolicy`, and `sovereignty` are part of the contract from line one — reviewed and versioned with the schema, not retrofitted after the data is already in a vector store.

**A fit if you have:**

- Two or more clouds, or a credible chance of a second one
- Compliance pressure — SOX, GDPR, HIPAA — that makes governance non-optional
- AI agents reading your data (often your newest and largest consumer)
- A platform team building a self-serve contract layer for internal users
- Data-product owners who don't want to learn five tools to ship one product

**Not the right tool (yet) if you're:**

- A single-warehouse, single-team analytics shop with no governance pressure — dbt alone is simpler
- Running **sub-second streaming** — Forge's model is batch and mini-batch (5-minute to 24-hour latency); for sub-second, look at Materialize / RisingWave
- Expecting a **hosted control plane today** — Forge is CLI + CI; a hosted UI is on the roadmap, not shipped

## See also

- [Why Fluid Forge](/forge_docs/why.html) — the engineer/leader value pillars this page extends for buyers
- [Governance & Policy](/forge_docs/concepts/governance-policy.html) — every governance field, which command enforces it, and what it becomes per cloud
- [Agent Policy](/forge_docs/concepts/agent-policy.html) — the per-expose `agentPolicy` concept + runtime enforcement
- [AWS provider](/forge_docs/providers/aws.html) — Lake Formation detail
- [Snowflake provider](/forge_docs/providers/snowflake.html)
- [GCP provider](/forge_docs/providers/gcp.html) — BigQuery detail
- [Provider roadmap](/forge_docs/providers/roadmap.html) — governance maturity across clouds
- [`fluid policy check`](/forge_docs/cli/policy-check.html), [`fluid policy apply`](/forge_docs/cli/policy-apply.html) and [`fluid verify`](/forge_docs/cli/verify.html) — the policy CLI path
- [Agent governance task](/forge_docs/cli/tasks/agent-governance.html) — the three agent enforcement modes
- [Consume a data product](/forge_docs/data-products/consume.html) — the consumer front door companion to this page
