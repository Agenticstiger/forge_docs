# `fluid stats`

Add up the cost of `fluid forge` runs: tokens, dollars and wall-clock time, optionally grouped by LLM provider, product type, engine, run or mode. It reads receipts that are already on disk, so it makes no network call and sends nothing anywhere.

::: tip Where this fits
`fluid stats` ships with the guided forge UX in `0.8.3`.
:::

## Syntax

```bash
fluid stats [--by {provider|type|engine|run|mode}] [--since SPEC] [--root PATH] [--json] [--judge]
```

## Examples

Total for the last 30 days:

```bash
fluid stats
```

```text
fluid stats — 3 runs · 32,610 tokens · $0.1089 · 65.2s wall-clock
```

Break it down by LLM provider:

```bash
fluid stats --by provider
```

```text
fluid stats — 3 runs · 32,610 tokens · $0.1089 · 65.2s wall-clock
┏━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ Provider  ┃ Runs ┃ Tokens ┃     USD ┃
┡━━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ (unknown) │    1 │      0 │ $0.0000 │
│ anthropic │    1 │ 21,330 │ $0.1014 │
│ gemini    │    1 │ 11,280 │ $0.0075 │
└───────────┴──────┴────────┴─────────┘
```

Separate runs that called an LLM from deterministic runs that did not:

```bash
fluid stats --by mode
```

```text
fluid stats — 3 runs · 32,610 tokens · $0.1089 · 65.2s wall-clock
┏━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ Mode          ┃ Runs ┃ Tokens ┃     USD ┃
┡━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ deterministic │    1 │      0 │ $0.0000 │
│ llm           │    2 │ 32,610 │ $0.1089 │
└───────────────┴──────┴────────┴─────────┘
```

Restrict to runs since a date, one row per run:

```bash
fluid stats --since 2026-10-01 --by run
```

```text
fluid stats — 2 runs · 11,280 tokens · $0.0075 · 24.0s wall-clock
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ Run                    ┃ Runs ┃ Tokens ┃     USD ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ 20261001-124156-a1b2c3 │    1 │ 11,280 │ $0.0075 │
│ 20261001-164156-a1b2c3 │    1 │      0 │ $0.0000 │
└────────────────────────┴──────┴────────┴─────────┘
```

The examples read three `cost.json` receipts under `.fluid/agents/`. Without `--by`, the output is the header line only.

## Options

| Option | Description |
| --- | --- |
| `--by {provider\|type\|engine\|run\|mode}` | Group the results. `provider` is the LLM provider recorded in each receipt, `type` the product's `metadata.productType` (SDP, ADP, CDP), `engine` the first build's engine, `run` the run directory, and `mode` splits `deterministic` runs from `llm` runs. Default: the total only. |
| `--since SPEC` | Only runs that started on or after this point. Accepts `30d`, `24h` (days and hours back from now) or an ISO date such as `2026-04-01`. Default `30d`. Anything else exits `2` with `error: --since must look like '30d', '24h', or an ISO date`. |
| `--root PATH` | The directory to scan. Default: the current directory. A path with no receipts gives an empty total, not an error. |
| `--json` | Emit JSON instead of the table. |
| `--judge` | Aggregate `judge.json` receipts (scores from an out-of-loop LLM judge) instead of `cost.json`. Not combinable with `--by`: that exits `2`, and the message says to group from the `--json` output. |

## What gets aggregated

An LLM-assisted `fluid forge` run writes `.fluid/agents/<run-id>/cost.json`. `fluid stats` scans `--root` recursively for those files and reads these keys from each:

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-5",
  "mode": "llm",
  "input_tokens": 18210,
  "output_tokens": 3120,
  "total_tokens": 21330,
  "total_usd": 0.1014,
  "wall_clock_seconds": 41.2
}
```

- The run ID is the directory name, in the form `YYYYMMDD-HHMMSS-<suffix>` in UTC. `--since` compares against the timestamp in that name. A directory whose name does not parse is never filtered out.
- `--by type` and `--by engine` read the product's `contract.fluid.yaml` from the directory that holds `.fluid/`. A run with no readable contract, or a contract without that field, is grouped under `(unknown)`, as is any run whose receipt has no `provider` (the first row of the provider table above).
- A receipt with no `mode` counts as `deterministic` when it recorded no tokens and no calls, and as `llm` otherwise.
- A receipt with no `total_usd` adds tokens and time to the totals but no cost.

For LiteLLM-backed runs (`FLUID_LLM_BACKEND=litellm`), the cost comes from LiteLLM's per-call attribution, not from the heuristic estimator. See [LiteLLM backend](../advanced/litellm-backend.md) for accuracy notes.

## JSON output

`--json` prints `total` and `runs_count`. With `--by`, it adds `by` (the dimension) and `groups` (one object per group, sorted by name). Each group has the same fields as `total`: `runs`, `input_tokens`, `output_tokens`, `total_tokens`, `total_usd` and `wall_clock_seconds`.

```bash
fluid stats --by provider --json
```

```json
{
  "by": "provider",
  "groups": {
    "(unknown)": {
      "input_tokens": 0,
      "output_tokens": 0,
      "runs": 1,
      "total_tokens": 0,
      "total_usd": 0.0,
      "wall_clock_seconds": 1.4
    },
    "anthropic": {
      "input_tokens": 18210,
      "output_tokens": 3120,
      "runs": 1,
      "total_tokens": 21330,
      "total_usd": 0.1014,
      "wall_clock_seconds": 41.2
    },
    "gemini": {
      "input_tokens": 9400,
      "output_tokens": 1880,
      "runs": 1,
      "total_tokens": 11280,
      "total_usd": 0.0075,
      "wall_clock_seconds": 22.6
    }
  },
  "runs_count": 3,
  "total": {
    "input_tokens": 27610,
    "output_tokens": 5000,
    "runs": 3,
    "total_tokens": 32610,
    "total_usd": 0.1089,
    "wall_clock_seconds": 65.2
  }
}
```

In a script, read `total.total_usd` for the cost, `runs_count` for how many runs matched, and `groups` for the breakdown:

```bash
fluid stats --since 7d --json | jq '.total.total_usd'
```

With nothing to aggregate, the same keys come back as zeros and `groups` is empty. The table output has no per-group split of input and output tokens and no total row; `--json` carries the split.

## See also

- [Cost tracking](../advanced/cost-tracking.md): how the cost figures are computed
- [LiteLLM backend](../advanced/litellm-backend.md): accurate per-call cost via LiteLLM
- [`fluid forge`](./forge.md): the runs that produce these receipts
