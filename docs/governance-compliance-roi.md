---
title: "Governance, Compliance & the Business Case"
description: "The audit-and-trust story for the people who sign off on data products: how governance is declared in the contract, gated in CI, and recorded in your cloud's native audit log \u2014 with an honest, per-provider enforcement matrix and a qualitative business case."
---

# Governance, Compliance & the Business Case

**Governance in Fluid Forge is not a phase you bolt on after the data ships.** It's declared in the same `contract.fluid.yaml` as the schema — who may read it (`accessPolicy`), which AI models may read it (`exposes[].policy.agentPolicy`), and where the data may physically live (`sovereignty`) — checked in CI *before* anything deploys, and recorded in your cloud's own audit channel after it does. This page is the audit-and-trust story written for the people who sign off on it.

> **Why it matters**
> For a CDO or compliance lead, the question is never "does the tool have a governance feature?" — it's "can I prove, on demand, who could read what, why it was allowed, and that nothing changed between review and deploy?" Forge answers that with three artifacts you already control: a versioned contract that declares the rules, a CI gate that rejects violations before they ship, and your platform's native audit log that records every access. Governance becomes something you *ship and prove*, not an audit you scramble to pass.

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

Four declarations carry the governance surface. All four are reviewed, versioned, and validated the same way as the schema. Note the one place maturity varies: native, fine-grained *value masking and row-level security* are not yet uniform across clouds (see the [enforcement matrix](#the-honest-provider-enforcement-matrix)). Everything else here — access-control grants, sensitivity-as-redaction-at-the-MCP-port, the `agentPolicy` read gate, and the sovereignty check — is declared in the contract, checked in CI, and enforced uniformly.

| Declaration | Field | What it governs | Compiles / enforces to |
|---|---|---|---|
| **Access** | `accessPolicy.grants[]` | *Who* (people & service principals) may do what — `read`, `select`, `write`, `admin`, … | Native cloud IAM (BigQuery IAM bindings / Snowflake `GRANT` / S3 + Glue + Athena) |
| **Sensitivity** | `schema[].sensitivity` | *What's sensitive* — tag a column `pii`, `phi`, etc. | PII/PHI redaction at the MCP output port (shipped); native platform auto-masking varies by cloud — see the [enforcement matrix](#the-honest-provider-enforcement-matrix) |
| **Agent access** | `exposes[].policy.agentPolicy` | *Which AI models* may read *this expose*, for which use-cases, with what token caps | Read-time gate at `fluid mcp output-port serve` |
| **Sovereignty** | `sovereignty` | *Where* data may live — jurisdiction, allowed/denied regions, cross-border transfer, regulatory frameworks | Deploy-time rejection via `fluid policy check` |

> **Honesty note — placement matters.** `agentPolicy` lives **per-expose** at `exposes[].policy.agentPolicy`, so each expose carries its own AI-access boundary. A contract that puts `agentPolicy` at the **contract root** fails schema validation. Likewise, there is **no top-level `security:` block** in the current schema (v0.7.5) — the contract root is closed, and a `security:` key fails `fluid validate`. If a draft you inherit has either, it never passed validation.

→ Full treatment: [Governance & Policy](/forge_docs/concepts/governance-policy.html) (access, sensitivity, sovereignty, audit) and [Agent Policy](/forge_docs/concepts/agent-policy.html) (the per-expose AI gate + runtime enforcement).

## Mapping Forge to compliance frameworks

> **Why it matters**
> Your auditors don't care which YAML key Forge uses. They care which *control* it supports. This table is the translation layer between your compliance obligations and the contract fields that back them — the rows you can paste into an adoption brief or a SOC 2 readiness doc.

Set `sovereignty.regulatoryFramework` to an array of framework codes (`GDPR`, `HIPAA`, `SOX`, `SOC2`, `CCPA`); each one activates additional validation rules at `fluid policy check`. Multiple frameworks compose — `['GDPR', 'SOX']` activates both rule sets.

| Framework | Forge supports these controls | Contract field + command |
|---|---|---|
| **GDPR** | Cross-border-transfer rules; DPA-required field tagging; right-to-erasure compatibility check; PII tagging | `sovereignty` (jurisdiction / regions / `crossBorderTransfer`), `schema[].sensitivity: pii`; checked by `fluid policy check` |
| **HIPAA** | PHI columns flagged for stricter masking; audit logging required; encryption-at-rest validation | `schema[].sensitivity: phi`, `agentPolicy.auditRequired: true`; checked by `fluid policy check` |
| **SOX** | Change-management trail — every `apply` writes a signed audit record; no destructive operations without a documented `--reason` | `sovereignty.regulatoryFramework: ['SOX']`; enforced across `fluid apply` / `fluid policy apply` |
| **SOC2** | Activity logging on every read; service-principal rotation reminders; SLA-breach alerts to a designated audit principal | `agentPolicy.auditRequired`, `accessPolicy.grants[]`, `exposes[].qos`; checked by `fluid policy check` |
| **CCPA** | California-resident handling, analogous to GDPR; consumer-rights compatibility | `sovereignty.regulatoryFramework: ['CCPA']` |

> **Framing, deliberately:** Forge **supports these controls** — it gives you the declarations, the CI gate, and the native audit trail that an auditor asks for. It does **not** *certify* you compliant. Compliance is an organizational outcome; Forge is the tooling that makes the technical evidence cheap to produce and hard to fake.

→ Detail: [`sovereignty.regulatoryFramework`](/forge_docs/concepts/governance-policy.html#compliance-frameworks).

## The honest provider enforcement matrix

> **Why it matters**
> This is the table that gets a tool thrown out of a procurement review when it's wrong. So it's the one we keep scrupulously honest. The variance below is confined to one band: **fine-grained value masking and row-level security**. Everything outside that band — access-control grants, the sovereignty check, the `agentPolicy` read gate, and MCP-output-port redaction — is uniform across clouds. Here is exactly what enforces where, today.

| Capability | AWS (Lake Formation) | Snowflake | GCP / BigQuery |
|---|---|---|---|
| **Access-control grants** | ✅ Shipped — LF grants + column-level grants, emitted as `aws_lakeformation_*` | ✅ Shipped — RBAC `GRANT` statements fully applied | ✅ Shipped — dataset/table-level IAM bindings |
| **Column governance** | ✅ Shipped — TBAC via LF-tags | 🧪 **Beta** — masking *policy objects created, not auto-attached* | 🛣️ **Roadmap** — policy tags not shipped |
| **Row filters** | ✅ Shipped — `aws_lakeformation_data_cells_filter` (row + optional column projection) | 🧪 **Beta** — row-access *policy objects created, not auto-attached* | 🛣️ **Roadmap** — row-level security not shipped |
| **Value masking** | ❌ Not provided — Lake Formation is access-control, **not** value-masking | 🧪 **Beta** — masking policy created, not attached on the default apply path | 🛣️ **Roadmap** — dynamic data masking / VPC-SC not shipped |

Read the cells carefully:

- **AWS Lake Formation is access-CONTROL, not value-masking.** Grants, column grants, LF-tag-based access (TBAC), and row filters via `data_cells_filter` are shipped and enforce at the platform layer. Lake Formation does **not** provide dynamic value masking — if you need masking, do it at the MCP output port (PII/PHI redaction) or upstream.
- **Snowflake masking & row-access are Beta.** The `snowflake_masking_policy` / `snowflake_row_access_policy` *objects* are emitted, but on the **default OpenTofu apply path** they are **created and NOT auto-attached** — no `ALTER TABLE … SET MASKING POLICY` / `ADD ROW ACCESS POLICY` runs there. RBAC `GRANT`s, by contrast, are fully applied. Don't rely on Snowflake masking for a compliance control until attachment lands on the default path.
- **GCP BigQuery fine-grained governance is roadmap.** Only **coarse, table-level IAM** is available today. Row-level security, policy tags, dynamic data masking, and VPC-SC are **not shipped**.
- **`policy.privacy.masking` / `rowLevelPolicy` are declarative-only on AWS and GCP.** The fields validate against the schema, but they emit **no AWS or GCP infrastructure**. On AWS, use `binding.governance.lakeFormation` for row/column governance; on GCP, manage masking with `gcloud` / Data Catalog until it's wired in.

Where native platform enforcement isn't available, route agent reads through the [MCP output-port gate](/forge_docs/concepts/agent-policy.html#enforcement-modes) instead — and always verify what actually deployed with `fluid policy check`.

→ Per-provider detail: [AWS](/forge_docs/providers/aws.html) · [Snowflake](/forge_docs/providers/snowflake.html) · [GCP](/forge_docs/providers/gcp.html) · [Provider governance maturity](/forge_docs/providers/roadmap.html).

## The audit trail

> **Why it matters**
> "Show me who accessed this product last quarter" should be a query, not a project. Forge doesn't build a parallel audit silo you'd then have to secure and reconcile — it writes to the channel your cloud already retains and your auditors already trust.

Every `fluid apply`, every `fluid policy apply`, and (when `auditRequired: true`) every read produces an audit record in the platform's **native** channel:

| Platform | Audit channel |
|---|---|
| **GCP / BigQuery** | BigQuery audit log (`cloudaudit.googleapis.com/data_access`) |
| **Snowflake** | `ACCESS_HISTORY` view |
| **AWS** | CloudTrail |

The record format is unified across clouds, so a cross-cloud "who read what" query works against one shape:

```json
{
  "ts": "2026-04-12T14:23:01Z",
  "actor": "serviceAccount:airflow@prod.iam",
  "action": "read",
  "product": "gold.finance.customer_360_v1",
  "expose": "customer_360_table",
  "use_case": "analysis",
  "model": "claude-sonnet-4-6",
  "audit_id": "aud_8f2c4..."
}
```

For agent reads over `fluid mcp output-port serve`, **both** allow and deny decisions are recorded — a deny record carries a `reason` (`model_not_in_allow`, `use_case_denied`, `token_budget_exceeded`, `cannot_store_violation`) and the `policySource` (the expose whose `agentPolicy` produced the decision). That means a denied agent read is just as auditable as an allowed one — you can prove the gate fired.

→ Detail: [Audit trail](/forge_docs/concepts/governance-policy.html#audit-trail) and [agent audit event schema](/forge_docs/concepts/agent-policy.html#audit-event-schema).

## How policy gets applied (the CLI path)

> **Why it matters**
> The policy path is designed so the *safe* operations need no cloud credentials at all — your CI can gate every PR on policy correctness without ever touching production IAM. Deployment is a separate, explicit, opt-in step.

Three commands, increasing blast radius:

| Command | What it does | Touches the cloud? |
|---|---|---|
| `fluid policy check` | Validates access control, sensitivity, sovereignty, data quality, lifecycle, schema evolution | **No** — safe pre-commit / CI gate |
| `fluid policy compile` | Reads `accessPolicy.grants[]`, emits provider-native IAM bindings as JSON | **No** — pure function (contract in, JSON out) |
| `fluid policy apply` | Deploys the compiled bindings — **defaults to `--mode check` (dry-run)**; `--mode enforce` actually applies | Only with `--mode enforce` |

`fluid policy apply` is **stage 8 of the 11-stage pipeline** — it runs *after* `apply` (stage 7, so the schema objects the grants reference already exist) and *before* `verify` (stage 9, so under-authorized transforms surface as policy failures, not masked build errors). The stage self-gates on the bindings file's existence, so reference-only contracts that emit no policy skip cleanly.

```bash
fluid policy check contract.fluid.yaml            # CI gate — no cloud calls
fluid policy compile contract.fluid.yaml          # contract → native IAM JSON
fluid policy apply runtime/policy/bindings.json   # dry-run by default
fluid policy apply runtime/policy/bindings.json --mode enforce   # deploy
```

→ Detail: [`fluid policy check`](/forge_docs/cli/policy-check.html) · [`fluid policy apply`](/forge_docs/cli/policy-apply.html) · [agent enforcement modes](/forge_docs/cli/tasks/agent-governance.html).

## The business case (qualitative)

> **Why it matters**
> The line item on your adoption brief isn't "buy a governance tool." It's "stop paying the five-tool drift tax." Here's the value, framed honestly — no invented ROI percentages, no benchmark claims, no customer counts. Just *why*.

- **Five tools to one.** Shipping a trustworthy data product today usually means five tools and five languages — the model (dbt), the infrastructure (Terraform), the schedule (Airflow), the access rules (OPA), the masking rules (a warehouse UI). That's five places for the same product to disagree. Forge collapses them into one `contract.fluid.yaml`.
- **Fewer drift incidents.** When the schema changes, you change *one* file and re-apply — instead of editing four systems in lockstep and hoping they agree.
- **Fewer 3am pages.** A breaking change or an unauthorized grant surfaces at `fluid validate` / `fluid policy check` in code review — not after a pipeline fails in production.
- **No per-cloud rewrite.** The same contract retargets `local` (DuckDB) → AWS (Athena/Glue) → GCP (BigQuery) → Snowflake by changing `binding.platform`. No lock-in at the contract layer.
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
- [Governance & Policy](/forge_docs/concepts/governance-policy.html) — `accessPolicy`, `sensitivity`, `sovereignty`, audit, compliance frameworks
- [Agent Policy](/forge_docs/concepts/agent-policy.html) — the per-expose `agentPolicy` concept + runtime enforcement
- [AWS provider](/forge_docs/providers/aws.html) — Lake Formation shipped detail
- [Snowflake provider](/forge_docs/providers/snowflake.html) — masking / row-access **Beta** detail
- [GCP provider](/forge_docs/providers/gcp.html) — BigQuery governance **roadmap** detail
- [Provider roadmap](/forge_docs/providers/roadmap.html) — governance maturity across clouds
- [`fluid policy check`](/forge_docs/cli/policy-check.html) and [`fluid policy apply`](/forge_docs/cli/policy-apply.html) — the policy CLI path
- [Agent governance task](/forge_docs/cli/tasks/agent-governance.html) — the three agent enforcement modes
- [Consume a data product](/forge_docs/data-products/consume.html) — the consumer front door companion to this page
