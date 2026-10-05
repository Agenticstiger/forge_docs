---
home: true
heroText: Fluid Forge
tagline: Declare a data product once in a contract. Build it on your laptop, deploy it to AWS, GCP or Snowflake, and verify that what landed matches what you declared.
actions:
  - text: Get started
    link: /getting-started/
    type: primary
  - text: Tutorials
    link: /walkthrough/
    type: secondary
  - text: Concepts
    link: /concepts/
    type: secondary
  - text: CLI reference
    link: /cli/
    type: secondary

features:
  - title: Local first
    details: Install with the local extra, then validate, plan, apply, verify and test a product on DuckDB before you touch a cloud credential.
  - title: One contract, one file or many
    details: Write a product as one file, or as a root contract plus fragment files. validate, plan and apply resolve the fragments into one document.
  - title: Environments and two clouds
    details: --env picks an overlay that patches the base contract. Since 0.17.0 one contract deploys to AWS and to GCP this way, with its retention, encryption and column restrictions mapped to each cloud's own resources.
  - title: Verify what landed
    details: fluid verify reads the deployed target and compares it with the contract. With --strict, drift fails the build, so it can gate CI.
  - title: Sovereignty enforced
    details: Pin a jurisdiction in the contract and the engine blocks a mismatched binding. An EU contract bound to us-east-1 fails "fluid validate" with exit 1.
  - title: Command Center
    details: fluid publish sends a product to a FLUID Command Center catalog, and fluid apply reports its runs there once a credential is configured.

footer: Apache 2.0 Licensed | Documentation for the Fluid Forge CLI
---

Fluid Forge is a command-line tool, `fluid`, for data engineers who build data products. You describe a product in a contract: its schema, how it is built, where it lands, its quality rules, who may read it and where it may live. The CLI validates the contract, plans and applies it to the platform the binding names, and checks the deployed result against it.

- **The contract is the source of truth.** The plan, the cloud resources, the access rules and the checks `fluid verify` runs are all derived from it. See [What is a contract](./concepts/contract.md).
- **One contract, several places.** An overlay per environment patches the binding, so the same contract runs in `dev` and `prod`, or on AWS and GCP. See [Environments and overlays](./concepts/environments-and-overlays.md) and [Governance parity](./concepts/governance-parity.md).
- **Checked before and after.** `fluid validate` refuses a contract that breaks the schema or its own sovereignty pin; `fluid test` runs the data-quality rules; `fluid verify` compares what landed with what was declared.

Where Forge does and does not fit next to dbt, Terraform, Airflow and Snowpark: [Fluid Forge vs alternatives](./concepts/vs-alternatives.md).

## Run it

```bash
pip install "data-product-forge[local]"
mkdir fluid-quickstart && cd fluid-quickstart
fluid init my-first-product --blueprint fluid.starter
cd my-first-product
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes --mode amend-and-build
fluid verify contract.fluid.yaml --strict
cat runtime/out/my-first-product.csv
```

```text
message,created_at
Hello from the my-first-product data product,2026-10-05 10:35:49.479853+02
```

[Getting Started](./getting-started/README.md) walks through each step with its output, then makes the product read a CSV and adds a data-quality rule. It explains why it uses the `fluid.starter` blueprint rather than `fluid init --quickstart` on 0.18.1.

