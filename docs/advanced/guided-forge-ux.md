# Guided `fluid forge` UX

The `feat/source-aligned-acquisition` branch overhauls `fluid forge` end-to-end. The new flow is detect-first, mode-aware, slash-command-friendly, and never writes a file before showing you what it's about to write.

<iframe
  src="/forge_docs/reels/guided-forge-ux.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="23 questions, skipped — Fluid Forge guided UX">
</iframe>

Most CLIs ask 27 questions before they help. Forge asks four — the rest, it already knows. The reel above walks the welcome scan, mode picker, slash-command interview, streaming preview, and pre-write panel.

::: tip Where this fits
This page covers the new forge UX layer. The pinned 0.8.0 docs baseline has the older `fluid forge` shape (single-shot interview, no mode picker, no preview panel). This page documents the next-release surface.
:::

## Mode picker — the first 5 seconds

Bare `fluid forge` (no flags, TTY) lands on a 5-mode menu instead of dropping straight into AI. The picker is pre-highlighted based on a parallel welcome scan that runs in <50 ms:

```text
What kind of run is this?
  1. AI Copilot                  — full interview, LLM-driven (default for fresh products)
  2. Compose from existing       — build on top of products already in the workspace  ←
  3. Refine a contract           — load a contract, ask 'what to change?'
  4. Template                    — start from one of the 5 built-in templates
  5. Blank scaffold              — empty contract, no AI

Pick 1–5, or hit enter for highlighted default ▸
```

The default is chosen by the welcome scan:

| Workspace state | Pre-highlighted mode |
|---|---|
| No contract, no AI configured | AI Copilot (with prompt to run `:ai-setup`) |
| No contract, AI configured | AI Copilot |
| 1 existing contract in workspace | Refine |
| 2+ existing contracts | Compose from existing |
| Returning user (3+ runs in usage history) | Last-used mode |

### Skipping the picker

```bash
# CI / scripts — never show the picker
FLUID_FORGE_NO_PICKER=1 fluid forge --domain retail

# Force the picker even for return users
FLUID_FORGE_PICKER_ALWAYS=1 fluid forge

# Pass a flag — the flag wins, picker is skipped
fluid forge --refine        # goes straight into Refine
fluid forge --from-product orders.fluid.yaml
fluid forge --blank
fluid forge --template starter
```

## Welcome scan — what gets detected in <50 ms

`cli/_welcome_scan.py` runs a parallel detect step before any prompt. The detected facts feed the mode picker, the cost-cap progress prefix, and the slash-command suggestions:

| Detected | Source |
|---|---|
| Workspace state (contracts, sidecars, history) | `walk(.)` for `*.fluid.yaml` |
| AI configured | `~/.fluid/ai_config.json` exists + has a provider |
| CLI tools installed | `which dbt`, `which docker`, etc. (PATH only — no exec) |
| Sample data present | `data/` dir exists with rows |
| Cloud creds | `gcloud auth list`, `aws sts ...` (only if PATH has the CLI) |
| Return-user | `~/.fluid/usage.json::forge_count` |

The scan is **read-only** and bounded — if it can't complete in 50 ms the rest is dropped and forge proceeds.

Suppress with `FLUID_FORGE_NO_WELCOME=1`.

## Guided interview

The new default fresh-product interview is **inferences-first**. Before asking a question, the runtime computes `InterviewSignals` from:

- The welcome scan output
- Any partial contract in the cwd
- Memory hits (similar products in the workspace)
- The `--domain` / `--provider` hints

If the inference is high-confidence, the question is skipped (or shown as "Detected: X — change?"). Concretely:

| Question that used to be asked | What the new bootstrap does |
|---|---|
| "What's the data product name?" | Inferred from cwd or `--target-dir` if provided |
| "What's the product type?" | Asked with examples in the prompt; productType-first |
| "What domain is this in?" | Skipped if `--domain` provided or memory has a hit |
| "What sources do you have?" | Inferred from `data/` directory contents |

Every prompt offers `:auto` as an escape — type `:auto` to accept the inferred default and move on. The interview ends with a **schema-coverage gate**: the runtime checks that every required field of the resolved schema (0.7.3) is filled, prompts only for what's missing.

To revert to the legacy bootstrap (1.x interview shape), set `FLUID_INTERVIEW_LEGACY=1`.

## Mode-aware short-circuits

| Mode | Questions |
|---|---|
| AI Copilot (fresh) | Guided bootstrap (above) |
| Compose from existing | 3 questions max — name, type, what's the new ADP/CDP for |
| Refine | 1 question — "what to change?" — then the existing contract is fed verbatim to the LLM |
| Template | 0 LLM calls — argparse alias of `--scaffold` |
| Blank | 0 LLM calls |

The short-circuits live in `cli/forge_copilot_interview.py::run_adaptive_copilot_interview`.

## Slash commands inside the interview

Any `:command` typed at any prompt is intercepted by `cli/_interview_slash_commands.py`:

| Command | Effect |
|---|---|
| `:ai-setup` | Re-run AI provider setup mid-interview without losing answers |
| `:override` | Interrupt the current agent loop — switch engine, restart, or export state |
| `:show-work` | Toggle live streaming of the agent's reasoning + tool calls |
| `:doctor` | Inline `fluid doctor` (the same scopes the standalone command runs) |
| `:help` | List the available commands |
| `:quit` | Abort gracefully (saves partial state to `.fluid/agents/<run-id>/`) |

The slash commands are wrapped into `forge_dialogs.ask_friendly_text` so every prompt accepts them — no special "are slash commands available here?" reasoning required.

## Streaming contract preview

