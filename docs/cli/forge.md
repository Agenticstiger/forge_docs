# `fluid forge`

Author a data product contract with an AI copilot, an offline guided interview, or an empty skeleton. By default forge writes `contract.fluid.yaml` and `.fluid/forge-receipt.json`; a scaffold (`--scaffold`), a CI pipeline (`--ci`) and engine artifacts add files.

## Syntax

```bash
fluid forge [OPTIONS]
fluid forge data-model <from-intent|from-ddl|from-source|validate|diff|dump-ddl|learn> [OPTIONS]
```

## Examples

```bash
# Interactive AI copilot
fluid forge

# Target a provider or a domain
fluid forge --provider gcp
fluid forge --domain finance

# Choose the model
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider gemini --tiered --require-llm

# No model: an empty contract, or a guided interview with no network
fluid forge --blank --target-dir ./out
fluid forge --offline --non-interactive --yes --target-dir ./out

# Keep the contract in fragments, and add a CI pipeline
fluid forge --fragments --ci github_actions

# Pick up a paused run
fluid forge --resume
```

For a guided walkthrough of the forge journeys, see [AI Forge And Data-Model Journeys](../walkthrough/ai-forge-data-model.md).

## Key options

### Project

| Option | Description |
| --- | --- |
| `--target-dir`, `-d DIR` | Target directory for project creation. |
| `--provider`, `-p NAME` | Infrastructure provider. Registered in the 0.18.1 test install: `aws`, `datamesh_manager`, `gcp`, `local`, `redshift`, `snowflake`. With `gcp`, an error line asks for the global `--project`; set it, or `FLUID_PROJECT`, to avoid it. |
| `--domain NAME` | Domain expertise agent. Built in: `ai_ready`, `education`, `energy`, `finance`, `government`, `healthcare`, `insurance`, `logistics`, `manufacturing`, `media`, `pharma`, `retail`, `telco`. A custom name loads `.fluid/agents/<name>.yaml`; see [Custom domain agents](./agents.md#custom-domain-agents). |
| `--data-product-type CODE` | `SDP`, `ADP` or `CDP`, or `Bronze`, `Silver` or `Gold`. When omitted, the copilot infers it from the project goal. |
| `--transform-engine NAME` | Override the transformation engine (`dbt`, `sql`, `spark`, `dataform`, `dataflow`, `glue`) for ADP and CDP products. SDP products pick an acquisition engine from the capability catalog. |
| `--blank` | An empty contract, with no model call. |
| `--no-llm` | Use the heuristic-only path; never call a model. |
| `--offline` | A fully local guided interview: no model, no mode picker, no welcome scan, no remote schema fetch. Also set by `FLUID_FORGE_OFFLINE=1`. Pair with `--non-interactive` for a prompt-free run. |
| `--scaffold NAME`, `--template NAME` | Write the full ForgeEngine scaffold from a code template (`etl_pipeline`, `analytics`, `ml_pipeline`, `streaming`, `starter`). Without it, forge writes the contract and its receipt rather than a scaffold. `--template` is an alias of `--scaffold`. |
| `--agent-loop` | Use the multi-turn agent loop instead of a single prompt. The model must support tool use. See [Forge tools](../advanced/forge-tools.md). |
| `--no-generate` | Skip generating engine artifacts (a dbt project, SQL scripts). |
| `--apply-enrichment` | Write the post-synthesis enrichment artifacts (dbt tests, freshness, physical layout) back into the contract. Shows a diff and asks first; `--yes` skips the question. Off by default. |
| `--also-emit LIST` | Also write other standards after the contract: any of `odcs`, `odps`, `opds`, comma-separated. Defaults to `odcs` for CDP products and nothing otherwise. |
| `--dry-run` | Preview without creating files. |
| `--non-interactive` | Use defaults without prompting. |
| `--yes`, `-y` | Skip the pre-write confirmation. The preview panel still renders. |
| `--context VALUE` | Extra JSON context, or a path to a context file. |
| `--show-work` | Stream the agent's reasoning and tool calls. They are also saved under `.fluid/agents/<run-id>/`. |
| `--watch` | Regenerate the contract when a source file in the discovery path changes. Regeneration is non-interactive and offline. Tune with `FLUID_FORGE_WATCH_INTERVAL` and `FLUID_FORGE_WATCH_DEBOUNCE` (seconds). |
| `--agent` | Headless preset for agentic IDEs: non-interactive, JSON-Lines progress events on stdout. See [Headless agent mode](#headless-agent-mode). |
| `--emit-plan` | With `--agent`, emit a deterministic `forge.plan` checklist event instead of authoring the contract. Implies `--agent`. |

### Layout

| Option | Description |
| --- | --- |
| `--fragments` | Write the contract as a root file plus fragments under `fragments/`. |
| `--no-fragments` | Write one flat file. |

Both apply on the default AI-copilot path only. See [Single file or fragments?](#single-file-or-fragments).

### AI config

| Option | Description |
| --- | --- |
| `--llm-provider NAME` | `openai`, `anthropic`, `claude`, `gemini` or `ollama`; or a keyless provider: `mcp-sampling` (the calling IDE's model) or `claude-code`, `codex`, `cursor`, `kiro` (a local agent CLI). Providers installed through the `fluid_build.llm_providers` entry point are also accepted. |
| `--llm-model NAME` | Model identifier. |
| `--llm-endpoint URL` | Exact HTTP endpoint for the selected provider. |
| `--forge-agent-mode MODE` | For the local agent CLIs: `envelope` (default; the agent returns the contract as JSON on stdout) or `agentic` (the agent writes `contract.fluid.yaml` into the workspace). |
| `--llm-routing-model NAME` | A fast, cheap model for interview clarification and AI self-evaluation. |
| `--llm-routing-endpoint URL` | Endpoint override for the routing model. |
| `--tiered` | Use the provider's deep and fast model tiers. See [LLM Providers](../advanced/llm-providers.md). |
| `--require-llm` | Fail if the model cannot run, instead of falling back to a non-AI path. |
| `--deterministic` | Temperature 0, cache off, tiering off, audit metadata on. For byte-stable runs. |
| `--no-cache` | Bypass the LLM response cache. |
| `--browser` | Use the browser-based provider setup flow (preview). The key is still pasted into the terminal. |

Show the model plan per provider with [`fluid ai models`](./ai.md), and check connectivity with [`fluid ai test`](./ai.md#ai-test).

### Prompt profiles and overlays

| Option | Description |
| --- | --- |
| `--prompt-profile NAME` | Replace the whole set of default prompt guidance with a named profile. Bundled: `eu-gdpr-strict`, `ai-lab-permissive`. One profile at a time. Env: `FLUID_PROMPT_PROFILE`. |
| `--prompt-overlay NAMES` | Stack overlays on top of the defaults and any profile. Comma-separate names or repeat the flag; later overlays win. Bundled: `pii-lockdown`, `strict-json-reinforce`. Env: `FLUID_PROMPT_OVERLAYS`. |

An overlay is a YAML file that patches labelled prompt sections with `replace`, `append` or `prepend`, and can add `validator_rules` that the generated contract must satisfy. A name resolves to `<name>.yaml` under `~/.fluid/agent_specs/prompt_overlays/` (or under `$FLUID_USER_HOME`), then to the overlays bundled with the CLI. Overlays are parsed with a safe YAML loader, and a stack that drops a load-bearing instruction (for example "Return strict JSON only.") is rejected. Set `FLUID_OVERLAY_STRICT=1` to reject any overlay without a valid ed25519 signature; a present but invalid signature is rejected in every mode.

The active profile and overlays are written into the contract's provenance:

```yaml
metadata:
  provenance:
    ...
    prompt_profile: eu-gdpr-strict
    prompt_overlays:
    - pii-lockdown
```

An unknown profile fails with `unknown prompt profile` and lists the available names.

### Discovery and memory

| Option | Description |
| --- | --- |
| `--discover` | Inspect local files before generation. On by default. |
| `--no-discover` | Skip local discovery. |
| `--discovery-path PATH` | Add extra paths to scan. |
| `--memory` | Load copilot memory. On by default. |
| `--no-memory` | Skip memory for this run. |
| `--save-memory` | Persist memory after a successful run. |
| `--show-memory` | Print the memory summary and exit. |
| `--memory-json` | With `--show-memory`, print the layered memory as JSON. |
| `--reset-memory` | Delete memory and exit. |

### Composition and refinement

| Option | Description |
| --- | --- |
| `--from-product ID_OR_PATH` | Compose from an upstream product; repeatable. Each one becomes a `consumes[]` entry. See [`--from-product`](#from-product-—-composition). |
| `--from-product-list FILE` | Read upstream ids or paths from a file, one per line. |
| `--from-workspace PATH` | Search another workspace path for upstream contracts; repeatable. |
| `--refine [PATH]` | Load a contract and ask what to change. See [`--refine`](#refine-—-load-a-contract-and-tweak). |
| `--seed-from PATH` | Seed from an ODCS or Bitol ODPS contract. See [Seeding](#seeding-from-an-existing-odcs-or-bitol-odps-contract). |

### Resume

| Option | Description |
| --- | --- |
| `--resume [RUN_ID]` | Resume an interrupted run. With no value, picks the most recent paused run; with a run id or an unambiguous prefix, that run. |
| `--no-resume` | Skip the prompt that offers a paused run. |
| `--from-stage STAGE` | Time-travel to a stage. Pair it with `--resume RUN_ID` or `--fork RUN_ID`. |
| `--fork RUN_ID` | Like `--resume` under a new run id, copying stages up to `--from-stage`. Requires `--from-stage`. |
| `--or-fail` | Exit 1 if no run can be resumed. |

### CI scaffolding

| Option | Description |
| --- | --- |
| `--ci PROVIDER` | Generate a CI pipeline after forging: `github_actions`, `gitlab_ci`, `azure_devops`, `jenkins`, `bitbucket`, `circleci` (also spelled `circle_ci`), `tekton`, `none` or `ask`. |
| `--ci-complexity LEVEL` | `basic`, `standard` (default), `advanced` or `enterprise`. |
| `--no-ci` | Same as `--ci none`. |

## Single file or fragments?

A fragment-layout contract is a root file whose `builds`, `exposes`, `sovereignty` and `accessPolicy` entries are `$ref` pointers into `fragments/`. `validate`, `plan` and `apply` resolve the references themselves, so you run them on the root. Forge's own closing hint says so: `FLUID auto-bundles fragments when you run validate, plan, or apply`. See [Contract references (`$ref`)](../concepts/contract-refs.md) for the resolution rules, and [`fluid split`](./split.md) and [`fluid bundle`](./bundle.md) for converting between the layouts.

On the default AI-copilot path, forge chooses the layout in this order:

1. `--fragments` forces fragments. `--no-fragments` forces one flat file.
2. A `fragments/` directory that already exists in the target keeps the fragment layout.
3. Otherwise, forge splits the contract when it has two or more builds, two or more exposes, or a `sovereignty` or `accessPolicy` block. A single-build, single-expose contract with neither block stays flat.

The split is mechanical, not a model call:

```text
contract.fluid.yaml                  # root, with $ref entries
fragments/
├── sovereignty.yaml                 # when the contract has sovereignty
├── access-policy.yaml               # when the contract has accessPolicy
├── builds/<build-id>.yaml
└── exposes/<expose-id>.yaml
```

When forge splits, it prints the fragment files, then `Layout: Fragment-first (modular)` with two hints: `fluid bundle` to reassemble one contract, and `--no-fragments` to get a single file next time.

::: warning The flags are ignored on the other paths
The layout rule lives in the single-prompt AI path. `--blank`, `--offline`, `--no-llm` and `--template` (or `--scaffold`) write a flat `contract.fluid.yaml` even with `--fragments`: the flag is accepted, nothing changes, and forge ends with a `fluid split` hint. `--agent-loop` has no layout code either. As of 0.18.1, `fluid forge --help` does not list `--fragments` or `--no-fragments`. To fragment a contract written by those paths, run [`fluid split`](./split.md).
:::

If the product federates, note that `fluid contract digest` and the federation check read only the root file, so an edit inside a fragment does not change the digest. See [`fluid contract digest`](./contract.md#fluid-contract-digest).

## Resume, fork and time-travel

An AI-copilot run writes its stages to `.fluid/agents/<run-id>/`, so a paused or interrupted run can be resumed from there. (`fluid forge --blank` created no `.fluid/agents/` directory in the 0.18.1 test, so it has nothing to resume.)

```bash
fluid agents list --incomplete        # find the paused run
fluid forge --resume                  # resume the most recent paused run
fluid forge --resume 1a2b3c           # resume one run, by id or prefix
fluid forge --resume 1a2b3c --from-stage builder       # re-run from the builder stage
fluid forge --fork 1a2b3c --from-stage builder         # same, under a new run id
fluid forge --resume --or-fail        # exit 1 instead of starting fresh when nothing is paused
```

The stages, in order, are `logical`, `contract_forge`, `builder`, `readme`, `transformation`, `validator`, `enrichment` and `judge`. A misspelled stage fails with a "did you mean" hint and the list. `--from-stage` without `--resume RUN_ID` or `--fork RUN_ID` fails with `--from-stage requires --resume <run-id> or --fork <run-id>`. `--fork` without `--from-stage` fails with `--fork requires --from-stage (which stage of the source run to fork from)`.

With neither flag, forge offers a paused run when it finds one and you are at a terminal. `--no-resume` skips the offer, and `FLUID_FORGE_AUTO_RESUME=1` accepts it. [`fluid agents`](./agents.md) lists, shows and prunes runs.

## CI scaffolding after forge

`--ci` asks forge to write a pipeline once the contract exists:

```bash
fluid forge --blank --ci github_actions --ci-complexity basic --non-interactive --yes --target-dir o
```

```text
o/
├── .env.ci.example
├── .fluid/
│   ├── ci-state.json
│   └── forge-receipt.json
├── .github/workflows/fluid-pipeline.yml
└── contract.fluid.yaml
```

`ci-state.json` records the provider, complexity and inputs that produced the committed files, so a later run can tell when they drift. Forge decides whether to scaffold CI in this order, and stops at the first rule that answers:

1. `FLUID_FORGE_AUTO_CI` set to `0`, `false`, `no` or `off` disables it.
2. `--no-ci`.
3. `--ci PROVIDER`.
4. The provider recorded in `.fluid/ci-state.json`.
5. The provider saved in copilot memory.
6. An interactive menu.
7. Nothing, when none of the above applies and there is no terminal.

For finer control over what the pipeline contains, use `fluid generate ci` ([generate](./generate.md)) or [`fluid generate-pipeline`](./generate-pipeline.md).

## Forging a data model

The model-first path is `fluid forge data-model`. It writes a Fluid contract, a `.model.json` logical sidecar, and a human-readable Mermaid + Markdown model document.

```bash
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

Use `from-intent` for YAML/JSON business intent files, `from-ddl` for SQL DDL, and `from-source` for configured metadata catalogs.

The intent format is discoverable from the CLI:

```bash
fluid forge data-model from-intent --example
fluid forge data-model from-intent --example retail
fluid forge data-model from-intent --example telco
fluid forge data-model from-intent --example finance
fluid forge data-model from-intent --schema
fluid forge data-model from-intent --validate intent.yaml
```

### Data-model flags

`from-intent`, `from-ddl` and `from-source` share most of their flags. `fluid forge data-model <subcommand> --help` prints the full list.

| Option | Description |
| --- | --- |
| `--output`, `-o PATH` | Output contract path. Required for `from-ddl` and `from-source`. |
| `--modeling-technique`, `--technique` | `data_vault_2`, `dimensional`, `flat` (source-aligned, one to one) or `custom`. Aliases such as `data-vault-2` and `kimball` are accepted. |
| `--logical-model PATH` | A `.model.json` used verbatim with `--modeling-technique custom`. |
| `--transformation-engine`, `--engine` | Engine hint stamped into the contract: `dbt` (default), `sql`, `python`, `spark` or `custom`. |
| `--emit-ddl-dir DIR` | Also write DDL files for the logical model. |
| `--emit-dimensional-variants DIR` | Also write `star`, `snowflake`, `galaxy` and `flat` sidecars to `DIR`. |
| `--emit-model-doc`, `--no-emit-model-doc` | Write, or skip, the Mermaid and Markdown model document. On by default; the `.model.json` sidecar is written either way. |
| `--emit-osi-sidecar`, `--osi-sidecar-format {yaml,json}` | Write a standalone OSI interchange document (`*.semantics.osi.yaml`) next to the contract. The `json` format is the shape dbt Core 1.12 and later reads natively. |
| `--industry NAME` | Lint the model against an industry pack's canonical skeleton (`telecommunications`, `retail`, `healthcare`, `finance`). |
| `--allow-semantic-warnings` | Write artifacts even when the industry check still warns. |
| `--llm-timeout-seconds N` | Timeout for staged model calls. Default 120. |
| `--review`, `--dry-run`, `--deterministic`, `--require-llm`, `--tiered`, `--no-cache` | As on `fluid forge`. `--review` opens the logical sidecar in `$EDITOR`. |
| `--llm-provider`, `--llm-model`, `--llm-endpoint`, `--llm-routing-model`, `--llm-routing-endpoint` | As on `fluid forge`. |

`from-ddl` takes `--ddl FILE...` and `--source-type` (`snowflake`, `bigquery`, `postgres`, `postgresql`, `oracle`, `mysql`). `from-source` takes `--source`, `--credential-id`, `--database`, `--schema`, `--catalog`, `--tables`, `--name`, and `--uri` for the JDBC sources; `--allow-metadata-service` lets the credential resolver use cloud workload identity.

See the [Forge Data Model guide](../forge-data-model.md) for the field mapping, generated artifacts, deterministic mode, strict LLM mode, and dbt generation flow.

For hosted provider smoke tests, export a provider key in your shell and use `--require-llm`. Do not paste API keys into command examples, contracts, intent files, or docs.

## Seeding from an existing ODCS or Bitol ODPS contract

::: tip Available in 0.8.3 (experimental — pre-processor)
`--seed-from` accepts an ODCS contract, a Bitol ODPS product, or a directory bundle as a **structural seed** for the copilot. The schema / quality / qos from the seed are treated as ground truth; the LLM fills in builds, execution, and governance.
:::

If you already have an upstream ODCS or Bitol ODPS contract (your own, or one published by an upstream team), use `--seed-from` to skip the discovery phase entirely:

```bash
fluid forge --seed-from ./upstream.odcs.yaml
fluid forge --seed-from ./upstream.odps.yaml
fluid forge --seed-from ./bitol-bundle/             # directory with ODPS + sibling ODCS files
```

Accepted entry shapes:

- `*.odcs.yaml` — a lone Open Data Contract Standard v3.1.0 file
- `*.odps.yaml` — a Bitol ODPS data product file
- a **directory bundle** containing the ODPS doc plus sibling `<contractId>.odcs.yaml` files (or only ODCS files)

### Remote seeds — opt in to `http(s)` fetch

```bash
fluid forge --seed-from https://catalog.example.com/products/orders.odps.yaml --seed-allow-remote
```

Remote `http(s)` `contractId` references are **off by default** (the May 2026 SSRF hardening). `--seed-allow-remote` opts in to remote fetch; the fetcher rejects internal/private IPs, pins the validated IP, and caps the body at 10 MiB. Only enable when you trust the upstream catalog. See [network safety](/forge_docs/advanced/network-safety.html) for the full SSRF posture.

### Where the seed lands

The seed pre-processor lives at `fluid_build/cli/forge_copilot_seed.load_seed(...)` and is callable as a library. The copilot runtime hand-off plus the ground-truth diff guard (rejecting an LLM rewrite that mutates schema fields the seed pinned) are wired into the standard `fluid forge` flow.

## Forging from a source catalog

If your team already maintains rich metadata (descriptions, tags,
lineage, classifications) in a data catalog, you can skip the
intent / DDL inputs entirely and forge **directly from the catalog**:

```bash
fluid ai setup --source snowflake --name snowflake-prod      # one-time setup
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

Seven catalogs are supported — Snowflake Horizon, Databricks Unity,
BigQuery, Dataplex, AWS Glue, DataHub, Data Mesh Manager. Each
ships with privilege grant scripts, auth methods, and an
end-to-end demo. See the **[catalogs index](catalogs/README.md)**
for the full list.

The same flow is exposed via the MCP `forge_from_source` tool, so
Claude Code / Cursor agents can drive a catalog forge from inside
the editor.

## Mode picker, refine, compose

::: tip Available in 0.8.3
The 5-mode picker, `--refine`, `--from-product`, slash commands, preview panel, and the streaming contract preview ship in `0.8.3` (schema `0.7.3`). Pre-0.8.3 releases had the older single-shot interview shape.
:::

Bare `fluid forge` (TTY, no flags) lands on a 5-mode menu instead of dropping straight into AI:

```text
What kind of run is this?
  1. AI Copilot                  — full interview, LLM-driven (default for fresh products)
  2. Compose from existing       — build on top of products already in the workspace
  3. Refine a contract           — load a contract, ask 'what to change?'
  4. Template                    — start from one of the 5 built-in templates
  5. Blank scaffold              — empty contract, no AI
```

The picker pre-highlights based on a parallel welcome scan that runs in <50 ms. Skip with `FLUID_FORGE_NO_PICKER=1`.

### `--from-product` — composition

Pick one or more upstream products; Forge resolves them, validates composition rules (SDP rejects upstreams; ADP/CDP accept SDP+ADP — see [Product Types](/forge_docs/data-products/product-type.html#composition-rules)), and pre-fills `consumes[]`:

```bash
fluid forge --from-product bronze.crm_orders
fluid forge --from-product bronze.crm_orders --from-product bronze.crm_customers
fluid forge --from-product-list ./upstreams.json
```

### `--refine` — load a contract and tweak

```bash
fluid forge --refine                          # auto-discover from cwd
fluid forge --refine ./products/orders.fluid.yaml
```

Loads the contract, asks "what to change?", feeds the contract verbatim to the LLM as the seed. One question, no full interview.

### Slash commands inside the interview

| Command | Effect |
|---|---|
| `:ai-setup` | Re-run AI provider setup mid-interview |
| `:override` | Switch engine / restart / export state |
| `:show-work` | Toggle live streaming of agent reasoning + tool calls |
| `:doctor` | Inline `fluid doctor` |
| `:help` | List commands |
| `:quit` | Abort gracefully (saves partial state) |

### Pre-write preview panel

Before any file is written, Forge renders a panel showing files, cost, and run-id so users see exactly what they're about to commit to. `--yes` skips the confirmation prompt but the panel still renders. Suppress with `FLUID_FORGE_NO_PREVIEW=1`.

For the full picture see [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html).

## Headless agent mode

`fluid forge --agent` is a preset for agentic IDEs (Kiro, Cursor, Claude Code, Cline) and other automation that drives Forge without a human at the prompt:

```bash
fluid forge --agent
fluid forge --agent --emit-plan
```

- It bundles `--yes` and `FLUID_FORGE_NO_*=1`, and emits **JSON-Lines progress events** on stdout so the calling agent can stream status.
- It defaults to `--blank`, so it can never drop into the interactive mode picker.
- `--emit-plan` makes the run emit a single deterministic `forge.plan` event — the per-product-type (SDP / ADP / CDP) field checklist for the agent to fill in — instead of authoring the contract itself.

This is the CLI half of the agentic-IDE flow. Set the editor side up with [`fluid scaffold-ide`](./scaffold-ide.md), and the in-editor tools come from the [MCP server](./mcp.md).

## Notes

- The current promoted syntax is `fluid forge`, not `fluid forge --mode copilot`.
- Use `--domain` for built-in domain guidance instead of the older `--mode agent` flow shown in some legacy docs.
- Discovery and memory guides live in the advanced docs: [discovery](/forge_docs/advanced/forge-copilot-discovery) and [memory](/forge_docs/advanced/forge-copilot-memory).

## Industry skills

`--domain` gives the copilot a role such as finance or retail. For deeper vocabulary, typical products and regulatory constraints, install an industry skills pack with [`fluid skills`](./skills.md). The copilot reads the pack from `.fluid/skills.yaml` in the project.

```bash
fluid skills install telco
```