This site documents CLI `0.18.1`, with contract schema `0.7.5` as the stable default and `0.7.6` as an [opt-in preview](./reference/preview-fields.md). `fluid version` is the CLI release you installed; `fluidVersion` inside a contract is the [schema version](./reference/README.md) it is written against. Which version each scaffold writes is in [Understand the version numbers](./getting-started/README.md#understand-the-version-numbers).

## Follow one product from laptop to production

The docs are ordered as the life of a data product. Each step links to the page that covers it:

1. **Install and build locally:** [Getting Started](./getting-started/README.md), then the [local walkthrough](./walkthrough/local.md).
2. **Understand the contract:** [What is a contract](./concepts/contract.md), [Builds, exposes, bindings](./concepts/builds-exposes-bindings.md), and the [contract reference](./reference/README.md).
3. **Split it into files:** [Contract fragments](./concepts/fragments.md) and [`$ref`](./concepts/contract-refs.md).
4. **Run it in each environment, and on two clouds:** [Workspaces](./concepts/workspaces.md), [Environments and overlays](./concepts/environments-and-overlays.md), [One contract, two clouds](./recipes/one-contract-two-clouds.md), [OpenTofu state](./concepts/state.md).
5. **Govern it:** [Governance and policy](./concepts/governance-policy.md), [Governance parity](./concepts/governance-parity.md), [Sovereignty](./concepts/sovereignty.md), [Agent policy](./concepts/agent-policy.md).
6. **Ship it:** [The 11-stage pipeline](./walkthrough/11-stage-pipeline.md), [Declarative Airflow](./walkthrough/airflow-declarative.md), [`fluid publish`](./cli/publish.md) and the [Command Center](./concepts/command-center.md).
7. **Change it and upgrade:** [Change a live data product](./recipes/evolve-a-live-product.md) and [Upgrading](./upgrading.md).

## See it run

A 60-second walkthrough of the core move: one `contract.fluid.yaml`, built and tested locally on DuckDB, then pointed at BigQuery and Snowflake by changing its `binding`. In the [`sovereignty-platform-swap` example](https://github.com/Agenticstiger/forge-cli/tree/v0.18.1/examples/sovereignty-platform-swap) the AWS, GCP and Snowflake contracts differ only inside `binding`; run `diff` on them to check.

<iframe
  src="/forge_docs/reels/one-contract-every-cloud.html"
  width="100%"
  height="680"
  style="border: 1px solid var(--vp-c-border); border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Fluid Forge — one contract, every cloud">
</iframe>

Use ←/→ to step scenes, space to pause, r to restart. The reels were recorded on an earlier CLI; [See it run](./see-it-run.md) has the full set and says what has changed since.

## AI-assisted scaffolding

```bash
fluid forge
fluid forge --domain retail
```

`fluid init` scaffolds from a fixed template or blueprint. `fluid forge` drafts a contract from the files in your directory with the LLM provider you configure with `fluid ai setup`. To forge a data model from a business intent file and generate dbt from it:

```bash
fluid forge data-model from-intent --example retail > intent.yaml
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

See [AI forge and data-model journeys](./walkthrough/ai-forge-data-model.md).

## Promoted command groups

These are the groups `fluid --help` prints on `0.18.1`:

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `validate`, `plan`, `apply` |
| Generate | `generate transformation`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import`, `mcp` |
| Quality & Governance | `policy-check`, `test` |
| Safety & Supply Chain | `rollback`, `verify-signature` |
| Utilities | `config`, `ai`, `split`, `auth`, `doctor`, `providers`, `exporters`, `version` |

`--help` promotes a short surface. Commands such as `bundle`, `diff`, `verify`, `runs`, `stats`, `ship` and [`mission`](./cli/mission.md) are registered and documented, and `--help` names the production path as `bundle` → `validate` → `generate artifacts` → `diff` → `plan` → `apply` → `verify` → `publish`. The [CLI reference](./cli/README.md) covers the commands.

:::: tip Current release — `0.18.1`, schema **0.7.5** stable (GA)
`pip install data-product-forge` gives you `0.18.1`. Its notes:
[`0.18.0` and `0.18.1`](./RELEASE_NOTES_0.18.0.md). Coming from an older release? The
[upgrade guide](./upgrading.md) has a checklist for each version you cross.

**Since `0.15.0`:**

- **`0.15.1`–`0.16.2`** ([notes](./RELEASE_NOTES_0.16.0.md)) — a stage name such as `../../ESCAPED` can
  no longer make `fluid generate transformation` write outside `--output`, and contract values
  are escaped in generated Airflow, Prefect and Dagster code. Generated SQL
  now creates views, which drops grants on Snowflake and Databricks. AWS resources go to the
  binding's region, and BigQuery bindings load their rows.
- **`0.16.3`–`0.17.0`** ([notes](./RELEASE_NOTES_0.17.0.md)) — one contract deploys to AWS and
  to Google Cloud through `--env` overlays and is governed the same on both, checked by
  `fluid verify`. The generated 11-stage pipeline runs as generated. Upgrading has one-time
  steps: retire old Airflow DAGs, move state to a per-provider key, and let the first
  GCP apply revoke stale dataset grants.
- **`0.18.0`** — a contract's `$ref` and its SQL are confined to the contract's directory tree and declared
  locations, unless you widen them.
- **`0.18.1`** — the drift gate (`fluid diff --exit-on-drift`) reads a target whose binding
  names its project or path through an environment variable.

::: details Before that, each release keeping its own work
- [`0.15.0`](./RELEASE_NOTES_0.15.0.md) — sovereignty enforcement: `sovereignty.enforcementMode`
  blocks, warns or informs as declared, the region→jurisdiction table comes from the vendors'
  data, and a jurisdiction-pinned MCP output port refuses to start on stdio, or on HTTP with no
  auth mode. It documents `0.14.1` with it.
- [`0.14.0`](/forge_docs/RELEASE_NOTES_0.14.0.html) — live-verification hardening: the dbt Iceberg
  loop reaching all three cloud warehouses.
- [`0.13.0`](/forge_docs/RELEASE_NOTES_0.13.0.html) — verifiable autonomy and declarative packaging,
  with the [`fluid mission`](/forge_docs/cli/mission.html) command.
- [`0.12.0`](/forge_docs/RELEASE_NOTES_0.12.0.html) — dbt integration and schema GA: `0.7.5` promoted
  to stable as the default for untagged contracts, plus the brownfield
  [`fluid import dbt`](/forge_docs/cli/import.html) importer.
- [`0.11.0`](/forge_docs/RELEASE_NOTES_0.11.0.html) — the AI-ready / RAG surface: vector output port,
  semantic-drift guard, `ai_ready` agent.
- [`0.10.0`](/forge_docs/RELEASE_NOTES_0.10.0.html) — plugin governance: an operator trust boundary
  over plugins, with [`fluid plugins`](/forge_docs/cli/plugins.html) and
  [`fluid exporters`](/forge_docs/cli/exporters.html).
- [`0.9.0`](/forge_docs/RELEASE_NOTES_0.9.0.html) — the streaming Kafka → Iceberg sink.
- [`0.8.6`](/forge_docs/RELEASE_NOTES_0.8.6.html) — the [`fluid mcp`](/forge_docs/cli/mcp.html)
  output-port gateway: `agentPolicy` enforced at runtime, with JWT-bearer identity.
:::

The vocabulary and the product types behind all of it:
[SDK & Plugins](/forge_docs/sdk-and-plugins/),
[Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html),
[Product Types](/forge_docs/data-products/product-type.html).
::::

## Where to go next

- [Getting Started](./getting-started/README.md): install and build your first product locally
- [Tutorials](./walkthrough/README.md): end-to-end builds, with what each one needs
- [Recipes](./recipes/README.md) and [CLI by task](./cli/tasks/README.md): one task on a contract you already have
- [Concepts](./concepts/README.md): the model, in reading order
- [CLI reference](./cli/README.md) and [contract reference](./reference/README.md): commands, flags and fields
- [Providers](./providers/README.md): what each platform supports
- [Advanced](./advanced/README.md): CI operation, security boundaries, the AI stack and runtime reference
- [SDK & Plugins](./sdk-and-plugins/README.md): extend the CLI with your own scaffolds, validators and apply hooks

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions).
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues) with what you ran and what you saw.
- **Want to contribute?** See [the contributing guide](./contributing.md): doc fixes, examples and providers are welcome.
