# `fluid stats`

Aggregate cost across forge runs. Walks `.fluid/agents/*/cost.json` records and groups by provider, product type, engine, or run.

::: tip Where this fits
`fluid stats` ships with the guided forge UX in `0.8.3`.
:::

## Syntax

```bash
fluid stats [options]
```

## Options

| Option | Description |
|---|---|
| `--by {provider\|type\|engine\|run}` | Group results by LLM provider, productType (SDP/ADP/CDP), transformation engine, or run. Default: total only. |
| `--since <spec>` | Restrict to recent runs. Accepts relative (`24h`, `7d`, `30d`) or ISO date (`2026-04-01`). Default `30d`. |
| `--root <path>` | Workspace root to scan. Default: current directory. |
| `--json` | Emit JSON instead of the human table. |

## Examples

```bash
# Last 30 days, total only
fluid stats

# Last 7 days, broken out by LLM provider
fluid stats --by provider --since 7d

# Since a specific date, broken out by data product type
fluid stats --by type --since 2026-04-01 --json

# Per-run breakdown with full timing
fluid stats --by run --since 24h
```

## Output (human table)

```text
fluid stats — last 30 days
──────────────────────────────────────────────────────────────
Provider                  Runs      Tokens (in/out)        USD
──────────────────────────────────────────────────────────────
anthropic/claude-sonnet     14   28,440 / 5,120        $0.273
openai/gpt-4.1-mini          8    9,210 / 1,890        $0.043
gemini/gemini-2.5-flash      3      820 /   240        $0.005
ollama/gemma4:31b            5    7,230 / 1,540        $0.000
──────────────────────────────────────────────────────────────
Total                       30   45,700 / 8,790        $0.321
```

## Output (JSON)

```json
{
  "since": "2026-03-30T00:00:00Z",
  "by": "provider",
  "totals": {
    "runs": 30,
    "input_tokens": 45700,
    "output_tokens": 8790,
    "total_usd": 0.321,
    "wall_clock_seconds": 145.6
  },
  "groups": {
    "anthropic/claude-sonnet": {
      "runs": 14,
      "input_tokens": 28440,
      "output_tokens": 5120,
      "total_usd": 0.273,
      "wall_clock_seconds": 67.2
    }
  }
}
```

## What gets aggregated

Every `fluid forge` run writes `.fluid/agents/<run-id>/cost.json` containing the per-call cost breakdown. `fluid stats` reads those files; nothing leaves the workspace.

For LiteLLM-backed runs (`FLUID_LLM_BACKEND=litellm`), the cost field comes directly from LiteLLM's per-call attribution, not from the heuristic estimator. See [LiteLLM Backend](/forge_docs/advanced/litellm-backend.html) for accuracy notes.

## See also

- [Cost Tracking](/forge_docs/advanced/cost-tracking.html) — how the cost figures are computed
- [LiteLLM Backend](/forge_docs/advanced/litellm-backend.html) — accurate per-call cost via LiteLLM
- [`fluid forge`](/forge_docs/cli/forge.html) — the runs that produce these records
