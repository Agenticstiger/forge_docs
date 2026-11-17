# `fluid profile`

Profile one expose's records where they live, and write a profile document of output-checked aggregates. A FLUX Simulation pins the document by its digest, so the FLUX engine reads aggregates of the real data and never a record of it.

*(since 0.31.0, [forge-cli #909](https://github.com/Agenticstiger/forge-cli/pull/909), [forge-cli #925](https://github.com/Agenticstiger/forge-cli/pull/925), [forge-cli #946](https://github.com/Agenticstiger/forge-cli/pull/946), [forge-cli #949](https://github.com/Agenticstiger/forge-cli/pull/949), [forge-cli #951](https://github.com/Agenticstiger/forge-cli/pull/951))*

FLUX's statistic registry, `flux-stats`, reads every value and forms every statistic. The fidelity check uses the same registry, so a profile and a check of the same records hold the same numbers.

The `[profile]` extra installs DuckDB and `flux-stats` (`>=0.6.0,<0.7`) from PyPI. Without flux-stats, `fluid profile` stops before it reads anything and says what to install:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: fluid profile forms every statistic with flux-stats, the statistic registry FLUX shares with its fidelity check, and flux-stats is not installed. It needs flux-stats>=0.6.0,<0.7; install it with: pip install 'data-product-forge[profile]'
  read: nothing: no record was read
  next: pip install 'data-product-forge[profile]'
```

If a `flux-stats` distribution is installed but cannot be imported, the detail names its version instead. PyPI's `flux-stats` 0.0.1 is a placeholder that holds no code, and the extra's range replaces it.

## Before you start

`fluid profile` profiles an expose that a FLUID contract declares. If your data is in a file and you have no contract for it yet, let [`fluid init --discover`](./init.md) write one from the file's schema. It reads files with DuckDB, which the `[profile]` extra installs:

```bash
fluid init orders --discover "file://$PWD/data"
```

It writes one contract per file in `data/`, here `contract.orders.fluid.yaml` for `data/orders.parquet`, with the columns and types it found and no records. The project name, `orders`, goes into the product id. Read the contract and correct what a schema cannot tell, such as which columns are required. Then profile the expose it declares:

```bash
fluid profile contract.orders.fluid.yaml --expose orders --source data/orders.parquet
```

## Where it runs

The profiler is the one part of FLUX that reads records. It runs inside the environment that holds the data, with that environment's own access to it. Only the profile document leaves: no record, no sample of records, and no per-record value. That is the boundary FLUX keeps, and everything that crosses it has passed the checks below.

## Syntax

```bash
fluid profile CONTRACT --source SOURCE [--expose ID] [--table NAME] [--out FILE] [--fractional-bits N] [--env ENV]
```

| Argument | What it does |
|---|---|
| `CONTRACT` | The FLUID contract (or a stage-1 bundle `.tgz`) that declares the expose. Its `exposeId` keys the profile's table, and each column's type gives the domain it is read in. |
| `--source` | Where the records live. See [Sources](#sources). |
| `--expose`, `--expose-id` | The expose to profile. Optional when the contract has one expose. |
| `--table` | The table of a database `--source`, as `name` or `schema.name`. Refused for a file. |
| `--out` | Where to write the document. Default: `<exposeId>.profile.json` in the current directory. |
| `--fractional-bits` | The grid [`mean/1`](#the-mean-1-statistic) is formed on, in steps of 2^-N: 0 to 128, default 16. Set it to the fidelity block's `encoding.fractionalBits`. |
| `--env` | An environment overlay to apply to the contract first. |

Install the extra, which adds DuckDB and flux-stats:

```bash
pip install 'data-product-forge[profile]'
```

`fluid profile` is in 0.31.0 and later.

## Sources

`fluid profile` reads every record of the table once. It does not sample.

| `--source` | Read how |
|---|---|
| a `.ndjson` or `.jsonl` file | As FLUX reads a committed slice: one JSON object per line, blank lines skipped. A number written as a JSON float (`12.5`) is refused; write it as a decimal string (`"12.50"`). |
| a `.csv` file | Through DuckDB, every column as text, so a decimal arrives as the digits the file holds. |
| a `.parquet` file | Through DuckDB, with the file's own types. |
| `postgres://`, `postgresql://`, `mysql://` or `sqlite:///` | Attached read-only, the way `fluid init --discover` attaches a database. Name the table with `--table`. A sqlite path that does not exist is refused, not created. The URI's password is never printed. |

A path can be relative, absolute or a `file://` URL. DuckDB runs in the same sandbox as the rest of forge-cli, allowed the one file it reads.

A timestamp value is read as RFC 3339 with an offset (`2026-07-01T10:00:00.000Z`). FLUX's clock counts milliseconds, so a value with finer precision is refused. A database or Parquet timestamp with a zone is read as its UTC instant, and one with no zone as UTC.

A date or timestamp that is infinite (PostgreSQL's `infinity`) is refused, by column, rather than read as the year 9999. Every value of the profiled columns is held in memory while it is measured, so a table larger than the machine's memory is out of reach for now.

A number that needs more than 1,000 digits written out, such as `1E+5000`, is refused by its cell before it is read, as `value class 'over-long number'`: a profile declares no range to bound it. A sum longer than 1,000 digits is refused when the document is checked, and nothing is written.

## What is profiled

For each column whose FLUID type has a profile domain, the document holds the seven OpenLineage column metrics that apply to it, and the table's `rowCount`:

| Domain | FLUID types | Metrics |
|---|---|---|
| `number` | `integer`, `bigint`, `decimal(p,s)`, `numeric`, `number`, `money`, `year`, ... | `count`, `nullCount`, `distinctCount`, `sum`, `min`, `max`, `quantiles` (0.25, 0.5, 0.75) |
| `timestamp` | `timestamp`, `timestamptz`, `datetime`, `date`, ... | the same, without `sum` (values in milliseconds since the epoch) |
| `category` | `string`, `varchar(n)`, `uuid`, `enum`, ... | `count`, `nullCount`, `distinctCount` |

These columns are left out and named in the output:
- binary floating point (`float`, `double`, `real`), which FLUX keeps out of every exact path;
- nested values (`json`, `array`, `struct`, ...);
- bytes;
- a bare time of day;
- intervals;
- geospatial values;
- booleans, which FLUX's reader does not read yet.

## The `mean/1` statistic

For each `number` column the document also holds `mean/1`, the statistic FLUX's fidelity check compares a `mean` property with. Its one group holds `k`, the number of non-null values, and `Sx`, their sum on the document's grid: each value is floored to a multiple of 2^-N and counted in those steps, as the check counts the synthetic rows. flux-stats forms it with the definition the check uses.

```json
"amount": {
  "domain": "number",
  "metrics": {},
  "statistics": [
    {
      "definition": "mean/1",
      "sampleSize": {"min": 598, "max": 602},
      "disclosure": "acro-default",
      "groups": [{"group": "", "k": 600, "Sx": "1818624000", "status": "F"}]
    }
  ]
}
```

That is the `amount` column of the 600 orders in [the FLUX guide](https://agenticstiger.github.io/flux/guide/from-your-data.html), with its metrics left out here. The amounts sum to 27750, so `Sx` is 27750 × 2^16 and the mean is 46.25.

Two things to know about the numbers:
- `k` is rounded to a multiple of 5, as `count` is, so the mean the engine reads is the exact sum over the rounded count. It can be off the records' own mean by up to 2/k of it: 20% at 12 records, at most 1% from 200. An exact mean next to the exact `sum` would give the exact count back.
- Most decimals, cents among them, are not on a binary grid, so each value loses a little when it is floored. Next to the exact `sum`, `Sx` gives the total of those losses, so the mean is withheld when that total would act as a count or show one record: when the records lose at most two different amounts, a loss of nothing counting as one (prices that all end in .99, or half whole numbers and half ending in .99), or when fewer than 10 records lose anything. A column of varied cents publishes its mean. Whole numbers and halves lose nothing.

The grid is the document's `encoding.fractionalBits`, 16 unless you pass `--fractional-bits`. The fidelity block must declare the same `encoding`, or the engine refuses the property with `FLX-5037` and names both grids. A block that declares no `encoding` uses 16. The summary names the grid:

```text
Fidelity statistics: mean/1 of 'amount', on fractionalBits 16 (the fidelity block must declare the same).
```

`mean/1` is written without a `groupBy`, and for number columns only. A timestamp or category column gets no statistic: a mean of timestamps would publish a sum that no metric publishes. `fluid profile` writes no other statistic yet: no histogram, `quantile/1`, `support/1` or `correlation/1`, and no `mean/1` with a `groupBy`. The engine refuses a property that reads one with `FLX-5037`.

## What leaves: the output checks

Every value is checked before the document is written. The checks are ACRO's defaults (ACRO 1.1.0, from the SACRO project). The document names them as the rule `acro-default`:

| Check | Rule | A withheld value's code |
|---|---|---|
| Threshold | a count of 1 to 9 records is withheld | `A` |
| Zeros | a count of zero is withheld | `A` |
| Rounding | every published count is a multiple of 5, and a positive count that would round to 0 is withheld | `A` |
| Contributors | a sum is withheld when fewer than 10 records hold a non-zero value: a sum of 0s and 1s is a count | `A` |
| Two values or fewer | a sum is withheld when its records hold at most two values: with `min` and `max` published, it would give each count back | `C` |
| Dominance (2, 0.90) | a sum is withheld when 1 or 2 records make up 90% of it | `O` (one), `T` (two) |
| p-ratio 0.10 | a sum is withheld when what is left after the 2 largest records is below 10% of the largest | `M` |
| Order statistics | a `min`, `max` or quantile is published only when at least 10 records hold that exact value | `A` |
| Means | a `mean/1` is published only when the column's `count` and `sum` are, and when its values on the grid pass the `sum` checks too, because values less than one grid step apart floor to one value. Next to the exact `sum`, `Sx` also gives the total of what the values lose below their grid points, so that total must pass the `sum` checks as well. Its `k` is rounded like every count | the code of the check that failed |

A withheld value keeps its SDMX `CL_CONF_STATUS` code and carries no value: a withheld `mean/1` group holds its code and no `k` or `Sx`, and FLUX scores it as censored, never as zero. Every metric also carries `sampleSize`, the band its number of records lies in. For a withheld count the band is `0` to `9`, and for a published one it is the counts that round to it. Neither says more than the code or the rounded count.

Two consequences to expect:
- A column with 1 or 2 distinct values withholds its `distinctCount`: it rounds to 0, and a published 0 would read as a zero cell.
- If any one quantile level's value is held by fewer than 10 records, the whole `quantiles` metric is withheld.

::: warning No privacy guarantee
These are output-checking conventions only. No privacy or anonymity guarantee is made or implied. ACRO's tools assist human output checkers and do not replace them: read the document before you share it.
:::

## Output

```bash
fluid profile contract.fluid.yaml --expose payment --source ./payment.parquet
```

```text
Profiled exposes[payment]: 4 columns, 21 values published, 3 withheld.
Withheld, by CL_CONF_STATUS code: A (small count) 3.
Not profiled: column 'raw': a nested value has no profile domain.
Not profiled: column 'score': binary floating point has no exact reading (KERNEL-SPEC §2.1).
Wrote /data/payment.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:32aefe6ed451030bb4961edc5750d8f4cd0ea1b05a741168390abc1faba19285}
```

The document is FLUX's profile format `1-0-0` in canonical JSON (RFC 8785), so the file's own sha256 is the digest. The same forge-cli release, given the same records, writes the same bytes, whichever of the four kinds of source they come from. The document names the release in `_producer`, so another release writes another digest. Pin the digest in the Simulation: copy the line the command printed into the `com.agentics.flux/1` namespace of the Simulation's `extensions`, indented to sit beside `emits`:

```yaml
extensions:
  com.agentics.flux/1:
    profile: {digest: sha256:32aefe6ed451030bb4961edc5750d8f4cd0ea1b05a741168390abc1faba19285}
    emits:
      payment:
        # the emit's declarations
```

Nothing is written, and no directory is made, until the profile is formed. The document is written readable by you alone, and never through a symbolic link: a link at the target is refused, and so is an `--out` that names the source file. The default name is `<exposeId>.profile.json` only when the exposeId holds nothing but letters, digits, `_`, `.` and `-`. Otherwise name the file with `--out`.

Each refusal names a stable code, for example `profile_expose_not_found`, `profile_source_unreadable`, `profile_value_refused` or `profile_out_is_a_link`, and nothing is written. A refusal names a column, a row or line number and the kind of value at fault, never the value itself.

## Next: FLUX

A FLUX Simulation turns the profile into synthetic rows. [From your data to a synthetic copy](https://agenticstiger.github.io/flux/guide/from-your-data.html) follows the whole path: a contract from a data file, this profile, a Simulation written from the profile's numbers, then rows from the FLUX engine. The engine does not generate rows from a profile yet, so you write the Simulation's declarations from the values the profile published.

The engine checks a run against the profile it pins, from flux-sim-engine 0.6.0. It compares each fidelity property with a statistic the profile carries for it, such as `mean/1` or a histogram. `fluid profile` writes [`mean/1`](#the-mean-1-statistic), so the engine scores a `mean` property over a number column against the profile. With the guide's data and Simulation on flux-sim-engine 0.6.0, the `mean` property lands within its 10% margin, `fluxsim verify` passes and `fluxsim ship --profile` packs the run. A fidelity block whose properties are all such means, each without a `groupBy`, ships the same way when the profile published each of them. Any other property is still refused with `FLX-5037`.

The rest of the FLUX documentation is at [agenticstiger.github.io/flux](https://agenticstiger.github.io/flux/).
