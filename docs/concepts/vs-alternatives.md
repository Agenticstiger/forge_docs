---
title: Fluid Forge vs alternatives
description: Honest side-by-side comparisons against dbt, Dagster, Terraform, OPA, and Snowpark — including when NOT to use Fluid Forge.
---

# Fluid Forge vs alternatives

If you already use dbt, Dagster, Terraform, OPA, or Snowpark, you might be wondering which problem Fluid Forge is solving that those tools don't. **Honest answer: none of them, individually.** Forge's value is unifying the four contracts every data product has — schema, infrastructure, orchestration, policy — into one declarative file so they can't drift from each other.

This page is the comparison page we'd want to read if we were evaluating Forge cold. It includes **honest losses** (dbt has a bigger ecosystem, Dagster has better asset lineage, Snowpark has tighter Snowflake integration) so you can decide whether the unification trade is worth it for your team.

[[toc]]

---

## The 30-second answer

| You have… | Forge fits when… | Forge is overkill when… |
|---|---|---|
| **One warehouse, one team, dbt + a CI runner** | You'll need governance, agent boundaries, or to add a second cloud later | You'll never leave that warehouse, and policy/agent boundaries aren't on the roadmap |
| **Multi-cloud already (BQ + Snowflake + Athena)** | You're rewriting the same contract three times in three formats | You have dedicated platform engineers per cloud and they don't mind the duplication |
| **Compliance pressure (SOX / GDPR / HIPAA)** | You want governance, sovereignty, and AI access boundaries in the same file as the schema | You've already centralised governance on a separate plane (Immuta, Privacera) |
| **Building agentic data products** | You want declarative `agentPolicy` gating LLM access at read-time | Your agents query through a separate runtime layer that already enforces this |
| **Prototyping, don't know what you need yet** | Start local DuckDB, graduate when you do | You're at a code-only POC stage with no contract requirements |

---

## The unification table

| Tool | What it owns | What it doesn't own | What you wire by hand today |
|---|---|---|---|
| **dbt Core** | SQL transformations, lineage, refs/sources, dbt tests | Provisioning, IAM, multi-cloud, agent governance, sovereignty | Terraform for IAM + Airflow for orchestration + OPA for policy + custom JSON for AI access |
| **Dagster** | Asset orchestration, asset checks, sensors, schedules | Schema-as-contract, native cloud IAM emission, multi-cloud abstraction | Terraform/Pulumi for infra + dbt for SQL + your own RBAC layer + your own AI gating |
| **Airflow / Composer / MWAA** | DAG scheduling, task retries, sensors | Schema, IAM, multi-cloud abstraction, contract validation | Resources + provider-specific operators + dbt + IAM + governance code |
| **Terraform** | Cloud infrastructure (any provider) | Schema, quality rules, transformations, orchestration | Tables + SQL + DAGs + dbt project + SLA checks + lineage emitters |
| **OPA / Rego** | Policy evaluation engine | Schema, transformations, cloud-native IAM emission, AI/agent boundaries | Compiling Rego → BigQuery row-level security / Snowflake masking / AWS IAM bindings |
| **Snowpark / dbt-Snowflake** | Snowflake-native data plane (UDFs, stored procs, dbt-cloud features) | Multi-cloud portability, agent governance | Rewriting everything if you ever leave Snowflake; a separate AI gate layer |
| **Fluid Forge** | All four — schema + infra + orchestration + policy + AI gating — in one `contract.fluid.yaml` | Bespoke per-vendor extreme tuning (e.g. Snowflake search optimization, BigQuery BI Engine reservations) | Anything genuinely vendor-specific that doesn't have a cross-cloud abstraction |

---

## Forge vs dbt

**The most common comparison.** dbt is the dominant SQL transformation framework; Forge is sometimes mistaken for a dbt competitor. It isn't.

### Where dbt wins
- **Ecosystem maturity** — 1000s of dbt packages, dbt-utils, dbt-expectations, dbt-snowflake, dbt-bigquery. Forge has none of these; it *uses* dbt for the SQL layer when `engine: dbt` is selected.
- **SQL-only teams** — if your data product *is* a SQL transformation and nothing more, dbt is simpler. Forge's contract surface (schema, dq.rules, accessPolicy, agentPolicy, sovereignty) is overhead you don't need.
- **Community + hiring** — dbt has been around since 2016. There are dbt analysts on the market. Forge engineers are still rare.
- **dbt Cloud / dbt Mesh** — if you're committed to the dbt ecosystem and willing to pay for the cloud product, you get IDE, CI, lineage, and discovery without leaving dbt-land.