After every interview answer, `cli/_streaming_contract_preview.py` re-shapes the seed contract and renders a side panel showing what's growing:

```text
┌────────── contract.fluid.yaml ──────────┐
│ fluidVersion: "0.7.3"                   │
│ kind: DataProduct                       │
│ id: bronze.crm_orders                   │
│ metadata:                               │
│   layer: Bronze                         │
│   productType: SDP                      │
│   owner: { team: data-platform }        │  ← just added
│ ...                                     │
└─────────────────────────────────────────┘
```

The user sees the contract grow as they answer. Toggle off with `FLUID_FORGE_NO_STREAMING_PREVIEW=1`.

## Pre-write preview panel

Before any file is written, `cli/_preview_panel.py` renders a final panel showing:

- Files that will be created / overwritten
- Estimated cost (from the agent loop's cost tracker)
- The run-id (so users can find the artifacts later)
- Confirmation prompt

```text
┌──────────────── About to write ────────────────┐
│ Will create:                                    │
│   ./customer-orders/contract.fluid.yaml         │
│   ./customer-orders/data/orders.csv             │
│   ./customer-orders/README.md                   │
│                                                 │
│ Run-id:  2026-04-30T14-22-08                    │
│ Cost:    $0.012  (3,840 in / 720 out)           │
│ Model:   anthropic/claude-sonnet-4-6            │
│                                                 │
│ Proceed? [Y/n] ▸                                │
└─────────────────────────────────────────────────┘
```

`--yes` skips the prompt but the panel still renders. Cost figures are persisted at `.fluid/agents/<run-id>/cost.json` — `Ctrl-C` at the panel doesn't lose anything (transcript and reasoning are already on disk). Suppress the panel with `FLUID_FORGE_NO_PREVIEW=1`.

## Self-healing repair loop

After each emitted contract, `forge_copilot_runtime.py` runs the JSON-schema validator. If validation fails, the path-specific errors are prepended to the next attempt's repair feedback (via `forge_copilot_corrective_feedback.build_schema_validation_message`), and the agent retries. Most contracts converge within 1–2 repair cycles.

## Composition pipeline

`fluid forge --from-product` resolves upstream products, validates composition rules (SDP rejects upstreams; ADP/CDP accept SDP+ADP — see [Product Types](/forge_docs/data-products/product-type.html#composition-rules)), and pre-fills `consumes[]`:

```bash
# Pick one upstream
fluid forge --from-product bronze.crm_orders

# Multiple upstreams
fluid forge --from-product bronze.crm_orders --from-product bronze.crm_customers

# From a JSON list file
fluid forge --from-product-list ./upstreams.json
```

Where `upstreams.json` looks like:

```json
[
  { "id": "bronze.crm_orders", "path": "products/orders/contract.fluid.yaml" },
  { "id": "bronze.crm_customers", "path": "products/customers/contract.fluid.yaml" }
]
```

## Refine mode

`fluid forge --refine` loads an existing contract, asks "what to change?", and feeds the existing contract verbatim to the LLM as the seed (via `_seed_contract_override`). One question, no full interview.

```bash
fluid forge --refine                          # auto-discover the contract in cwd
fluid forge --refine ./products/orders.fluid.yaml
```

## Cost-cap progress prefix

Set a per-run USD budget to see a live progress prefix:

```bash
FLUID_COST_LIMIT_USD_PER_RUN=0.50 fluid forge
```

```text
[$0.012/$0.50 · 12% · gemini-2.5-flash] What's the product domain?
```

Useful for keeping demo runs predictable and for CI runs where you want hard cost discipline.

## UX telemetry

When an OTel exporter is configured, the run emits these per-invocation fields onto the `forge.invocation` span:

- `time_to_first_panel_ms` — how long until the user saw the first panel
- `questions_asked` — number of interview questions answered
- `inferences_used` — number of times the runtime skipped a question because of inference
- `picker_choice` — which mode the user picked (or what the picker pre-highlighted)
- `mode` — the resolved mode (ai / compose / refine / template / blank)
- `preview_accepted` — whether the user accepted the pre-write panel
- `schema_repair_attempts` — how many times the self-healing loop fired

No telemetry is sent when no exporter is configured.

## Environment variables

| Env var | Purpose |
|---|---|
| `FLUID_FORGE_NO_PICKER` | Suppress the mode picker (CI / scripts) |
| `FLUID_FORGE_PICKER_ALWAYS` | Force the picker even for return users |
| `FLUID_FORGE_NO_WELCOME` | Suppress the welcome scan render |
| `FLUID_FORGE_NO_STREAMING_PREVIEW` | Suppress the live contract growth panel |
| `FLUID_FORGE_NO_PREVIEW` | Suppress the pre-write preview panel + prompt |
| `FLUID_FORGE_AUTO_CI` | Auto-enable CI mode (no TTY prompts) |
| `FLUID_INTERVIEW_LEGACY` | Revert to the legacy 1.x interview bootstrap |
| `FLUID_COST_LIMIT_USD_PER_RUN` | Per-run cost cap shown in the progress prefix |

## See also

- [`fluid forge`](/forge_docs/cli/forge.html) — the CLI reference
- [Product Types — composition rules](/forge_docs/data-products/product-type.html#composition-rules) — what `--from-product` enforces
- [LiteLLM Backend](/forge_docs/advanced/litellm-backend.html) — opt-in unified LLM routing for accurate per-call cost
- [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html) — error catalog (the schema-validation errors the self-healing loop catches)
- [Cost Tracking](/forge_docs/advanced/cost-tracking.html) — what `cost.json` contains
