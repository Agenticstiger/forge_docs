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
the missing-usage warning footer, and the variant-lint surfacing
— all V2 polish items shipped with V1.5.

## Embedded price table

Prices live in `fluid_build/copilot/cost.py::MODEL_PRICES_USD` —
USD per 1M tokens, `(input_price, output_price)` tuples. Source:
each provider's public pricing page. Snapshot date is in the
module docstring.

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

V1.5+V2 polish wires a missing-usage counter:

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

The counter resets per run. `fluid forge data-model` calls
`reset_run_tracker()` at start so the summary reflects only the
current invocation.

## Variant-lint warning footer

When the dimensional variant validator runs (per-Kimball-flavor
lint), warnings flow into the validation report. V1.5+V2 polish
also surfaces them in the cost summary footer so operators
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
surfacing are all covered by `tests/copilot/test_cost_tracking.py`
(39 tests).

## See also

- [Cost summary in `fluid forge data-model`](../cli/forge.md)
- [V1.5 architecture](v1.5-architecture.md)
