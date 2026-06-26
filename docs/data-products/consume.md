---
title: "Consume a Data Product"
description: "Discover a published Fluid data product, read its contract to decide whether to trust it, and consume it three ways \u2014 as a human with SQL/BI, as a downstream data product via consumes[], or as an AI agent over the MCP output-port."
---

# Consume a Data Product

You didn't build this product. You want to *use* it — and you want to use it safely, without spelunking through someone else's pipeline code to figure out what a column means, how fresh it is, or whether you're allowed to read it at all.

This page is the consumer front door. It shows you how to **discover** a published Fluid data product, **read its contract** to decide whether to trust it, and then **consume it three ways** — as a human with SQL or BI tools, as a downstream data product, or as an AI agent over MCP.

> **Why it matters**
> The contract is how you trust a product *before* you query it. Schema, sensitivity, freshness, quality rules, lineage, and access rules all travel inside one versioned, validated artifact — so you can decide "is this safe to use?" by reading the contract, not by reverse-engineering the producer's code. And it's the **same** contract whether you're a person, a pipeline, or an agent: one source of truth, three consumers, the same declared rules.

---

## Who this is for

| You are… | You want to… | Jump to |
| --- | --- | --- |
| **An analyst / BI user** | Read the published data with SQL, a notebook, or a dashboard | [Pattern 1 — Consume as a human](#pattern-1-consume-as-a-human-sql-exports-bi) |
| **Building a downstream product** | Pull this product into your own pipeline without re-typing its schema | [Pattern 2 — Consume as a downstream product](#pattern-2-consume-as-a-downstream-product-consumes) |
| **Wiring an AI agent** | Let an LLM query the product safely, under contract-declared rules | [Pattern 3 — Consume as an AI agent](#pattern-3-consume-as-an-ai-agent-mcp-output-port) |

Whichever row you're in, you start the same way: **discover the product**, then **read its contract**.

---

## Step 1 — Discover: find a published product

> **Why it matters (analyst / consumer):** Before you can use a product, you have to find it — and find out whether it's the *right* one. `fluid market` is your catalog search: it answers "what data products exist, who owns them, how good are they?" from the terminal, no portal login required.

Products are published to catalogs (stage 10 of the pipeline — see [`fluid publish`](/forge_docs/cli/publish.html)). You discover them with [`fluid market`](/forge_docs/cli/market.html), which searches and browses data products across your configured catalogs and blueprint sources.

```bash
# Browse everything
fluid market

# Narrow by what you care about
fluid market --search "customer analytics"
fluid market --domain finance --status active
fluid market --layer gold --min-quality 0.9
fluid market --owner growth-team

# Drill into one product
fluid market --product-id customer-360-v2 --detailed
```

Useful filters: `--search` / `-s`, `--domain` / `-d`, `--owner` / `-o`, `--layer` / `-l`, `--status`, `--tags` / `-t`, `--min-quality`, and `--created-after` / `--created-before`. Use `--list-catalogs` to see which catalog sources are configured, and `--catalogs` to restrict the search to specific ones.

::: tip Command Center enrichment is automatic and silent
If a FLUID Command Center instance is reachable, `fluid market` auto-detects it and enriches results with cross-organization catalog data — you don't configure anything for this to happen. If no endpoint is reached, it **falls back to local catalog discovery** transparently. This is detection-and-enrich, not a hosted UI you log into: the consumer surface here is the CLI.
:::

---

## Step 2 — Read the contract = read the trust story

> **Why it matters (analyst / consumer):** "Can I trust this?" is the question that stalls most consumption. The contract answers it up front. Everything you need to evaluate a product — what's in it, how good it is, where it came from, and whether you're allowed to use it — is declared in one place and validated by the CLI, so it can't silently drift from the data.

Once `fluid market` points you at a product, open its contract. The contract is the single source of truth ([why.md → the contract carries the context](/forge_docs/why.html#the-contract-carries-the-context)). Here's where each part of the trust story lives:

| What you need to know | Where it lives in the contract |
| --- | --- |
| **What columns exist, their types, and what's sensitive** | `exposes[].contract.schema` — each field has `name`, `type`, and an optional `sensitivity` (e.g. `pii`, `phi`, `cleartext`) |
| **How good / fresh the data is** | `exposes[].contract.dq.rules` — freshness, completeness, uniqueness, valid_values, accuracy, schema, anomaly_detection, drift_detection — each with a `severity` (`info` / `warn` / `error` / `critical`) |
| **The declared service-level targets** | `exposes[].qos` — availability, freshness, latency, completeness, error budget |
| **Where the data came from (lineage)** | Auto-derived from `consumes[]` (explicit upstream-product references), plus `builds[].properties.sql` and dbt repository references |
| **Who may read it** | `accessPolicy.grants[]` (humans / services, compiled to native cloud IAM) and `exposes[].policy.agentPolicy` (AI agents) |

To inspect quality, SLA, and lineage in depth, see [Quality, SLAs & Lineage](/forge_docs/concepts/quality-sla-lineage.html).

::: warning Honest note on SLA monitoring
The `qos` targets you read in the contract are **declared** SLAs. Today they're published to catalogs (ODCS) and Data Mesh Manager so consumers can *see* the promise — but **active monitoring against those thresholds is on the roadmap**, not shipped. Treat `qos` as the producer's stated intent, not a live, alerting SLO yet.
:::

The `dq.rules`, on the other hand, *are* enforced: they're checked by `fluid validate`, `fluid test`, and `fluid verify`, and an `error` / `critical` rule blocks the producer's deploy. So a published product has already passed its own declared quality gates.

---

## Pattern 1 — Consume as a human (SQL / exports / BI)

> **Why it matters (analyst):** You don't need to learn Forge to read a Forge product. Once you have access, the data lives in an ordinary table or view in the warehouse you already use. Forge got it there, governed; you query it with the SQL and BI tools you already know.

The contract's `exposes[].binding` tells you exactly **where the data physically lives** — the platform, and the table or view name. Once the producer grants you access via the top-level `accessPolicy.grants` (which compiles to native cloud IAM — BigQuery / Snowflake / S3), you read it with standard warehouse tooling:

```sql
-- BigQuery / Snowflake / Athena — whatever the binding names
SELECT segment, COUNT(*) AS customers
FROM analytics.customer_segments_v1
GROUP BY segment;
```

This consumption happens **outside the Forge runtime**. Forge declared the schema, applied the access grants from `accessPolicy.grants`, and deployed the table; from there you point Looker, Tableau, a notebook, or a `SELECT` straight at the bound object. The contract's `schema` is your data dictionary; its `sensitivity` tags tell you which columns are PII/PHI before you ever put them on a dashboard.

---

## Pattern 2 — Consume as a downstream product (`consumes[]`)

> **Why it matters (downstream data engineer):** You shouldn't have to copy-paste an upstream product's schema into your pipeline and pray it stays in sync. Naming the upstream by product ID lets the planner resolve its bindings for you — when the upstream changes, your contract is checked against it at plan time, not at 3am in production.

A downstream product names its upstream by **product ID** in `consumes[]`. The planner resolves the binding, so your contract never re-types the upstream schema or transformation logic:

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: silver.orders_enriched
metadata:
  layer: Silver
  productType: ADP

consumes:
  - product: bronze.crm_orders      # named by ID — planner resolves the binding
    expose: orders
    alias: orders
  - product: bronze.crm_customers
    expose: customers
    alias: customers

builds:
  - name: enrich
    engine: sql
    sql: |
      SELECT o.order_id, o.amount_cents, c.region, c.segment
      FROM {{ orders }} o
      LEFT JOIN {{ customers }} c USING (customer_id)
```

Then drive it through the normal lifecycle:

```bash
fluid validate silver.orders_enriched.fluid.yaml
fluid plan     silver.orders_enriched.fluid.yaml
fluid apply    silver.orders_enriched.fluid.yaml --yes
```

`fluid plan` resolves each `consumes[].product` against the workspace registry, confirms the named expose exists, and validates the projected schema against your SQL `{{ alias }}` placeholders. A broken pointer never gets past plan.

**Composition rules** (enforced by the planner — see [Product Types → Composition rules](/forge_docs/data-products/product-type.html#composition-rules)):

| Product type | Can it `consumes[]`? |
| --- | --- |
| **SDP** (Bronze / source-aligned) | No — SDPs are leaves; declaring `consumes[]` fails |
| **ADP** (Silver / aggregate) | Yes — may consume SDP(s) |
| **CDP** (Gold / consumer-aligned) | Yes — may consume SDP and/or ADP |

For the full walkthrough, see the recipe: [Write a contract that consumes another contract](/forge_docs/recipes/consumes-contract-to-contract.html).

---

## Pattern 3 — Consume as an AI agent (MCP output-port)

> **Why it matters (platform engineer onboarding an agent):** Pointing an LLM at your warehouse is how PII leaks and runaway queries happen. The MCP output-port gives the agent a deliberately small, read-only surface — and enforces the *contract's* governance (allowed models, PII redaction) on every single call, with no extra glue code.

You serve a published product to an agent with **`fluid mcp output-port serve`** — the consumer-side data-access gate.

::: warning Use the right command
`fluid mcp output-port serve` is the **consumer** gate that serves data products to agents. `fluid mcp serve` is the **producer / authoring** server for data engineers — it does **not** serve published data to agents. They are different commands.
:::

```bash
fluid mcp output-port serve ./contract.fluid.yaml
```

The agent gets exactly **four bounded tools** (full reference: [`fluid mcp`](/forge_docs/cli/mcp.html)):

| Tool | What it does |
| --- | --- |
| `describe` | Returns schema + semantics + the `agentPolicy` block — no engine round-trip; how the agent orients itself |
| `sample` | Returns a few rows, with PII/PHI columns redacted |
| `query` | Runs a **predeclared** semantic aggregate (a metric/measure from `semantics`) — no raw SQL |
| `query_sql` | Free-form `SELECT` — **OFF by default**, advertised only with `--allow-sql` |

The server is **read-only**, and free-form SQL stays off unless you explicitly opt in with `--allow-sql`.

**Two contract-driven guarantees the gateway enforces on every call:**

1. **`agentPolicy` gate.** The allowlist lives per-expose at `exposes[].policy.agentPolicy` (a top-level `agentPolicy` fails validation). A caller whose `model_id` isn't in `allowedModels` is refused with a typed envelope:

   ```jsonc
   {
     "error": "AgentPolicyDenied",
     "tool": "sample",
     "reason": "not-in-allowedModels",
     "message": "denied by agentPolicy; see audit trail for the full decision."
   }
   ```

2. **Automatic PII/PHI redaction.** A column marked `sensitivity: pii` keeps its name but its values come back as `[REDACTED-PII]` on every `sample` / `query` / `query_sql` result. The mask is **alias-proof**: even with `--allow-sql`, `SELECT email AS x` is rejected at compile time. The agent learns the field *exists* (so it can still write `COUNT(DISTINCT email)`) but never sees a real value.

For the hands-on version — serve a DuckDB-backed product, drive the tools, and watch a deny and a redaction happen — follow [Walkthrough: MCP Output Port](/forge_docs/walkthrough/mcp-output-port.html). For the policy concept in depth, see [agentPolicy](/forge_docs/concepts/agent-policy.html).

::: tip One nuance on token caps
`agentPolicy.maxTokensPerRequest` is a **post-hoc throttle**, not a pre-flight limit: the read executes, the response is measured, and it's withheld with `TokenBudgetExceeded` if it's over the cap. It bounds what the agent *receives*; it doesn't pre-block the query.
:::

---

## One contract, every consumer

The schema, sensitivity tags, `qos`, lineage, and `dq.rules` that earn **human** trust are the same declarations a **downstream pipeline** and an **AI agent** read to act safely — one artifact, no second governance system to keep in sync.

- A **person** reads `sensitivity: pii` and keeps it off a dashboard; the agent gateway reads the same tag and redacts the value to `[REDACTED-PII]`.
- A **person** reads the top-level `accessPolicy.grants` to know they're allowed in; the agent is gated by `agentPolicy.allowedModels` on the same contract.
- A **downstream product** doesn't re-read any of it by hand: its planner resolves the very `exposes[].binding` and schema the human and agent rely on, straight from `consumes[]` — so when the upstream changes, every consumer sees the change through the same source of truth.

One versioned artifact, three kinds of consumer, the same declared rules.

---

## Next steps / See also

- [`fluid market`](/forge_docs/cli/market.html) — discovery options, catalog filters, and Command Center enrichment.
- [Why Forge — the contract carries the context](/forge_docs/why.html#the-contract-carries-the-context) — what travels inside a contract and why it earns trust.
- [Quality, SLAs & Lineage](/forge_docs/concepts/quality-sla-lineage.html) — `dq.rules`, `qos`, and auto-derived lineage (with the SLA-monitoring roadmap note).
- [Consume one contract from another](/forge_docs/recipes/consumes-contract-to-contract.html) — the full Pattern 2 recipe.
- [Product Types → Composition rules](/forge_docs/data-products/product-type.html#composition-rules) — what can consume what.
- [Walkthrough: MCP Output Port](/forge_docs/walkthrough/mcp-output-port.html) — Pattern 3, hands-on.
- [`fluid mcp` reference](/forge_docs/cli/mcp.html) — the four agent tools, every flag.
- [agentPolicy](/forge_docs/concepts/agent-policy.html) — the agent-access policy concept.
- [Governance, Compliance & ROI](/forge_docs/governance-compliance-roi.html) — the buyer / governance companion page, including the honest provider-enforcement matrix.
