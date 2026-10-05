# Cost Tracking

Every `fluid forge data-model` invocation prints a per-run cost
summary. CLI-only — no UI, no dashboard, just a one-block panel
in the terminal:

```
Cost summary
─────────────────────────────────────────────────────────────────
  anthropic / claude-sonnet-4-6     12,453 in   3,827 out  $0.0247
  anthropic / claude-haiku-4-5         876 in     412 out  $0.0006
─────────────────────────────────────────────────────────────────
  total                            13,329 in   4,239 out  $0.0253
```

This page documents the price table, the per-org override path,
the cost ceilings, the missing-usage warning footer, and the
variant-lint surfacing. It covers the cost of the LLM calls an AI-assisted
`fluid forge` makes.

::: tip Looking for the acquisition cost budget?
`BudgetExceededError` and the `cost.budget` block of an acquisition build are a different feature. Its message links here, but the budget is described under [Cost tracking and budget gates](./source-aligned-acquisition.md#cost-tracking-and-budget-gates) on the acquisition page, including the fact that no engine enforces it yet.
:::

## Embedded price table

Prices live in `fluid_build/copilot/cost.py::MODEL_PRICES_USD` —
USD per 1M tokens, `(input_price, output_price)` tuples. Source:
each provider's public pricing page. Snapshot date is in the
module docstring. The excerpt below shows the shape; the table has more models.

The table is a frozen Python dict, not a pulled-at-runtime
catalog. Stale entries fail loud-but-safe — unknown models
surface with `$?` instead of a misleading `$0.00`.

```python
MODEL_PRICES_USD: Dict[str, Tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-7": (15.00, 75.00),
    "gpt-4.1": (2.50, 10.00),
    "gpt-4.1-mini": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.075, 0.30),
    # Ollama is local — provider-name match wins, returns $0 for any model.
    "*ollama*": (0.0, 0.0),
}
```

When forge-cli sees a model not in the table:

```
Cost summary
─────────────────────────────────────────────────────────────────
  openai / future-gpt-9000   1,000 in   500 out   $?
─────────────────────────────────────────────────────────────────
  total                      1,000 in   500 out   $?

  Note: no price table entry for 'future-gpt-9000'.
  Update fluid_build/copilot/cost.py:MODEL_PRICES_USD.
```

Total is `$?` whenever any row is unknown — defends against
partial sums that look authoritative.

## Cost ceilings

Two environment variables stop a forge run that spends more than you intend:

| Env var | Ceiling |
|---|---|
| `FLUID_COST_LIMIT_USD` | The total for one invocation, in USD |
| `FLUID_COST_LIMIT_USD_PER_PRODUCT` | One product, when an invocation forges several (`--from-product-list`) |

```bash
FLUID_COST_LIMIT_USD=5 fluid forge data-model from-intent intent.yaml -o out.fluid.yaml
```

The check runs before each LLM call, against the projected cost, and again after each call is recorded. A run over its ceiling stops with:

```text
Cost ceiling exceeded: running $5.2301 > limit $5.0000. Set FLUID_COST_LIMIT_USD or behavior.cost_limit_usd_per_run in ~/.fluid/config.yaml to a higher value, or run with --no-cost-limit to disable.
```

A value that is not a positive number means no ceiling. The ceiling is not enforced while any row in the summary has an unknown price (`$?`), because the total cannot be measured. As of 0.18.1 the message's last suggestion is wrong: there is no `--no-cost-limit` flag. Unset the variable instead.

## Per-org price override

Enterprise customers negotiate rates that don't match the
embedded list price. The override file at `~/.fluid/prices.json`
patches in your negotiated rates without forking forge-cli:

```jsonc
{
  "schema_version": 1,
  "prices": {
    "claude-sonnet-4-6": [2.40, 12.00],
    "gpt-4.1": [2.00, 8.00]
  }
}
```

The flat layout `{"model": [in, out]}` is also accepted — operators
scribbling overrides don't have to look up the wrapped schema.

### Path resolution order

1. `$FLUID_PRICES_JSON` — explicit override (used by tests).
2. `$FLUID_HOME/prices.json` if `$FLUID_HOME` is set.
3. `~/.fluid/prices.json` (default).

### Failure modes (always silent fallback)

- Override file missing → embedded table wins. No warning.
- Override JSON malformed → embedded table wins. Logged at DEBUG.
- Negative price in override → that entry skipped (rest applied).
- Wrong-shape entry (e.g. `[0.10]` instead of `[0.10, 0.40]`) → that
  entry skipped, rest applied.

The override file is operator-edited, so syntax errors are real
possibilities. We never let a malformed override break a forge
run.

## Missing-usage warning footer

Some providers ship empty `usage` blocks under load (or on
streaming-cancellation paths, or on certain Azure deployments).
Without a counter, the user would see a misleading "$0.0042"
total with no hint that the figure is under-reported.

Forge counts calls that report no usage:

```
Cost summary
─────────────────────────────────────────────────────────────────
  openai / gpt-4.1-mini     12,453 in   3,827 out  $0.0042
─────────────────────────────────────────────────────────────────
  total                     12,453 in   3,827 out  $0.0042

  Note: 2 calls had no usage data; cost may be under-reported.
```

The counter increments on two paths:

1. **`extract_usage` exception** — provider's usage extractor
   blew up. The call is recorded as missing without per-row
   token data.
2. **0/0 token counts on a non-Ollama provider** — the LLM
   responded but the provider ate the usage block.

Ollama is special-cased: its `(0, 0)` baseline is legitimate
(local compute, no token counts) so 0/0 calls there don't flag.

::: tip Streaming runs report usage
Streamed calls report token usage the same way blocking calls do, so
the footer does not appear just because a call was streamed.
:::

The counter resets per run. `fluid forge data-model` calls
`reset_run_tracker()` at start so the summary reflects only the
current invocation.

## Variant-lint warning footer

When the dimensional variant validator runs (per-Kimball-flavor
lint), warnings flow into the validation report. Forge also
surfaces them in the cost summary footer so operators
piping stdout to a log see the lint score next to the cost:

```
Cost summary
─────────────────────────────────────────────────────────────────
  anthropic / claude-sonnet-4-6   12,453 in   3,827 out  $0.0247
─────────────────────────────────────────────────────────────────
  total                           12,453 in   3,827 out  $0.0247

  Note: 2 variant-lint warnings on variant='snowflake'.
  See validation report for details.
```

The footer:

- Shows one line per variant with non-zero warnings (sorted alphabetically).
- Pluralises correctly ("1 warning" vs "2 warnings").
- Replaces (not accumulates) on repair-loop reruns — the count
  reflects the FINAL pass, not all retries summed.
- Is silent when every variant lint passes — no false alarms.

## What gets tracked

Every staged LLM call goes through `BaseStageAgent._call_once`,
which after parsing the response calls
`get_run_tracker().record_call()`:

```python
get_run_tracker().record_call(
    provider=provider.name,
    model=config.model,
    input_tokens=int(usage.get("input_tokens", 0) or 0),
    output_tokens=int(usage.get("output_tokens", 0) or 0),
)
```

::: tip Anthropic prompt-cache tokens are visible in the breakdown
On Anthropic, the `usage` block also carries `cache_read_input_tokens`
and `cache_creation_input_tokens` (and Gemini emits
`cachedContentTokenCount` for its context-cache feature). When you
run a multi-stage pipeline (`fluid forge data-model from-intent`) the
system prompt is identical across stages, so the cache hit rate tends
to be 80–90% on calls 2..N. Concretely: a 9-stage Anthropic run that
would have charged for 36K input tokens at full rate often comes in
around 7K equivalent input-token cost — the discount shows up in the
per-call cost figures because the price table maps cache-read tokens
to the discounted rate.
:::

The tracker is a module-level singleton because it has to be
written from threads (parallel-physical fan-out runs three
agents concurrently) without threading a context object through
the entire pipeline. The lock is per-instance.

## Hermetic tests

The price table itself is regression-pinned:

```python
def test_price_table_entries_well_formed():
    """Every entry is a (in, out) tuple with non-negative numeric prices."""
    for model, prices in MODEL_PRICES_USD.items():
        assert isinstance(prices, tuple)
        assert len(prices) == 2
        for p in prices:
            assert isinstance(p, (int, float))
            assert p >= 0
```

Override semantics, missing-usage flags, and variant-lint
surfacing are covered by `tests/copilot/test_cost_tracking.py` in
the `forge-cli` repository.

## See also

- [Cost summary in `fluid forge data-model`](../cli/forge.md)
- [Catalog integration architecture](v1.5-architecture.md)
- [Cost tracking and budget gates for acquisition builds](./source-aligned-acquisition.md#cost-tracking-and-budget-gates)