### Where Forge wins
- **Multi-cloud portability** — change `binding.platform: snowflake` to `binding.platform: bigquery`, redeploy. dbt's adapter layer handles SQL dialect differences but not the surrounding infrastructure (datasets, IAM, regions).
- **Governance as part of the contract** — `accessPolicy.grants` compiles to native IAM (BigQuery `IAM_BINDINGS`, Snowflake `GRANT`, AWS resource policies). dbt has no equivalent — you wire IAM separately.
- **Agent governance** — `agentPolicy` declares which LLMs can read which fields, with audit logging. dbt has no concept of this.
- **Sovereignty / regulatory framework** — `sovereignty.regulatoryFramework: ['SOX', 'GDPR']` is enforced before deploy. dbt does not validate compliance.
- **Local-first development** — `pipx install "data-product-forge[local]"` and `fluid apply` work entirely on DuckDB with no cloud account. dbt-core works locally too, but the typical dbt onboarding assumes a warehouse.
- **The contract is the source of truth** — dbt models describe transformations; Forge contracts describe the entire data product (schema, transformation, exposure, governance). Different scope.

### How they fit together
Forge does **not** replace dbt. The recommended pattern is `engine: dbt` inside a Forge contract — Forge handles provisioning, IAM, policy, and AI gating; dbt handles the SQL transformation. Both worlds, no overlap.

```yaml
builds:
  - id: customer_metrics
    engine: dbt              # ← dbt does the SQL
    repository: ./dbt
    properties:
      project: customer_360
      target: prod
```

---

## Forge vs Dagster

**A sharper philosophical comparison.** Dagster's asset-oriented orchestration is the closest thing in the OSS world to Forge's contract-first model.

### Where Dagster wins
- **Asset orchestration depth** — software-defined assets, partitioned assets, asset checks, asset sensors. Forge has builds + exposes; Dagster has a richer asset graph model with native lineage.
- **Python-first** — write your business logic in Python and let Dagster orchestrate. Forge's primary interface is YAML; Python is for builds via `engine: python`.
- **Dagster Cloud / Plus** — hosted control plane, branch deployments, concurrency controls. Forge has no hosted offering.
- **Op-level retries, backfills, and sensors** — operationally rich. Forge defers orchestration to the chosen scheduler (`fluid generate schedule --scheduler dagster | airflow | prefect`).

### Where Forge wins
- **Contract-first vs pipeline-first** — Forge starts with "what is this data product" (schema, SLAs, governance). Dagster starts with "how is it computed" (assets, ops). Different first principle.
- **Native cloud IAM emission** — same as the dbt comparison: `accessPolicy.grants` → `bindings.json` → `policy-apply`. Dagster has IO managers and resources, but no equivalent IAM compilation.
- **Multi-cloud abstraction at the contract layer** — Dagster's resources are typed to a specific platform per pipeline. Forge's `binding.platform` is a swap.
- **Agent governance as a first-class contract field** — Dagster doesn't model this.
- **Smaller surface for read-only data product producers** — if your team's job is to *publish* a data product (not to *operate* a complex pipeline), Forge's mental model is lighter than Dagster's.

### How they fit together
`fluid generate schedule --scheduler dagster` emits a Dagster job from the Forge contract. You get Forge's contract + governance + multi-cloud, plus Dagster's runtime. Forge owns the *what*; Dagster owns the *how*.

---

## Forge vs Terraform

**The infrastructure-as-code comparison.** Terraform is universal; Forge is data-specific.

### Where Terraform wins
- **Universality** — Terraform manages everything: VPCs, Kubernetes clusters, IAM roles, S3 buckets, Stripe products, Cloudflare DNS. Forge only manages data products.
- **Provider ecosystem** — 3000+ Terraform providers. Forge has 4 primary (local, gcp, aws, snowflake) plus a Custom Provider SDK.
- **State management** — Terraform's state is a battle-tested model with locking, partial apply, drift detection. Forge has lighter state semantics tuned for data products.
- **Mature blast-radius controls** — `terraform plan`, `terraform import`, workspaces, modules. Forge has `fluid plan` but the surrounding tooling is younger.

### Where Forge wins
- **Data-product-specific abstractions** — `exposes`, `dq.rules`, `agentPolicy`, `sovereignty`, `lineage` — try expressing these in Terraform. You can't, except as ad-hoc resource configurations that drift.
- **Schema-as-contract** — Forge validates the schema against the actual deployed table. Terraform doesn't know what a "schema" is.
- **One contract, three clouds** — Terraform requires three different sets of resource definitions to deploy "the same" BigQuery table on Snowflake and Athena. Forge does it with one binding swap.
- **Compiles to Terraform** — `fluid generate artifacts --target terraform` emits Terraform HCL when you want to inherit your Terraform pipeline downstream.

### How they fit together
Forge sits **on top of** Terraform conceptually. Many teams use Forge for the data-product layer and inherit their Terraform pipeline for the surrounding infra (VPCs, KMS keys, etc). Forge's `policy-apply` can either apply IAM directly or emit Terraform for human review.

---

## Forge vs Snowpark / dbt-Snowflake / dbt Cloud

**The single-vendor stack.** If you've gone all-in on Snowflake, this is who you're really comparing against.

### Where Snowflake-stack wins
- **Vendor-specific feature depth** — Snowpark UDFs, stored procs, search optimization, query acceleration, time-travel, zero-copy clones. Forge can drive Snowflake but doesn't surface every Snowflake-specific tuning knob.
- **Single bill, single support contract** — one vendor relationship, one billing system, one support team.
- **Snowflake Cortex / native LLM** — if your strategy is "Snowflake will be the AI plane too", Cortex is integrated. Forge supports Snowflake Cortex via providers but isn't tied to it.
- **dbt Cloud** — IDE, CI, lineage, jobs all hosted. Forge has none of the hosted UX yet.

### Where Forge wins
- **Optionality** — the day Snowflake pricing changes or a faster engine emerges (DuckDB, RisingWave, Materialize), you can move. With Snowpark you cannot.
- **Local development** — Forge runs end-to-end on DuckDB with no Snowflake account. Snowpark needs a Snowflake account from day one.
- **Cross-warehouse** — if part of your portfolio is on BigQuery and part on Snowflake, Forge unifies the contract. Snowpark + BigQuery is two parallel stacks.
- **Open-source, Apache-2.0** — no vendor lock at the orchestration layer.

### How they fit together
Use `binding.platform: snowflake` for your Snowflake-resident data products and inherit Snowflake's vendor-specific features via `binding.properties.snowflake.*`. The contract stays portable; the Snowflake-specific knobs are a property pass-through.

---

## When NOT to use Fluid Forge

The honest list. Adoption decisions are easier when you know where the tool actively isn't right.

### You're a one-warehouse, one-team analytics shop
If you have one Snowflake account, one dbt project, and no governance/compliance pressure, the Forge contract is overhead. **Stay on dbt.** You can still adopt `fluid validate` standalone if you ever want schema-as-contract testing.

### You need real-time streaming with sub-second SLA
Forge's batch-and-mini-batch model fits 5-minute to 24-hour latency. For sub-second streaming (CDC → live materialized view), look at **Materialize**, **RisingWave**, or a Kafka + Flink stack. Forge's `engine: kafka-connect` and `engine: debezium` cover ingestion; the streaming compute layer is out of scope.

### You're doing pure ML feature engineering
Forge's contract surface is general-purpose. For ML feature stores specifically, **Feast**, **Tecton**, or **Hopsworks** have richer concepts (feature views, point-in-time joins, online/offline parity). Forge can express the *output* feature table as a contract but doesn't have feature-store-specific abstractions.

### Your team already has a working four-tool stack
If `Terraform + dbt + Airflow + OPA` is humming and the team is happy, the migration cost to a unified contract may not pay off. Consider adopting Forge incrementally — start with `fluid validate` for contract testing, expand only if/when the cross-tool drift starts to bite.

### You need a hosted control plane today
Forge is currently CLI + GitHub Actions / GitLab CI / Jenkins / Tekton (any CI). There is no hosted Forge Cloud. If you need a SaaS UI for your data team to onboard non-engineers, **Dagster Cloud / dbt Cloud** are mature options today; the equivalent Forge offering is on the roadmap but not shipped.

---

## Bottom line

**Pick Fluid Forge when**:
- You're shipping data products across **2+ clouds** (or expect to within 12 months)
- Governance / compliance is **part of the contract**, not an after-the-fact audit
- You're building **agentic data products** and need declarative LLM access boundaries
- You want a **single source of truth** for schema, infra, orchestration, policy, AI gating

**Pick something else when**:
- You're committed to **one warehouse forever** and have no governance pressure → use dbt
- You need **rich orchestration** with pipeline-first semantics → use Dagster
- You need **arbitrary cloud infrastructure** (not just data products) → use Terraform
- You need **sub-second streaming** → use Materialize / RisingWave
- You need a **feature store** → use Feast / Tecton

**Use them together** when:
- You want Forge's contract + governance with dbt's SQL: `engine: dbt`
- You want Forge's contract with Dagster's runtime: `fluid generate schedule --scheduler dagster`
- You want Forge's contract layered on top of Terraform: `fluid generate artifacts --target terraform`

The unification value is highest when **at least two of (multi-cloud, governance, AI gating)** apply to your data products. If only one applies, the dedicated tool for that one thing is usually a better fit.

## See also

- [Concepts overview](/concepts/) — the rest of the conceptual reference
- [Get Started](/forge_docs/getting-started/) — install and ship a data product in 30 seconds
- [Demos library](/demos/) — the proof, in 30-second SVG casts
- [Universal pipeline](/forge_docs/walkthrough/universal-pipeline) — the canonical 11-stage CI flow
