# `fluid profile`

Profile one expose's records where they live, and write a profile document of output-checked aggregates. A FLUX Simulation pins the document by its digest, so the FLUX engine reads aggregates of the real data and never a record of it.

*(since 0.31.0, [forge-cli #909](https://github.com/Agenticstiger/forge-cli/pull/909), [forge-cli #925](https://github.com/Agenticstiger/forge-cli/pull/925), [forge-cli #946](https://github.com/Agenticstiger/forge-cli/pull/946), [forge-cli #949](https://github.com/Agenticstiger/forge-cli/pull/949), [forge-cli #951](https://github.com/Agenticstiger/forge-cli/pull/951))*

FLUX's statistic registry, `flux-stats`, reads every value and forms every statistic. The fidelity check uses the same registry, so a profile and a check of the same records hold the same numbers.

The `[profile]` extra installs DuckDB and `flux-stats` from PyPI: `flux-stats>=0.6.2,<0.7` through 0.34.0 and, *(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))*, `flux-stats[yaml]>=0.7.0,<0.8` through 0.37.0 and, *(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))*, `flux-stats[yaml]>=0.9,<1` through 0.39.0 and, *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))*, `flux-stats[yaml]>=0.11,<1` through 0.42.0 and, *(since 0.43.0)*, `flux-stats[yaml]>=0.13,<1`: from 0.9 flux-stats is versioned by its own formats and API, so a minor release no longer renames what the profiler imports. 0.9.0 is the first release that holds the profile request reader, a boolean read as a category and profile format 1-2-0. 0.11.0 is the first that holds rank correlations, the follows reach of a release under differential privacy and profile format 1-4-0. 0.13.0 is the first that holds profile format 1-5-0 and profile request format 1-3-0: a noisy history, `nullCount/2` and a noisy query rate with its unit. Installing the extra replaces a flux-stats below its lower bound. Without flux-stats, `fluid profile` stops before it reads anything and says what to install:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: fluid profile forms every statistic with flux-stats, the statistic registry FLUX shares with its fidelity check, and flux-stats is not installed. It needs flux-stats[yaml]>=0.13,<1; install it with: pip install 'data-product-forge[profile]'
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
fluid profile CONTRACT --source SOURCE [--expose ID]... [--table NAME] [--out FILE] [--fractional-bits N] [--bundle DIR]
               [--request FILE [--row-floor N] [--strict]] [--timings] [--env ENV]
               [--privacy-unit EXPOSE --rho R --release-record PATH [--release-table EXPOSE] [--unit-key COL[,COL]]
                [--follow PARENT.COL[,COL]=CHILD.COL[,COL]:MAX]... [--max-rows-per-unit N] [--max-rows-per-cell K]
                [--clique-method aim|mst] [--rederive]]
```

| Argument | What it does |
|---|---|
| `CONTRACT` | The FLUID contract (or a stage-1 bundle `.tgz`) that declares the expose. Its `exposeId` keys the profile's table, and each column's type gives the domain it is read in. |
| `--source` | Where the records live. See [Sources](#sources). *(since 0.36.0, [forge-cli #1024](https://github.com/Agenticstiger/forge-cli/pull/1024))* For several exposes, repeat it as `--source <exposeId>=<location>`, one for each. |
| `--expose`, `--expose-id` | The expose to profile. Optional when the contract has one expose. *(since 0.36.0, [forge-cli #1024](https://github.com/Agenticstiger/forge-cli/pull/1024))* Repeat it to profile several exposes into one document. See [Profiling a whole data product](#profiling-a-whole-data-product). |
| `--table` | The table of a database `--source`, as `name` or `schema.name`. Refused for a file. For several exposes, `--table <exposeId>=<table>`. |
| `--out` | Where to write the document. Default: `<exposeId>.profile.json` in the current directory, or `<contract id>.profile.json` when the call profiles several exposes. |
| `--fractional-bits` | The grid [`mean/1`](#the-mean-1-statistic) is formed on, in steps of 2^-N: 0 to 128, default 16. Set it to the fidelity block's `encoding.fractionalBits`. |
| `--bundle` | *(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* A FLUX bundle directory: the profile answers the fidelity block its one Simulation declares for the expose, on the block's grid, and a different `--fractional-bits` is refused. See [Answering a fidelity block](#answering-a-fidelity-block-bundle). |
| `--request` | *(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))* A profile request that `fluxsim init --contract` wrote. See [Answering a profile request](#answering-a-profile-request-request). *(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* A workload, a consumer query, a date pair, a calendar, a relationship's dates or an exposure that the profile does not form is now named under `Not measured` with its reason, where it was dropped without a word before. See [Asks the profile does not form](#asks-the-profile-does-not-form-strict). *(since 0.42.0, [forge-cli #1112](https://github.com/Agenticstiger/forge-cli/pull/1112))* A consumer query the request lists is answered with its rate: see [Consumer queries](#consumer-queries). |
| `--privacy-unit`, `--rho`, `--release-record` | *(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))* Release one table under differential privacy. See [Releasing a table under differential privacy](#releasing-a-table-under-differential-privacy). `--release-table`, `--unit-key`, `--max-rows-per-unit`, `--max-rows-per-cell`, `--clique-method`, `--follow` and `--rederive` refine it. |
| `--row-floor` | *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* The row floor of the rank correlations a `--request` asks for: a public count of 2 or more, written as each statistic's `rowFloor` and used to form its value, as the larger of the number of records and N. Without it a rank correlation is formed over its records alone and states no `rowFloor`. In a private release each noisy rank correlation carries `--row-floor` as its public `rowFloor`, 1000 by default. Without `--request` it is refused with `profile_row_floor_needs_request`, and in a private release that releases no rank correlation it is refused with `profile_release_row_floor_unused`. |
| `--strict` | *(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* Refuse a `--request` before any record is read when the request or the contract alone shows that an ask cannot be formed. See [Asks the profile does not form](#asks-the-profile-does-not-form-strict). |
| `--timings` | *(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* After the report, print how long each table took to read, measure and check, and how long the document took to write. The document is the same bytes without it. Refused with a private release. See [Where the time goes](#where-the-time-goes-timings). |
| `--follow PARENT.COL[,COL]=CHILD.COL[,COL]:MAX` | *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* With `--privacy-unit`, the privacy unit follows its child rows through one declared relationship: at most MAX children of each parent row are kept. Repeat it for each relationship of the tree rooted at `--privacy-unit`. See [Releasing a table under differential privacy](#releasing-a-table-under-differential-privacy). |
| `--clique-method` | *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* `aim` (the default) or `mst`: how a private release chooses its cliques when two or more columns may join them. Both are OpenDP's, from the `[privacy]` extra. |
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

## Profiling a whole data product

*(since 0.36.0, [forge-cli #1024](https://github.com/Agenticstiger/forge-cli/pull/1024))* One call profiles every expose of a contract into one document. Give each expose its records as `--source <exposeId>=<location>`. With no `--expose`, every expose a `--source` names is profiled, in the contract's order:

```bash
fluid profile contract.fluid.yaml \
  --source customers=data/customers.csv \
  --source orders=data/orders.csv
```

```text
Profiled 2 exposes (customers, orders): 8 columns, 30 values published, 38 withheld.
Withheld, by the check (CL_CONF_STATUS code): A (small count) 26, D (secondary suppression) 12.
The document writes C for every withheld group and cell of a histogram or a quantile, whatever withheld it, so its code says nothing of its size.
exposes[customers]: Fidelity statistics: mean/1 of 'customer_id'; quantile/2 of 'customer_id' at level 0.25 over 116 bins; quantile/2 of 'customer_id' at level 0.5 over 116 bins; levelHistogram/1 of 'segment'; marginalHistogram/1 of 'age' over bins 18, 20, 30, 40, 50, 60, 70, 80, 90, on fractionalBits 16 (the fidelity block must declare the same).
exposes[customers]: Withheld whole, so a run that checks them scores them censored: quantile/2 of 'customer_id' at level 0.75 over 116 bins; quantile/2 of 'signup_date' at level 0.25 over 202 bins; quantile/2 of 'signup_date' at level 0.5 over 202 bins; quantile/2 of 'signup_date' at level 0.75 over 202 bins.
exposes[orders]: Fidelity statistics: mean/1 of 'order_id', 'customer_id'; quantile/2 of 'order_id', 'customer_id' at level 0.25 over 116 bins; quantile/2 of 'order_id', 'customer_id' at level 0.5 over 116 bins; marginalHistogram/1 of 'amount' over bins 0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000; levelHistogram/1 of 'status', on fractionalBits 16 (the fidelity block must declare the same).
exposes[orders]: Withheld whole, so a run that checks them scores them censored: quantile/2 of 'order_id', 'customer_id' at level 0.75 over 116 bins.
Wrote /work/gold.shop.orders_v1.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:7fe97b2d1dd22735b13b431a3455481a68c5fc6fb64f42fc6008da2bfbe58934}
```

(Output from 0.38.0 on a two-expose contract with 3,000 customers and 9,000 orders, so your counts and digest differ.) The document's `tables` hold both exposes, `customers` and `orders`. It is written to `<contract id>.profile.json` unless `--out` names it, and is read back whole before the command reports success. A single `--expose` with one bare `--source` works as before.

`--expose` repeats too. Each flag then needs its own `--source <exposeId>=<location>`, so that one expose's records are never read as another's. A database source takes `--table <exposeId>=<table>`:

```bash
fluid profile contract.fluid.yaml \
  --source customers=sqlite:///$PWD/data/shop.db --table customers=customers \
  --source orders=sqlite:///$PWD/data/shop.db --table orders=orders
```

The same records, read from SQLite and from the two CSV files, wrote the same bytes. Each of these is refused before any record is read, and the run reads nothing and exits 1:

| Call | Refusal |
|---|---|
| `--expose customers --expose orders --source data/customers.csv` | `profile_source_unpaired`: `--expose` is given 2 times and no `--source` names its expose |
| `--expose customers --expose orders --source customers=...` | `profile_source_missing`: `exposes[orders]` has no `--source orders=<location>` |
| `--expose customers --source customers=... --source orders=...` | `profile_source_unused`: `--source` names `exposes[orders]`, which no `--expose` names |
| `--expose customers --expose customers ...` | `profile_expose_repeated`: `--expose` names `customers` twice |
| `--source customers=a.csv --source customers=b.csv` | `profile_source_repeated`: `exposes[customers]` is given more than one `--source` |

With a contract of two exposes and neither `--expose` nor a `<exposeId>=` source, the run stops with `profile_expose_required` and lists the exposes. A database source's password is masked in every refusal.

With `--bundle`, each expose answers its own fidelity block, and the blocks must declare one grid.

## What is profiled

For each column whose FLUID type has a profile domain, the document holds the seven OpenLineage column metrics that apply to it, and the table's `rowCount`:

| Domain | FLUID types | Metrics |
|---|---|---|
| `number` | `integer`, `bigint`, `decimal(p,s)`, `numeric`, `number`, `money`, `year`, ... | `count`, `nullCount`, `distinctCount`, `sum`, `min`, `max`, `quantiles` (0.25, 0.5, 0.75) |
| `timestamp` | `timestamp`, `timestamptz`, `datetime`, `date`, ... | the same, without `sum` (values in milliseconds since the epoch) |
| `category` | `string`, `varchar(n)`, `uuid`, `enum`, ... | `count`, `nullCount`, `distinctCount` |
| `category` | *(since 0.38.0)* `boolean`, `bool`, `bit` | The same. The value is read as the category `false` or `true`. |

These columns are left out and named in the output:
- binary floating point (`float`, `double`, `real`), which FLUX keeps out of every exact path;
- nested values (`json`, `array`, `struct`, ...);
- bytes;
- a bare time of day;
- intervals;
- geospatial values;


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

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* [`--bundle`](#answering-a-fidelity-block-bundle) writes the statistic each property of a fidelity block declares, a grouped `mean/1`, the histograms, `support/1` and `quantile/1` among them, and still no `correlation/1`.

## Default statistics without `--bundle`

*(since 0.36.0, [forge-cli #1024](https://github.com/Agenticstiger/forge-cli/pull/1024))* With no `--bundle`, the profile declares a fidelity block from the contract alone, never from the records, and answers it through the same path as a Simulation's block. So the profile carries the statistics `fluxsim init` reads, and flux-stats forms and checks each of them:

| The contract declares | The profile writes |
|---|---|
| an `enum(...)` column | `levelHistogram/1` over every declared level. A level no record holds is listed, its cell withheld as `C`. |
| a number whose `validationRules` give both ends of a range, each inside its type | `marginalHistogram/1` over about ten bins of one width, exact at both ends. |
| any other number of a bounded type, and every date and timestamp | `quantile/2` at 0.25, 0.5 and 0.75, on a ladder fixed by the type. |
| a categorical `semantics.dimensions` entry on an `enum` column | the other `enum` columns' level histograms, grouped by its levels. One column's groupings hold at most 10,000 cells together; a grouping past that is left out and named. |

*(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* A date or timestamp with no declared range gets a month or year histogram in place of those quartiles, and its table gains a calendar. See [Time and structure statistics](#time-and-structure-statistics).

A `range` rule reads as `">= 18 and <= 90"` or `"between 18 and 90"`. A rule in another shape, such as `">= 18, <= 90"`, declares no range, so that number gets `quantile/2` if its type is bounded. A number with neither a two-ended range nor a bounded type, such as a `decimal` without `(p,s)`, gets no such statistic, and the summary says so:

```text
Profiled exposes[notes]: 2 columns, 7 values published, 5 withheld.
Withheld, by the check (CL_CONF_STATUS code): A (small count) 5.
Fidelity statistics: mean/1 of 'weight', on fractionalBits 16 (the fidelity block must declare the same).
Left out of the default statistics: column 'weight': neither its type nor a validationRules range bounds it within 10^38.
Wrote /work/notes.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:bc4000a1f50cd0a95dcccf073e8c53ec6393de73db4aa87b8923bf56c15a547d}
```

A record outside what the contract declares stops the run and writes nothing: a level its type does not list, a value outside its type or its declared range, a strict bound included. The refusal is `profile_record_outside_declared_domain`. It names the column and the row, never the value:

```text
❌ profile_record_outside_declared_domain  [ERR_PROFILE_RECORD_OUTSIDE_DECLARED_DOMAIN]
  detail: column 'age' row 2: value outside the range its validationRules declare
  written: nothing
  next: the records and the contract disagree: fix the records, or the contract's column type, enum levels or validationRules range, then profile
```

Three more rules keep a count table from pinning a small count: a column that a level histogram counts, or that a grouped statistic groups by, withholds its `distinctCount` under `D`; a number with a default histogram withholds its exact `sum`, `min`, `max`, `quantiles` and `distinctCount` under `D` and has no `mean/1`; and a column gets a histogram or quantiles on the same bins, not both. In the run above, `age` has a histogram, withholds its `sum`, `min`, `max`, `quantiles` and `distinctCount` under `D` and has no `mean/1`, and `segment` withholds its `distinctCount` under `D`. `customer_id` has no histogram, so it keeps `mean/1` and gets `quantile/2`.

A profile that holds a `quantile/2` is format `1-1-0`, which flux-stats reads from 0.7. A profile without `--bundle` of a contract with a bounded number, a date or a timestamp is therefore a `1-1-0` document, and its bytes and digest differ from a 0.35.0 profile of the same records. A contract with only categories and an unbounded `decimal`, like the one above, stays `1-0-0`.

*(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* A default profile of a table with a date or timestamp column moves from format `1-1-0` to `1-3-0`, so its digest changes. It gains more than spans and a calendar: date pairs, a relationship's `dates`, `structural`, `exposure`, `periods` and `per` too, wherever the contract declares what they need, so more contracts change digest. See [Time and structure statistics](#time-and-structure-statistics).

A column the contract types `date` reads a `YYYY-MM-DD` text, from a CSV file too, as that day's midnight in UTC. Anything else in that column is refused as before.

## Answering a fidelity block: `--bundle`

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))*

With `--bundle DIR`, the profile answers the fidelity block of a FLUX Simulation, so the engine can score every property the block declares but a correlation, not only an ungrouped mean. `DIR` is a FLUX bundle directory, the kind `fluxsim init` writes. Exactly one document in its `*.flux.yml` or `*.flux.yaml` files, which may hold several `---` documents, must be the Simulation, and `fluid profile` reads that Simulation's block for the expose:

```yaml
extensions:
  com.agentics.flux/1:
    emits:
      payment_recovery_moment:
        fidelity: {encoding: ..., columns: ..., properties: ...}
```

For each property, the document holds the statistic the engine compares it with:

| Property | What the profile writes, per group |
|---|---|
| `mean` | `mean/1`: the number of values, `k`, and their sum on the grid, `Sx` |
| `marginalHistogram` | `marginalHistogram/1`: a count for each of the property's bins |
| `levelHistogram` | `levelHistogram/1`: a count for each level the column declares |
| `support` | `support/1`: the declared levels the records hold |
| `quantile` | `quantile/1`: the value at the property's `level`, in steps of the grid, with the number of records below it and at or below it, both rounded like every count. *(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* A `quantile` that declares `bins` is answered with `quantile/2` instead, see below |
| `correlation` | nothing: see below |

A property with a `groupBy` gets one group for each level of that column the records hold, and one without gets a single group. The grid is the block's `encoding.fractionalBits`, 16 when the block declares none, and a `--fractional-bits` that differs is refused with `profile_fractional_bits_conflict`. Each number column still gets the [ungrouped `mean/1`](#the-mean-1-statistic), written once when the block declares that same mean.

The block is read the way the FLUX engine reads it, and the fidelity grammar in flux-stats parses it, so a profile and a check read the same declarations. Before any record is read, `fluid profile` refuses a block the engine would refuse (`profile_bundle_block_refused`, with the engine's code), and a property over a column the profile does not read, or reads in another domain than the property does (`profile_bundle_column_not_profiled`, `profile_bundle_column_domain`). A record value outside the block's declared range for its column is refused with `profile_bundle_record_refused`, and so is a level outside the declared support where a level histogram or a `groupBy` reads the column; nothing is written, and the refusal names the row, never the value. A `support` lists the levels the records hold, as the engine reads them. A bundle that gives no block is refused before any record is read, with `profile_bundle_not_a_directory`, `profile_bundle_no_simulation`, `profile_bundle_many_simulations`, `profile_bundle_no_block` or `profile_bundle_unreadable`. `profile_bundle_unreadable` also refuses a block that holds more than 100,000 values once its YAML aliases are written out, nests deeper than 64 levels, or holds a number of more than 1,000 digits written out, and a bundle whose YAML merge keys (`<<`) copy more than 100,000 pairs.

*(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* A `quantile` property that declares `bins` is answered with `quantile/2`. The group states the declared bin that holds the order statistic at its level, and the records below that bin and through it, and no witness. A reader checks that the rounded counts still put the order statistic in that bin, and a group whose rounded counts do not is withheld. A profile that holds one names format `1-1-0`, and every other profile keeps `1-0-0` and its bytes. A quantile with bins is published beside a histogram that shares its bins, where a `quantile/1` is withheld.

*(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* `--bundle` reads the bundle's YAML with flux-stats' exact reader and puts its block in the canonical form with flux-stats, where 0.34.0 used a copy of the engine's code. The bounds hold as before and a refusal still names the file, and the line where the reader reports one, never a value. Its words differ in places: a YAML error names the line and column where the reader found it, the most values a document may write out through its aliases is 1,000,000, and the characters it writes out are bounded too. A block whose bins are not strictly increasing grid points is refused before any record is read (`FLX-5004`), as the fidelity check refuses it.

Through 0.34.0, `--bundle` needed flux-stats 0.6.2 or newer, the first release that holds the fidelity grammar, and the `[profile]` extra asked for `>=0.6.2,<0.7`. *(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* Every `fluid profile` run needs `flux-stats[yaml]>=0.7.0,<0.8`, the first release that holds the readers and the check below. With an older flux-stats, `fluid profile` stops before it reads anything, whether or not it has `--bundle`:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: fluid profile forms every statistic with flux-stats, the statistic registry FLUX shares with its fidelity check, and flux-stats 0.6.2 is installed but cannot be imported (ImportError). It needs flux-stats[yaml]>=0.7.0,<0.8; install it with: pip install 'data-product-forge[profile]'
  read: nothing: no record was read
  next: pip install 'data-product-forge[profile]'
```

### The checks on each group

Each group is checked before it is written, by the [output checks](#what-leaves-the-output-checks) the rest of the document passes:

- A group's `k` is a count of records: it is withheld under 10 records and rounded to a multiple of 5.
- Each group of a grouped mean passes the checks an ungrouped [`mean/1`](#the-mean-1-statistic) passes.
- A histogram's cells are counts, each checked and rounded on its own. A group whose every cell is withheld is withheld whole.
- A support names its members, so each member must be held by at least 10 records, or the group is withheld.
- A quantile's value must be held by at least 10 records, and the rounded counts must still show it is the quantile, or the group is withheld. Few values of a continuous column, such as amounts in cents, are held by 10 records, so expect its quantiles to be withheld.
- When one group of a grouped mean or support is withheld, every other group of it is withheld too, under `D` (secondary suppression). The document publishes the column's `count` and `sum`, so subtracting the published groups from them would give the withheld one back. The records a null `groupBy` value leaves out of every group count as one more group here, checked and never written.

*(since 0.33.0, [forge-cli #965](https://github.com/Agenticstiger/forge-cli/pull/965), [forge-cli #967](https://github.com/Agenticstiger/forge-cli/pull/967))* Four more checks apply to a quantile and to a grouped histogram:

- A quantile is withheld unless at least 10 records lie below its value and at least 10 lie above it. The records are counted before rounding. The group states how many records lie below its value, and this check keeps that count from being a small one.
- No record below or above counts as a zero. A group whose value is the smallest or the largest of its records has no record on one side, and `acro-default` withholds a zero, so the group is withheld.
- A quantile is published only as its column's one histogram or quantile. Beside another histogram or quantile of the same column, whatever its bins, level or `groupBy`, every group of the quantile is withheld. A histogram beside it is checked on its own, and a second quantile is withheld the same way, so two quantiles of one column are both withheld. A quantile's ranks count records at its own value, an edge that no declaration in the block fixes. Beside a histogram of the column they could give a withheld cell back, and two quantiles of a column give back the records between their values. To keep a quantile, declare no other histogram or quantile on its column.
- When a group of a `groupBy` holds fewer than 10 records with a value in a column, every group of that column's histograms and quantiles by that `groupBy` is withheld too. A grouped statistic states the size of each group, and the column states its count, so the size of a small group would follow from the sizes of the others. Here too the records a null `groupBy` value leaves out of every group count as one more group, checked and never written. If 1 to 9 of them hold a value in the column, or if they cannot be read as the block reads them, they withhold the groups. Another column's groups are checked on their own sizes.

The `quantiles` metric of a number or timestamp column states values and no ranks. None of these checks applies to it, and it is checked as before.

What the checks leave readable, on purpose: a grouped statistic lists every group the records form, published or withheld. Each key is a level the bundle declares, because a record whose `groupBy` value the block does not declare is refused, so a key says only that its level holds at least one record. A withheld histogram cell or quantile group is not suppressed in turn: the rounded counts still bound it, somewhere inside 0 to 9 records.

*(since 0.33.0, [forge-cli #967](https://github.com/Agenticstiger/forge-cli/pull/967), [forge-cli #978](https://github.com/Agenticstiger/forge-cli/pull/978))* One thing changes in that paragraph: a histogram or quantile group withheld for its size now brings secondary suppression, as the checks above say, and its siblings are withheld too. A withheld histogram cell still does not. The checks also leave two more things readable, or open:

- A published `min` shows that no record lies below it, and a published `max` that none lies above it. That is a range of no records, and no check withholds a `min` or a `max` for it. A quantile group whose value is the smallest or the largest of its records shows the same, and `acro-default` holds zeros disclosive, so the group is withheld for that.
- Through 0.34.0 the checks left one gap: a reader could subtract one histogram's published counts from another's, or from a level histogram's group size, and read a withheld cell, a zero included, to within the rounding.

*(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* `fluid profile` passes every histogram, level histogram and quantile of a column to flux-stats' `check_edge_counts` in one call, and publishes what it lets through. A histogram and a coarser one of one column, or a published cell and the column's count, no longer give a withheld cell back by subtraction, and a cell that does goes with it. A level histogram is checked over its levels as it is over bins, so one small level withholds a neighbour. A histogram that does not sit on the column's one partition of bins is withheld, and so is a group whose rounded counts no longer prove its quantile. The summary counts a cell or group withheld for its size or rounding as `A`, and one withheld so that another cannot be recovered as `D`. The check does not see a column's `support/1`, the group sizes of a statistic grouped by the column, or a declared level that holds no record, which is absent from a grouped statistic.

A `correlation` property is not answered: its moments need the exact number of records, which the checks round. The summary names it, and `fluxsim verify` fails with `FLX-5037`, so a block you check against a profile cannot declare a correlation yet.

### What it prints

The summary names each statistic the profile publishes, and each one it withholds whole or in part, since a run scores a withheld group as censored. A quantile is named with its level and a histogram with its bins, so two of one column stay apart. Here is a payment-recovery bundle of 400 records in four markets, whose block declares a mean of the amount, a mean by market, a histogram of the amount over three bins, a level histogram and a support of the market, and the amount's median:

```bash
fluid profile bundle/payment-recovery.fluid.yml --source data.csv --bundle bundle
```

```text
Profiled exposes[payment_recovery_moment]: 4 columns, 13 values published, 16 withheld.
Withheld, by CL_CONF_STATUS code: A (small count) 13, D (secondary suppression) 3.
Fidelity statistics: mean/1 of 'amount'; marginalHistogram/1 of 'amount' over bins 1, 100, 1000, 10000; levelHistogram/1 of 'market', on the fidelity block's fractionalBits 16.
Withheld whole, so a run that checks them scores them censored: mean/1 of 'amount' by 'market'; quantile/1 of 'amount' at level 0.5; support/1 of 'market'.
Wrote /data/payment_recovery_moment.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:bd2725b5d5da3ec1311579e6b752f26af26b7b343057102e6dbaedd665792a9c}
```

One market, DE, holds 3 of the 400 records. Its group of the mean by market is withheld, and so are the other three markets' groups, under `D`. Its cell of the level histogram is withheld, and the other levels publish. Its member of the support is held by fewer than 10 records, so the support is withheld. The histogram's top bin holds no record, and a zero is withheld, while the two others publish. No amount is held by 10 records, so the median is withheld. When some groups of a statistic publish and others do not, a `Partly withheld` line names it with the number of groups published.

Run with flux-sim-engine 0.6.2 against this profile, `fluxsim verify` passes: the three published statistics score within their margins, the three withheld ones score as censored, and `fluxsim ship --profile` packs the run.

*(since 0.33.0, [forge-cli #965](https://github.com/Agenticstiger/forge-cli/pull/965), [forge-cli #967](https://github.com/Agenticstiger/forge-cli/pull/967))* The summary counts each withheld value by the check that withheld it, because the document no longer names the check for a histogram or a quantile. The line that starts `Withheld, by` now reads `Withheld, by the check (CL_CONF_STATUS code): ...`, where 0.32.0 printed `Withheld, by CL_CONF_STATUS code: ...`, and up to two lines follow it. A bundle of the same shape, with other records, prints:

```text
Withheld, by the check (CL_CONF_STATUS code): A (small count) 11, D (secondary suppression) 3.
Withheld histogram cells, by the check (CL_CONF_STATUS code): A (small count) 2.
The document writes C for every withheld group and cell of a histogram or a quantile, whatever withheld it, so its code says nothing of its size.
```

The `Withheld histogram cells` line counts the histogram cells withheld inside groups that were published: here the empty top bin and the market that holds 3 records. It appears only when there are such cells. The last line appears when any histogram cell, or any group of a histogram or a quantile, is withheld.

## Answering a profile request: `--request`

*(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))* `--request FILE` takes the list of statistics, column metrics and relationships that `fluxsim init --contract` writes for a contract. The profile measures what the request lists and nothing else, under the same output checks: per listed table only the listed columns, metrics and statistics, the row count only when asked, and children per parent only for a listed relationship the contract declares. The request's grid is the profile's. Each listed item the profile cannot answer is named in the report as `Not measured`, with its reason, for example a histogram over a number with no declared range. A listed fact, a rule of the contract's `invariants`, is measured as the rows the rule covers that do not and do satisfy it, and the profile is then format 1-2-0.

*(since 0.43.0)* `fluid profile` reads profile request format 1-3-0. Beside the asks above, a request of that format may ask a table's `history: {}`, with `columns` optionally naming the candidate tracked columns, and a column's `nullCount/2`. A [private release](#releasing-a-table-under-differential-privacy) answers both with noise. An exact profile forms the history of exactly the tables whose request asks for it, from the contract's natural entity and validity window, and names a table with no window, or whose history does not form, under `Not measured` with the reason; a request that asks for no history still writes none. `nullCount/2` has a noisy form only, so an exact profile names the ask under `Not measured` with that reason, and [`--strict`](#asks-the-profile-does-not-form-strict) refuses it. A rule over an aggregate, a dependency or a related row is reported as not measured.

### The facts of a table are checked together

*(since 0.39.0, [forge-cli #1066](https://github.com/Agenticstiger/forge-cli/pull/1066))* Each fact's own two cells (the rows that satisfy the rule and the rows that do not) pass the output checks, but facts that overlap give more together than each alone. `A` beside `A OR id = 'x'` differ by the one row `x` when it lies outside `A`, and `A`, `B` and `A OR B` give `|A AND B| = |A| + |B| - |A OR B|` however large each pair's difference is. Rounding does not hide it: counts of 102 and 103 are published as 100 and 105. So the profiler counts every combination of a table's facts' states (not covered by the rule, fails it, holds it) in one pass over the records, on the exact counts before any rounding, and holds every combination to the threshold.

- **A fact that touches a small combination is withheld.** A fact is withheld when it touches a combination of 1 to 9 records (the threshold, 10, less 1), and the combinations of the facts still published are formed again, until none is left. Small cells are settled first, so a fact is not withheld for the empty combinations around a cell that other facts set apart.
- **Where zeros are disclosive** (they are, by default) an empty combination that the rules' texts allow also withholds the facts it differs in, however many single changes it lies from a combination the records hold. What a withheld fact is does not depend on the order of the facts.
- **A fact that leaves too few rows uncovered is withheld too.** The table's `rowCount` less a fact's `k` gives the number of rows its `when` does not cover, so a `when` that leaves fewer than 10 rows uncovered, or none where zeros are disclosive, withholds its fact. A withheld fact with a `when` writes `sampleSize: {"min": 0}`, because the band of the rows it covers would give their number back to a reader who differences it against another fact's `when`.
- **The texts are read as AND, OR and NOT.** `A` TRUE beside `A OR id = 'x'` not TRUE is known to be no row's, so a containment the rules' texts show is not taken for one the records show. What the parts mean (`x > 2` beside `x > 1`) is not read, which errs toward withholding. Rules that share too many parts to be read in 2^17 readings are taken to rule nothing out, which also only withholds more.

A withheld fact is written `C` in the document, as every withheld group of a level histogram is, and the summary counts it as `D` (secondary suppression):

```text
Profiled exposes[orders]: 1 column, 3 values published, 2 withheld.
Withheld, by the check (CL_CONF_STATUS code): D (secondary suppression) 2.
Fact orders.big: withheld by the check (D, secondary suppression).
Fact orders.big_or_x: withheld by the check (D, secondary suppression).
Fact orders.open_status: its share is published, as rounded counts.
```

This is the output of a profile of 301 records, one of which, `x`, lies outside the rule `amount >= 10`, for the facts `amount >= 10`, `amount >= 10 OR id = 'x'` and `status = 'open'`. The two overlapping facts differ by that one record, so both are withheld, and the third is published. 0.38.0 published all three, and a reader could take the one record from the first two.

What this does not cover: a fact's overlap with a histogram's cells, a column's counts or a relationship's counts, and facts of two exposes that the data owner reads from the same records, which it takes for two tables. A threshold makes differencing harder and cannot rule it out. Noise does, and [a release under differential privacy](#releasing-a-table-under-differential-privacy) is the way to publish counts with noise. A profile that lists facts may therefore differ from one that 0.38.0 wrote, and its digest with it: see [Changes in 0.39.0](../upgrading.md#changes-in-0-39-0).

A request is refused before any record is read, each with its own event code, when it is used beside `--bundle`, `--env` or `--expose`, when the contract is a stage-1 bundle archive, when the request file is not a regular file, is too large, is not UTF-8 or is refused by flux-stats, when its contract digest is not the contract file's (run `fluxsim init` again), when a table, column or domain is not shared by the contract and the profile, when `--fractional-bits` differs from the request's, and when a listed table has no `--source` or a `--source` names a table the request does not list.

### Consumer queries

*(since 0.42.0, [forge-cli #1112](https://github.com/Agenticstiger/forge-cli/pull/1112))* A request of format 1-1-0 can list consumer queries (PROFILE-REQUEST-SPEC 1-1-0, section 6). Through 0.41.0 the profile named each under `Not measured` and answered none. Now it answers a query with its rate, in a `queries` section of the document: how many of its unit's records the query keeps.

A query lists a `name`, its `sql`, a `unit` and, optionally, a `groupBy`. This request, written by hand, asks the share of a library's membership cards held at the `family` tier:

```yaml
"queries":
  - "name": "family_cards"
    "sql": "SELECT member_id FROM cards WHERE tier = 'family'"
    "unit":
      "table": "cards"
```

```bash
fluid profile contract.yaml --source cards=cards.ndjson --request request.yml --out library.profile.json
```

```text
Queries: 1 of 1 published whole.
```

The document answers it with one `levelHistogram/1` over `false` and `true`. `k` is the unit's records and the `true` count is the rows the query returns, each published as a count rounded to a multiple of 5 like any other:

```json
{"name": "family_cards", "statistics": [{"definition": "levelHistogram/1", "levels": ["false", "true"],
  "groups": [{"group": "", "k": 910, "levelCounts": [595, 310], "status": "F"}], ...}]}
```

The table held 908 records, 311 of them at the `family` tier. With a `groupBy`, the histogram has one group for each level of that column, and a profile that holds a grouped query is format 1-3-0:

```json
"groups": [{"group": "basic", "k": 320, "levelCounts": [230, 90], "status": "F"},
           {"group": "family", "k": 310, "levelCounts": [215, 95], "status": "F"},
           {"group": "plus", "k": 280, "levelCounts": [195, 85], "status": "F"}]
```

That is the query `SELECT member_id, tier FROM cards WHERE valid_to IS NULL` with `"groupBy": "tier"`: the cards still open, by tier.

**What a query may be.** A query is answered when it keeps some of its unit's records and changes none:

- It is one outer `SELECT` of columns, from exactly its unit, with at most one `WHERE`. A join, `DISTINCT`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, a window, an aggregate, a set operation or a subquery in the `WHERE` is not answered.
- Its `unit` is a table of the request, or a view that itself only keeps some of one table's rows (`SELECT ... FROM table [WHERE ...]`). A query over a view carries the view as its one `WITH` entry. This one counts the open cards that are at the `plus` tier, out of the open cards (`k` is 265, and the `true` count 85):

```yaml
  - "name": "open_plus_cards"
    "sql": "WITH \"v\" AS (SELECT * FROM cards WHERE valid_to IS NULL) SELECT \"v\".\"member_id\" AS \"member_id\" FROM \"v\" AS \"v\" WHERE \"v\".\"tier\" = 'plus'"
    "unit":
      "sql": "SELECT * FROM cards WHERE valid_to IS NULL"
```

- Its `groupBy` names a column of the unit's records that the query also returns under the same name, and whose type declares its levels (an `enum(...)` or a boolean). The groups are those levels, whatever the records hold.
- A condition must not be able to fail on a row's value. A cast, arithmetic, a `CASE` or a function off the allowed list is refused. Compare columns with constants of their own type, joined by `AND`, `OR` and `NOT`.
- A unit may aggregate only when it counts entities: one table's rows grouped by the child column of a declared `many_to_one` relationship, as in `SELECT branch_id, count(*) AS n FROM cards GROUP BY branch_id`. Its records are then the relationship's parents, and a query over it is checked together with the relationship's children-per-parent bins. Any other aggregate unit is not answered.
- A request holds at most 1,024 queries, and at most 64 are answered over one unit.

What is not answered is named under `Not measured`, with its reason, and the rest of the profile is written. These lines are from requests run on `main`. The first query groups its rows, the second joins a table the request does not list, the third casts a column, the fourth groups by a column with no declared levels, the fifth is the 65th over its unit, and the last one's unit aggregates by a column that keys no relationship:

```text
Not measured: query per_member: fluid profile answers a query that keeps some of its unit's records: it groups its rows.
Not measured: query joined: the check refuses the query: the query names the table 'branches', which is not one of the tables the request lists (['cards']) and not a WITH entry.
Not measured: query cast_cond: a condition of its query or its unit's view could raise an error that depends on a row's value, so fluid profile does not run it: compare columns with constants of their own type, joined by AND, OR and NOT.
Not measured: query by_branch: its groupBy branch_id is a column whose type declares no levels.
Not measured: query q64: past the 64 queries over one unit that fluid profile answers.
Not measured: query busy_branches: a unit that aggregates is answered only when it groups one table's rows by an entity they belong to.
```

The report counts the queries: `Queries: N of M published whole.`, with `, K in part.` when a grouped query publishes some of its groups.

**The queries of a unit are checked together.** A query's two cells pass the output checks as a fact's do. Queries over one unit, and the facts of the same table, are then checked as one set, since two queries that differ by one record give that record back by differencing. Each published cell of the table's columns is held in the set too: an ungrouped level histogram, an ungrouped histogram of a number or timestamp column, or the rows with a value where a column's `count` or `nullCount` is published. A query that would give back a small cell is withheld with `D`. Two queries that differ only by the cards of one member, `valid_to IS NULL` and `valid_to IS NULL OR member_id = 7`, are both withheld:

```text
Queries: 0 of 2 published whole.
Query open_cards: withheld by the check (D, secondary suppression).
Query open_or_member_7: withheld by the check (D, secondary suppression).
```

A table's records are counted one way in a run: as its rows, as its entities by one column, or as the parents of one relationship's children. A query whose unit counts a table another way than a fact or an earlier query does is named, and not answered.

**Before any record is read.** Whether a query is answered, with the shape, `groupBy`, condition and bound rules above, is decided before any record is read. [`--strict`](#asks-the-profile-does-not-form-strict) refuses a request with such a query. What only the records decide (a withheld cell, a statement that failed) is named and never refused. If a statement fails because of the records (an error, a time-out, running out of memory, a value that does not load), every query of the run is withheld with one message, so the run says at most that some statement failed.

**How a query runs.** The query's text is untrusted. It is parsed and checked against closed lists of expression classes and functions, and bounds. It is then built again from the checked tree, and that text is checked a second time. Only the rebuilt text runs, in a DuckDB process of its own: a bare environment with no inherited descriptors, file-size, CPU and memory limits, an in-memory database that cannot reach files, load extensions or change its settings, one `SELECT` per statement, and only counts and bits come back. A request from a source you do not trust still belongs in a container.

**A private release answers a query with noise.** *(since 0.43.0)* Through 0.42.0 a private release named each query under `Not released`. Now a query that passes the checks above gets a `queries` entry whose rate is two noisy cells (`false`, then `true`) for each group, and which states its `unit`. See [Queries answered with noise](#queries-answered-with-noise).

### Asks the profile does not form: `--strict`

*(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* The request is read whole. An ask that `fluid profile` does not form is named in the report under `Not measured` (under `Not released` with `--privacy-unit`), with its reason, and the rest of the profile is written. A listed query is named, never printed: its text is not kept.

`--strict` turns that into a refusal before any record is read. It refuses a request when the request or the contract alone shows that an ask cannot be formed:

- a workload;
- a consumer query that `fluid profile` does not answer. *(since 0.42.0, [forge-cli #1112](https://github.com/Agenticstiger/forge-cli/pull/1112))* A query is answered where it can be: see [Consumer queries](#consumer-queries). Through 0.41.0 every consumer query was refused;
- a metric, statistic, rank correlation, grouping, date pair, calendar, relationship date or exposure over a column the profile does not read, over a key of a counted relationship, or over a column whose type rules it out;
- a fact whose rule `fluid profile` cannot measure;
- more entries than a profile holds;
- any ask of a relationship the contract does not declare or the profile does not read.

With `--privacy-unit`, `--strict` refuses instead the kinds a private release does not form: a workload, date pairs, a calendar, relationship dates and exposure. *(since 0.43.0)* A consumer query is no longer one of them.

An ask that only the records leave unanswered, such as a small cell, a column with no published date span or a value that is not a whole day, is named under `Not measured` and never refused. Without `--request`, `--strict` is refused.

The command exits 1, names each ask and its reason, and writes nothing. This request asks for the children per parent of `waterings(watering_id)` to `beds(bed_id)`, a relationship the contract does not declare:

```text
CLI command error
❌ profile_request_not_formed  [ERR_PROFILE_REQUEST_NOT_FORMED]
  detail: --strict: the request asks for 1 item fluid profile does not form
  the contract declares no such relationship: children per parent of waterings(watering_id) to beds(bed_id)
  read: nothing: no record was read
  next: leave --strict out to profile what fluid profile forms, with each of these named under Not measured, or write the request without them
```

Without `--strict`, the same request is profiled, and the report says:

```text
Not measured: children per parent of waterings(watering_id) to beds(bed_id): the contract declares no such relationship.
```

With `--privacy-unit`, a request for date pairs and a calendar is refused the same way:

```text
CLI command error
❌ profile_request_not_formed  [ERR_PROFILE_REQUEST_NOT_FORMED]
  detail: --strict: the request asks for 3 items fluid profile does not form
  a private release forms no date pair: date pair planted to sprouted of beds; date pair planted to harvested of beds
  a private release forms no calendar: calendar of beds.planted
  read: nothing: no record was read
  next: leave --strict out to profile what fluid profile forms, with each of these named under Not measured, or write the request without them
```

`--strict` with no `--request` is refused:

```text
CLI command error
❌ profile_strict_needs_request  [ERR_PROFILE_STRICT_NEEDS_REQUEST]
  detail: --strict refuses a request that asks for what fluid profile does not form, and --request names none
  read: nothing: no record was read
  next: give --request, or leave --strict out
```

## Releasing a table under differential privacy

*(since 0.38.0, [forge-cli #1040](https://github.com/Agenticstiger/forge-cli/pull/1040))* With `--privacy-unit`, `--request`, `--rho` and `--release-record`, the profile is a release of one table's requested statistics under zero-concentrated differential privacy, a profile of format 1-2-0, or 1-4-0 once it holds a rank correlation or a follow, or, *(since 0.43.0)*, 1-5-0 once it holds a null count, a noisy history or a noisy query. It holds a noisy level histogram of each required `enum` column the request lists, a noisy histogram of each required number, date or timestamp column on public bins, and noisy clique marginals chosen with OpenDP's AIM or, with `--clique-method mst`, its MST. *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* A request can also ask for noisy rank correlations, and a clique can hold a number or timestamp column. The selection needs the `[privacy]` extra, `pip install 'data-product-forge[profile,privacy]'`, and only when a selection runs.

```bash
fluid profile contract.fluid.yaml --request orders.request.json \
  --source orders=./orders.csv --privacy-unit orders --unit-key customer_id \
  --max-rows-per-unit 3 --rho 1 --release-record orders.release-record.json
```

- **The privacy unit is an entity.** *(since 0.39.0, [forge-cli #1066](https://github.com/Agenticstiger/forge-cli/pull/1066))* `fluid profile --help` says so too. One row of `--privacy-unit`, or with `--release-table` a child table through one declared relationship, or with `--unit-key COL[,COL]` the rows of one table that share a key. Each entity contributes at most `--max-rows-per-unit` rows and counts at most `--max-rows-per-cell` in one cell, so the stated loss holds for each entity and for each row of it.
- **A `--rho` above 1 warns.** *(since 0.39.0, [forge-cli #1066](https://github.com/Agenticstiger/forge-cli/pull/1066))* `--rho` still takes any number above zero, and the release goes ahead, but once it is planned (from `--rho`, or from the record under `--rederive`) a `rho` above 1 prints one warning:

  ```text
  ⚠️  rho 1.5 is above 1, a large privacy loss. OpenDP's rule of thumb keeps epsilon at most 1, which is rho 0.5 (an epsilon-DP release is (epsilon^2/2)-zCDP); the US Census Bureau's 2020 Census
  products used rho from about 2.6 to 7.7. The release goes ahead.
  ```

  A `rho` of 1 or below prints nothing.
- **A rank correlation carries a row floor.** *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* Each noisy rank correlation carries `--row-floor` as its public `rowFloor`, 1000 by default. Its sensitivity for one row is 4 / (floor + 1) for Kendall's tau and 9 / (floor + 1) for Spearman's rho, times the rows one unit contributes, counted as at least two in a keyed or related release.
- **The cliques are chosen with AIM or MST.** *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* `--clique-method mst` chooses them with OpenDP's MST instead of its AIM. The profile records the method, the OpenDP version and the tenth of `rho` the choice cost in `cliqueSelection`. A clique that holds a number or timestamp column is released as `cliqueMarginal/2` on the public bins of the column's declared range, and the bins are never chosen from the data.
- **The unit can follow its child rows.** *(since 0.40.0, [forge-cli #1074](https://github.com/Agenticstiger/forge-cli/pull/1074))* `--follow PARENT.COL[,COL]=CHILD.COL[,COL]:MAX` makes the unit a row of the privacy unit's expose with at most MAX of its children through that relationship. Repeat it for a tree. The profile names the follows in `privacy.privacyUnit.follows` (format 1-4-0), and the tree is checked before any record is read. `--follow` is not combined with `--release-table`, `--unit-key` or `--max-rows-per-unit`. This unit is an account with up to 3 invoices, each with up to 2 lines:

  ```bash
  fluid profile billing.fluid.yaml --request billing.profile-request.yml \
    --source account=./account.csv --source invoice=./invoice.csv --source line=./line.csv \
    --privacy-unit account --follow account.id=invoice.account_id:3 \
    --follow invoice.invoice_id=line.invoice_id:2 --rho 1 --release-record billing.record.json
  ```

- **A request can ask a table's noisy null counts.** *(since 0.43.0)* For each column whose `nullCount/2` the request lists, and that is not a key, the release writes one `nullCount/2` of two noisy cells, the known records and then the NULL ones. It is a count table of its own, charged like any count table of its table (`m_T`, so the cap of a followed table counts), and it joins no clique. A release whose request asks for none is byte for byte what it was.
- **A request can ask a followed table's noisy history.** *(since 0.43.0)* When the request asks a table's `history: {}` and the unit follows into that table (the unit's own expose has none), the release writes the table's `versionsPerEntity`, `firstStart`, `versionLength`, `chain`, `lastVersion`, each tracked column's `initial` and `transitions`, and `reasons`, on the same public ladders an exact history uses. Each member is a count table over the followed table, charged `m_T`, with an equal share of the budget of its own, and every cell is published: nothing is withheld. Under one parent row the cap is spent on whole entities. An entity is kept with all of its versions or dropped with all of them, by a priority that reads only that parent's rows, and an entity with more versions than the cap is not described. A release whose records put one entity's versions under two parent rows is refused (`profile_release_entity_units`) before anything is written. The unit's own expose, a table the unit does not reach and a table with no validity window are named under `Not released` with the reason.
- **A request's consumer queries are answered with noise.** *(since 0.43.0)* See [Queries answered with noise](#queries-answered-with-noise).
- **The budget.** A tenth of `rho` chooses the cliques, and the rest is split equally over the count tables. The report names the unit, the loss and its split, each table's noise scale, the cliques, an informational conversion to (epsilon, delta), and every requested item that is not released, with the reason.
- **The release record.** The noise is drawn from a seeded randomness source that is recorded in `--release-record`, created readable by its owner alone, and the file must not exist for a new release. Keep it inside the data owner's boundary: with the record and the profile, the noise can be taken off. `--rederive` with the existing record draws the release again and writes the profile only when its digest is the recorded one.
- **Nothing that depends on the records** is printed, logged or recorded outside the noise. A refusal names a column and a row, never a value or a count.

### Queries answered with noise

*(since 0.43.0)* A consumer query that passes the same checks as for an exact profile gets a `queries` entry in a private release. Its rate is two noisy cells for each group, the records of its unit the query does not return (`false`) and those it does (`true`). It is a count table of its own, with a share of the budget of its own, and it states its `unit`:

- `{table: T}`: the query counts the records of `T`, or of a view that keeps some rows of `T`. It is charged `m_T`, so `T` must be a table the unit reaches.
- `{table: T, by: [columns]}`: the query counts groups of `T`'s rows. The columns are the child columns of a relationship the unit follows, and the charge is `m_P` of the parent, or they are the natural entity of `T` where the release holds `T`'s history, and the charge is `m_T`.

A query that cannot be charged is named under `Not released` with its reason, and never a count. A statement that fails because of the records withholds every query of the release, each named with the reason. The disclosure checks of an exact profile do not apply to a noisy release, since noise stands in for them, and an exact profile writes no `unit`. The release record re-derives the same bytes.

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

*(since 0.33.0, [forge-cli #965](https://github.com/Agenticstiger/forge-cli/pull/965), [forge-cli #967](https://github.com/Agenticstiger/forge-cli/pull/967))* A withheld group or cell of a histogram, and a withheld group of a `quantile/1`, is written `C`, whatever withheld it. A code that names the check tells a reader a range: `A` says that a cell holds fewer than 10 records. In the worst case a reader knows the group's total and the exact size of each published cell, and then cells of 10, 9, 9 and 10 records written `F`, `A`, `A` and `F` give both withheld cells as 9. A histogram group with a withheld cell, whose count is `null`, and a withheld quantile group read like this in the document, shown here with spaces added and each object taken from its own `groups` list:

```text
{"binCounts": [40, 360, null], "cellStatus": ["F", "F", "C"], "group": "", "k": 400, "status": "F"}
{"group": "", "status": "C"}
```

So `C` has two meanings in a document, a sum over at most two values and any withheld value of a histogram or a `quantile/1`, and the statistic it sits in tells them apart. The summary still counts each withheld value by the check that withheld it, which the document does not say. Every other statistic, and every column metric (`min`, `max` and `quantiles` among them), keeps the code of its check.

A profile that 0.32.0 wrote still reads, because flux-stats' reader accepts every `CL_CONF_STATUS` code.

Two consequences to expect:
- A column with 1 or 2 distinct values withholds its `distinctCount`: it rounds to 0, and a published 0 would read as a zero cell.
- If any one quantile level's value is held by fewer than 10 records, the whole `quantiles` metric is withheld.

::: warning No privacy guarantee
These are output-checking conventions only. No privacy or anonymity guarantee is made or implied. ACRO's tools assist human output checkers and do not replace them: read the document before you share it.
:::

### Rounded date extremes

*(since 0.42.0, [forge-cli #1112](https://github.com/Agenticstiger/forge-cli/pull/1112))* The order-statistics rule publishes a `min` or `max` only when at least 10 records hold that exact value. One record often holds a date or timestamp column's earliest or latest value, so through 0.41.0 such an end was withheld. Now an end that fewer than 10 records hold is rounded to a calendar unit and published.

- The units are the UTC calendar day, the month and the year, finest first. A column the contract types `date` has no day unit, since its exact value already is a day.
- The first unit whose bucket holds at least 10 records gives the end. For a `min` the bucket is the one that holds the column's smallest value, and for a `max` the one that holds its largest.
- A `min` is published as the first value of the bucket. A `max` is published as the last value of it: its last day for a `date` column, its last millisecond for a timestamp column. The value has status `F`, as any published value has. The document carries no mark that an end was rounded, and the report names it.
- When no bucket up to the year holds 10 records, the end stays withheld.
- A `range` rule on the column clips a rounded end, so a `max` is never published past the declared end, nor a `min` before the declared start. When a record lies outside the declared range, the end stays withheld and is not clipped. A range rule the profiler does not read leaves the column's ends unrounded.
- A `min` or `max` that is withheld for what a histogram of the same column withholds (`D`) is not rounded.

A published end says that its bucket holds at least 10 records and that no record lies beyond it. It does not say that a record holds that value: a `min` of 2019-01-01 can sit beside an earliest record of 2019-01-02.

The examples use a `visits` table with a timestamp column `visited_at` and a `date` column `visit_day` that hold the same days. Each row of the table below adds 12 visits a day for 60 consecutive days from 2024-06-01 to the records it names. Each row was profiled on forge-cli `main`:

| The records at the end | `visited_at` (timestamp) | `visit_day` (date) | Report |
|---|---|---|---|
| Earliest: 3 visits at 09:00 on 2024-03-02 and 9 more at 15:00 the same day | `min` 2024-03-02T00:00:00.000Z | `min` 2024-03-02, exact: 12 records hold it | `visited_at min to day` |
| Latest: 3 visits on 2024-12-30, and 11 more on 2024-12-05 | `max` 2024-12-31T23:59:59.999Z | `max` 2024-12-31 | `visited_at max to month; visit_day max to month` |
| Latest: 3 visits on 2024-12-30, and 11 more on 2024-10-05 | `max` 2024-12-31T23:59:59.999Z | `max` 2024-12-31 | `visited_at max to year; visit_day max to year` |
| Latest: 3 visits on 2024-12-10 and 11 more on 2024-12-05, and the contract declares a range ending `2024-12-20` | `max` 2024-12-20T00:00:00.000Z | `max` 2024-12-20 | `visited_at max to month; visit_day max to month` |
| The contract declares a range ending `2024-12-15`, and 3 visits lie on 2024-12-30 with 11 more on 2024-12-05 | `max` withheld, status `A` | `max` withheld, status `A` | none |

A range is declared on the column as a rule, for example `validationRules: [{type: range, constraint: "<= '2024-12-20'"}]` on the `date` column. A timestamp column's constraint names an instant, such as `"<= '2024-12-20T00:00:00Z'"`.

The report names each rounded end and its unit, per table, in the summary of a default profile, of a [`--request`](#answering-a-profile-request-request) and of a [`--bundle`](#answering-a-fidelity-block-bundle) table:

```text
exposes[cards]: Rounded extremes: valid_from min to year; valid_to min to year.
```

In the library profile of [Reference tables published whole](#reference-tables-published-whole), the earliest `valid_from` is 2019-01-02 and only 7 records start in January 2019, so no month holds 10 and the `min` is the first day of the year, which 166 records start in. In the document that is `"status": "F"` and `"value": "1546300800000"`, the milliseconds since the epoch of 2019-01-01T00:00:00Z. The `max` of the same column stays withheld (`"status": "A"`), since the year of its largest value holds 1 record. Through 0.41.0 both ends were withheld.

## Children per parent

*(since 0.37.0)* When one call profiles both exposes of a `semantics.relationships` entry, without `--bundle`, the document's `relationships[]` entry holds how many child rows each parent has. Each parent row counts once, in one of these bins: 0, 1, 2, 3 to 4, 5 to 9, 10 to 19, and 20 or more. Keys are matched as the registry reads them, and a null key matches none.

To keep a count from showing more than it should, the child's foreign-key columns withhold their `distinctCount`, `sum`, `min`, `max` and `quantiles`, and form no `mean/1`. Next to the parents' row count, the number of parents that have a child would give the number that have none, and the key's own values would describe each parent's children one key at a time. The key columns of a counted relationship also take no default statistic of their own.

A relationship is named in the summary and left out when:

- its target is not profiled in the call;
- it declares a validity window;
- its keys are read in different domains.

The histogram goes through its own output check. Treat it as one more table about the same parents: other tables over them (an `enum` column's level histogram, another relationship's cells) bound the numbers, and so do the children's own counts.

## Time and structure statistics

*(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* The profile publishes the date and structure members of FLUX's profile format 1-3-0, which `fluxsim init` reads to place dates and shape relationships: date spans, date pairs, a relationship's dates, structural classes and exposure, a table's calendar and periods, and statistics counted per entity. They go through the same output checks as every other value, and a private release forms none of them and names each one it was asked for.

The examples on this page use a small synthetic garden. The `beds` expose has the columns `bed_id`, `planted`, `sprouted` and `harvested`, the last three typed `date`. Its contract says a bed does not sprout or get harvested before it is planted, and a bed is harvested only after it sprouted. The `waterings` expose has a `bed_id` that its relationship `bed` ties to `beds`.

```bash
fluid profile contract.json --source beds=./beds.ndjson --source waterings=./waterings.ndjson --out garden.profile.json
```

```text
Profiled 2 exposes (beds, waterings): 6 columns, 35 values published, 38 withheld.
Withheld, by the check (CL_CONF_STATUS code): A (small count) 23, D (secondary 
suppression) 15.
Withheld histogram cells, by the check (CL_CONF_STATUS code): A (small count) 2,
D (secondary suppression) 2.
The document writes C for every withheld group and cell of a histogram or a quantile, whatever withheld it, so its code says nothing of its size.
exposes[beds]: Fidelity statistics: mean/1 of 'bed_id'; marginalHistogram/1 of 'planted' over bins 1672531200000, 1704067200000; marginalHistogram/1 of 'sprouted' over 12 bins; marginalHistogram/1 of 'harvested' over bins 1672531200000, 1704067200000, 1735689600000, on fractionalBits 16 (the fidelity block must declare the same).
exposes[beds]: Left out of the default statistics: column 'bed_id': a key of a counted relationship, which its children per parent describe.
exposes[waterings]: Fidelity statistics: mean/1 of 'watering_id'; quantile/2 of 'watering_id' at level 0.25 over 116 bins; quantile/2 of 'watering_id' at level 0.5 over 116 bins, on fractionalBits 16 (the fidelity block must declare the same).
exposes[waterings]: Withheld whole, so a run that checks them scores them censored: quantile/2 of 'watering_id' at level 0.75 over 116 bins.
exposes[waterings]: Left out of the default statistics: column 'bed_id': a key of a counted relationship, which its children per parent describe.
Children per parent of exposes[beds] in exposes[waterings] (bed): withheld whole.
exposes[beds]: Date pairs: 2 of 3 published.
Exposure of exposes[beds] in exposes[waterings]: 1 of 6 published.
exposes[beds]: Calendar: 4 of 6 histograms published.
Not measured: days of date pair planted to harvested of beds: its first or last day bin holds fewer than the least cell, so its days have no outer edge to publish.
Wrote /work/garden.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:3c1886305cc3a0b15f8fb170e8c58a27be81ffebb8bc54c2fab60ce45e38560d}
```

The document names format 1-3-0. A profile of a table with a date or timestamp column moves from format 1-1-0 to 1-3-0 even with no date pair or relationship in it, so its digest changes. `fluxsim` 0.10.0 is the first release that reads format 1-3-0, and 0.9 and older refuse it. Profile again after upgrading, and pin the new digest wherever the old one was pinned.

### Date spans

A date or timestamp column with no declared range gets a `marginalHistogram/1` over calendar months. When its first or last month holds fewer than the minimum cell, or the span is longer than 240 months, it is over calendar years instead. It runs from the start of the first month (or year) that holds a record to the start of the month (or year) after the last, so its outer edges cover every record, and `fluxsim init` can take a run window from them. The histogram takes the place of the column's quartiles, so a column has a histogram or quartiles, never both on one set of bins. A request that lists both gets the histogram, and the quartiles are named under `Not measured`.

The grain is published only when its first and last bin each hold at least the output check's minimum cell (10 under ACRO) and the span is at most 240 bins. Otherwise the column keeps the quartiles on the type's ladder, and the report says why. This is the line for a `tasks` expose whose `due` column holds one date years after the rest:

```text
tasks.due: no date span: its first or last month and year hold fewer than 10 records; its quartiles stay on the type's ladder.
```

A column with both ends of a range declared, a column a request groups by or is grouped by, and a key of a counted relationship are unchanged.

### Date pairs and a relationship's dates

Each pair of date columns of a table gets a histogram of the whole days from the earlier to the later, on one fixed ladder of bins trimmed to the bins from the first one that holds a record to the last, and the order of the two: after, before or same. A request lists the pairs it wants, and a table holds at most 1024 of them. The days and the order are checked together in one pass on the same outer edges.

- The days are published only when each of the two end bins holds at least the minimum cell, so no single record places an outer edge. With no day histogram the order is checked alone.
- A cell that a contract rule empties is published as a zero only when the records leave it empty. In the garden, the rule `sprouted IS NULL OR sprouted >= planted` empties "before" for the pair `planted` to `sprouted`, and the published order reads after 270, before 0, same 30. The rule never makes a zero out of data, and a rule the records break changes nothing.
- A pair with a timestamp column, or a value that is not a whole day, is named under `Not measured` with its reason (`--strict` refuses a pair whose column type rules it out). The `planted` to `harvested` pair above is named because its end day bins are too small, as the first bullet says.
- A pair that no record holds both dates of is written like a small one, with its order withheld whole, so the list of pairs says nothing about it.

Each declared relationship gets the same for every pair of a parent's and a child's date columns, under `dates`, at most 1024 of them.

### Structural classes and exposure

A relationship states `structural: ["childless"]` only when its children per parent are counted, the disclosure rule treats zeros as disclosive, the contract derives the parent's count of its children and checks that it is at least 1, and no parent lacks a child.

An `exposure` holds the child rows whose parent's start is known, and the days those parents are active inside a window. The window comes from the start column's published date span or the range the contract declares for it. A relationship holds at most 1024 exposures.

A parent table publishes the exposure of one lifetime, the same under every relationship into it: among the lifetimes formed, the first with an end, else the first date column alone, in the schema's order. The lifetime is chosen from the contract, the request and the published document, never from the records. Every other lifetime's exposure is written withheld whole, with the code `D`, because sums over the same parents can be added and subtracted to give one parent's date back. In the garden profile the six exposures are the three date columns alone and the three pairs, and only `planted` to `sprouted` carries its numbers:

```text
Exposure of exposes[beds] in exposes[waterings]: 1 of 6 published.
```

The output checks hold within one run. The tier does not protect across runs, so separate runs that request different lifetimes can be combined.

### Calendar, periods and statistics per entity

Each date and timestamp column gets `month`, `dayOfWeek` and, on a timestamp only, `hourOfWeek`, each a `levelHistogram/1` read in UTC. A request lists the columns it wants, and a table's calendar holds at most 1024 columns. `dayOfWeek` is numbered as ISO 8601 numbers it, Monday 1 to Sunday 7. The hours and the days of the week are checked in one call, since a day is 24 hours.

A calendar histogram is published only when no statistic on the column withholds a group or a cell, and every statistic cuts the records only at the start of its unit: a month, a day or an hour. Otherwise it is withheld whole. A declared range's quantile edges, which fall mid-month, withhold the month.

A table that declares `semantics.defaultAggTimeDimension` gets, without `--request`, the mean of each number column that is not a key and has no histogram over a declared range, in each calendar month from the first to the last of the time column's published span or declared range. These are the table's `periods`. They are withheld whole unless the time column's edge statistics all cut at month starts and withhold nothing.

A column that a contract `dependency` sets from an entity key gets its histogram counted per entity, each entity at the value its rows most often hold, under `per`. It is withheld whole when the cells it withholds are not the cells the column's row-level histogram withholds, or when no entity holds a known value.

### Asking for these members, and what stays withheld

A profile request asks for the members in the table's `datePairs` (entries of `start` and `end`) and `calendar` (a list of columns), and in a relationship's `dates` (entries of `parent` and `child`) and `exposure` (entries of `start`, and `end` for a lifetime). A default profile forms them from the contract. On a public profile a request's date pairs, calendar, relationship dates and exposure are formed. A workload is named, not formed, and so was a consumer query through 0.41.0. *(since 0.42.0, [forge-cli #1112](https://github.com/Agenticstiger/forge-cli/pull/1112))* A consumer query is [answered](#consumer-queries) where it can be. Event lags are not formed: neither the request format nor the profile format has a member for them yet.

- **What a withheld cell leaves readable.** Where a date statistic chooses between a published zero and a withheld cell (an order level a contract rule empties, `childless`, the end bins that set a span's or a pair's grain), the choice reads the records. A withheld cell there, a missing `childless` or a coarser grain tells a reader that at least one record lies there, never how many beyond what the check's code says, and never a value.
- **A relationship's day histogram counts child rows.** The children of one parent can fill an end bin, so a published outer edge bounds the days from that parent's date to its children's to the bin, an interval, as a row threshold does in any histogram.
- **`fluxsim init` reads an exposure in one case.** It uses an exposure only when its start and end are the lifetime it reads from the table's date pairs, the pair whose order holds on the most rows. The fixed order matches that when the pair is the table's first pair with an end. Otherwise `fluxsim init` uses none of the table's exposures.

### What the report says

Each line names tables, columns and how many entries were published, never a count of records.

| Line | Counts |
|---|---|
| `exposes[beds]: Date pairs: 2 of 3 published.` | A table's date pairs. A pair published in part is counted apart: `N of M published whole, K in part.` |
| `Dates of exposes[parent] in exposes[child]: ...` | A relationship's dates, counted the same way. |
| `Structural classes of exposes[parent] in exposes[child]: childless, stated by the contract.` | The classes a relationship states. |
| `Exposure of exposes[parent] in exposes[child]: 1 of 6 published.` | A relationship's exposures. |
| `exposes[beds]: Calendar: 4 of 6 histograms published.` | A table's calendar histograms. |
| `exposes[beds]: Periods: N of M monthly groups published.` | A table's monthly periods. |
| `exposes[beds]: Per-entity statistics: N of M published.` | The statistics counted per entity. |
| `tasks.due: no date span: ...` | A date column that kept its quartiles, with the reason. |

## Reference tables published whole

*(since 0.42.0, [forge-cli #1121](https://github.com/Agenticstiger/forge-cli/pull/1121))* A small table that its contract marks `Public` is written whole, under the profile's top-level `references` (PROFILE-SPEC section 5b, format 1-3-0), when it passes the gate below. Its rows are not counts: every value of every column is in the document. A table the gate does not pass is left out, and named. Mark an expose `Public` only when you mean to release all of its rows.

The examples use a small synthetic library. `branches` is a table of its six branches, marked `Public`. `cards` holds a membership card for each version of a member's membership: it has a validity window (`valid_from`, `valid_to`), a `tier` and a foreign key `branch_id` into `branches`. The records are 360 members and 908 cards.

```yaml
fluidVersion: 0.7.7
kind: DataProduct
id: library.members
exposes:
  - exposeId: branches
    kind: table
    policy:
      classification: Public
    contract:
      schema:
        - {name: branch_id, type: string}
        - {name: city, type: string}
  - exposeId: cards
    kind: table
    semantics:
      entities:
        - {name: member, type: natural, expr: member_id}
      dimensions:
        - name: valid_from
          type: time
          typeParams: {timeGranularity: day, validityParams: {isStart: true}}
        - name: valid_to
          type: time
          typeParams: {timeGranularity: day, validityParams: {isEnd: true, chain: nextStart}}
      relationships:
        - name: home_branch
          to: branches
          fromColumns: [branch_id]
          toColumns: [branch_id]
          cardinality: many_to_one
    contract:
      schema:
        - {name: member_id, type: integer}
        - {name: valid_from, type: date}
        - {name: valid_to, type: date}
        - {name: branch_id, type: string}
        - {name: tier, type: "enum('basic','plus','family')"}
```

```bash
fluid profile contract.yaml --source branches=branches.ndjson --source cards=cards.ndjson --out library.profile.json
```

The lines of the report that matter here (the others are left out):

```text
Profiled 2 exposes (branches, cards): 7 columns, 36 values published, 30 withheld.
exposes[cards]: Rounded extremes: valid_from min to year; valid_to min to year.
Children per parent of exposes[branches] in exposes[cards] (home_branch): withheld whole.
exposes[cards]: History: 5 of 10 members published whole, 2 in part.
Published whole, as the contract marks them Public: branches
```

### The gate

A table is written whole only when every one of these holds:

1. **The expose marks itself public.** Its own `policy.classification` is `Public`, spelled so. A lowercase `public`, an expose with no classification, and a `metadata.classification` of the whole product do not count: a product-wide label would publish every table.
2. **A relationship the profile counts reaches it.** It is the parent of a relationship whose [children per parent](#children-per-parent) the profile counts, so a table nothing references is never written, whatever its label.
3. **It is not a versioned table.** No counted relationship reaches it by the natural entity of a table with a validity window, since the keys of such a table repeat.
4. **It holds at most 64 rows.**
5. **It states no row restriction.** It has no `policy.authz.rowFilters` and no `policy.privacy.rowLevelPolicy`.
6. **None of its columns is labelled.** No column has a `sensitivity` other than `none`, a tag or a `labels` key or value with a part `pii`, `phi` or `sensitive` in any case (so `pii-email` and `contains-pii` count), a `sensitivity` label other than `none`, a `semanticType` that names personal data, or a `policy.authz.columnRestrictions` or `policy.privacy.masking` entry. One labelled column keeps the whole table out: it is all or none. *(since 0.42.0, [forge-cli #1124](https://github.com/Agenticstiger/forge-cli/pull/1124))* That covers the labels, the semantic types and the parts of a tag.
7. **The table is not marked personal.** No tag or label with a part `pii`, `phi` or `sensitive` sits on the expose, its `policy`, `policy.authz` or `policy.privacy`. *(since 0.42.0, [forge-cli #1124](https://github.com/Agenticstiger/forge-cli/pull/1124))*
8. **The profile reads every column and can write every cell.** A table with a column the profile does not read (a floating-point column, for example) is left out, and so is a table with a cell longer than 4,096 characters.
9. **The key is one column, never null, and unique.** This is the column of the table that each counted relationship references.

A `semanticType` names personal data when it is one of a set of personal-data types (an email, a phone number, a person's name, a national or passport id, a card or bank number, an address, a birth date, an IP or MAC address, credentials, health and special-category data, and the types forge's own classifier writes), read case-folded with its separators and camel case split, or a longer name that ends in one, such as `customer_email`. `semanticType` is free text, so the set cannot be complete: label a personal column with `sensitivity` as well.

### What the profile writes

The columns stay in the contract's order, and the rows are sorted by the text of the key (in Unicode NFC code point order), so the bytes never follow the order of the source's rows: the same records in another order give the same document. A cell is spelled as the format spells it: a number as canonical decimal text (`12.5` for `12.50`, `1` for `1.0`), a date as `YYYY-MM-DD`, a timestamp as its milliseconds since the epoch, a boolean as `true` or `false`, and a string as stored.

```json
"references": {
  "branches": {
    "columns": ["branch_id", "city"],
    "disclosure": "public",
    "rows": [["central", "Aldermoor"], ["harbour", "Brookby"], ["hillside", "Corley"],
             ["lakeside", "Dunmere"], ["market", "Elstow"], ["station", "Fenwick"]]
  }
}
```

`disclosureRules` gains `"public": {}` beside `acro-default`. A document that holds `references` names format 1-3-0, so its format changes with its digest: a profile of one contract with no date column went from 1-1-0 to 1-3-0.

### Where it is never written

A [private release](#releasing-a-table-under-differential-privacy), a [`--request`](#answering-a-profile-request-request) and a table that a [`--bundle`](#answering-a-fidelity-block-bundle) fidelity block answers never write `references`, whatever the contract marks `Public`.

### What the report names

The report names each table written whole, and each table marked `Public` that is left out, with the reason. A reason names a table, a column or a kind of rule, and never a key, a value or a count:

```text
Published whole, as the contract marks them Public: branches
```

```text
Not measured: reference table branches: no relationship this profile counts reaches it.
Not measured: reference table branches: it is a versioned table, whose keys repeat.
Not measured: reference table branches: it holds more rows than a table released whole may.
Not measured: reference table branches: a row filter or a row-level policy limits who reads its rows.
Not measured: reference table branches: column 'city' carries a label.
Not measured: reference table branches: column 'area' is not read.
Not measured: reference table branches: column 'notes' cannot be written as a cell.
Not measured: reference table branches: a key it is referenced by holds more than one column.
Not measured: reference table branches: its key 'branch_id' is not unique and never null.
```

A table that is not marked `Public` is not named. A history that follows a foreign key into it says why it did not ([below](#following-a-foreign-key)).

## History of a table with a validity window

*(since 0.41.0, [forge-cli #1111](https://github.com/Agenticstiger/forge-cli/pull/1111))* A default profile of a table whose contract declares a validity window publishes the table's `history`. The window is one natural entity and a start and an end, which are both `date` columns or both timestamp columns (see [Versioned tables](../concepts/semantic-layer.md#versioned-tables-window-conventions-and-as-of-reads)). The history says how many versions each entity has, when its first one starts, how long a version lasts, how consecutive versions meet, how the last one ends, and for each categorical column that declares its levels, its first value and its changes. A table that a `--bundle` fidelity block answers writes no history, and neither does a `--request` that does not ask for one. *(since 0.43.0)* A request of format 1-3-0 can ask a table's history: see [Answering a profile request](#answering-a-profile-request-request). A private release writes a [noisy history](#releasing-a-table-under-differential-privacy) for a followed table that its request asks for.

The rows used are those whose entity and start are known. An entity's versions are ordered by start, then end (an open end last). An end is open when it is NULL or equals the `openEnd` the contract declares. The `cards` table of the [library](#reference-tables-published-whole) publishes these members:

| Member | What it counts |
|---|---|
| `versionsPerEntity` | the entities, by their number of versions, on the bins 1, 2, 3, 5, 10 and 20 and up |
| `firstStart` | the entities, by the year of their first version's start |
| `versionLength` | the whole days from a version's start to the next version's start |
| `chain` | each pair of consecutive versions, as `dayBefore`, `gap`, `nextStart` or `overlap` |
| `lastVersion` | the entities, by how their last version ends: `closed` or `open` |
| `columns` | for each categorical column that declares its levels (at most 32 columns of at most 64 levels): `initial`, the value on each entity's first version, and `transitions`, the changes between consecutive versions, grouped by the column's own value |
| `reasons` | with at least two tracked columns, the changes by the one column that moves, or `several` |

Every member goes through the same output checks as any other statistic. The report counts them:

```text
exposes[cards]: History: 5 of 10 members published whole, 2 in part.
```

A member is whole when every group of it is published with no cell withheld, and in part when some cell is published and some is not. Here the ten members are the five fixed ones, `initial` and `transitions` of `branch_id` and `tier`, and `reasons`.

### Withheld a cell at a time

*(since 0.42.0, [forge-cli #1119](https://github.com/Agenticstiger/forge-cli/pull/1119))* `versionsPerEntity`, `versionLength` and `firstStart` are counted on public ladders: versions per entity, whole days, and calendar years. Each is trimmed to the bins that hold records, as a date pair's days are.

- **The ends are coded.** An end bin with fewer than 10 records is joined to the bin beside it, until each end holds at least 10. The coded end then reaches a public bound, which is the ladder's own end, or for `firstStart` and `versionLength` the start column's published extremes. So no outer edge is placed by fewer than 10 records.
- **A cell, not the member.** Each member is checked once, as a set of cells, with complementary suppression: a small cell is withheld, and so is what the check needs beside it, so that no withheld cell comes back by subtraction. A bin inside the ladder that holds no record is a zero, and is withheld with what the check needs beside it. The group and its `k` stay published.
- **A member is withheld whole only when its records together are fewer than 10.** It is then written on the whole public ladder, so its bins say nothing of where records lie.

On the library with six more members of six versions each, `versionsPerEntity` on 0.41.0 and on 0.42.0:

```text
0.42.0: bins 1, 2, 3, 5, 10, 20, and up    cells [85, 90, withheld, withheld, withheld, withheld]
main:   bins 1, 2, 3, and up               cells [85, 90, 190]
```

On 0.42.0 the six members made the bin of 5 to 9 versions small, and the check withheld every bin from 3 up. Now that small end bin is joined to the bin beside it, and the last bin holds the 190 members of 3 versions or more.

`versionLength` of the library has a bin that holds no record, the one of 91 to 180 days, and the check withholds it with the bin beside it. The group's `k` is published:

```json
"versionLength": {"bins": ["8", "31", "91", "181", "366"],
  "groups": [{"binCounts": [175, 210, null, null], "cellStatus": ["F", "F", "C", "C"],
              "k": 550, "group": "", "status": "F"}], ...}
```

A table of 8 members has fewer than 10 entities, so `versionsPerEntity` and `firstStart` are written withheld whole, with `"status": "C"`, on their whole ladders. Its version lengths number 10 or more, so `versionLength` is published, on one bin.

### First starts beside the start and end columns

*(since 0.42.0, [forge-cli #1119](https://github.com/Agenticstiger/forge-cli/pull/1119))* `firstStart` is published. Through 0.41.0 it was always withheld whole.

Every end that is not an entity's last is the next version's start. So the start column's records below a date, less the first starts below it, are the later versions' starts, and the end column's records below it, less those, are the closed last ends. A reader who knows the start and end columns' published counts at a date (a histogram's cells, a quantile's bin, the `min` and `max`) and the first starts there can work out both. Any two of the start column, the first starts and the later versions' starts give the third. Any two of the end column, the later versions' starts and the closed last ends do too.

So the first starts are checked against the two columns. When a count of later versions' starts or of closed last ends that a reader could form only through the first starts is small (or zero, where zeros are disclosive), the two first-start cells beside the date that sets it apart are withheld, until none is left. When only the records' own outer edge sets it apart, `firstStart` is withheld whole. Where the published versions per entity show that every entity has one version, and no row with a start lacks an entity, the later versions' starts are 0 everywhere and count as known.

In the library, 3 entities have a closed last version that ends before 2020, a small count that the end column, the start column and the first starts would give back. So the first starts of 2019 and 2020 are withheld, and those of 2021 and 2022 are published. With 13 such entities in place of 3, all four cells are published.

```json
"firstStart": {"bins": ["1546300800000", "1577836800000", "1609459200000", "1640995200000", "1672531200000"],
  "groups": [{"binCounts": [null, null, 100, 80], "cellStatus": ["C", "C", "F", "F"],
              "k": 360, "group": "", "status": "F"}], ...}
```

The bins are the starts of 2019, 2020, 2021, 2022 and 2023.

### Zeros the contract states

*(since 0.42.0, [forge-cli #1119](https://github.com/Agenticstiger/forge-cli/pull/1119))* A contract can declare a `lifecycle` on the natural entity, with an `endMarker` or a `currentFlag` (see [Versioned tables](../concepts/semantic-layer.md#the-natural-entity-s-life-cycle)). Each states zeros:

- An `endMarker` ends an entity with a marked version, and never by closing its last one. `lastVersion` then writes `closed` as 0, and the marker value's `transitions` group is written as zeros.
- A `currentFlag` marks the last version of an entity, so its value's `transitions` group is written as zeros.

This holds only where the records leave those cells empty, as a declared `chain` already does. Where the records break the statement, the cells are checked like any other. In a library whose members end with a final version marked `lapsed`:

```yaml
entities:
  - name: member
    type: natural
    expr: member_id
    lifecycle:
      endMarker: {column: status, value: lapsed}
```

`lastVersion` is published, `closed` as 0 and `open` as 360 (the count the output check rounds to), and the `lapsed` group of `status` is `[0, 0]`. Without the declaration the same records give a zero `closed`, which is withheld, and `lastVersion` is withheld whole. When 40 members end with a closed version that is not marked, `closed` is no zero and is published as any cell is.

### `lastVersion` beside the end column's NULLs

*(since 0.42.0, [forge-cli #1119](https://github.com/Agenticstiger/forge-cli/pull/1119))* The end column's NULL ends, less the open last versions, are the rows that have no entity and a NULL end. When that count is small, both levels of `lastVersion` are withheld, since the end column's `nullCount` would give it back. With 3 such rows added to the library, `lastVersion` goes from `[95, 265]` to withheld whole.

### Following a foreign key

*(since 0.42.0, [forge-cli #1121](https://github.com/Agenticstiger/forge-cli/pull/1121))* A history tracks a foreign key into a table that [the profile publishes whole](#reference-tables-published-whole). The levels of the tracked column are that table's keys, in the order it publishes them, and its `initial` and `transitions` pass the same output checks as any tracked column's. Through 0.41.0 the `branch_id` of the library was named under `Not measured` with "the contract declares no levels for it" and not tracked.

A foreign key is tracked when it is one column, the relationship that keys it is counted, and the table it references is published whole. When it is not followed, the report says why, naming no value:

```text
Not measured: history of cards.branch_id: the table it references is not declared public.
Not measured: history of cards.branch_id: the table it references is left out: column 'city' carries a label.
Not measured: history of cards.branch_id: its key is not text or a whole number.
```

**Whole-number keys.** *(since 0.43.0)* A key typed as an integer, or as a decimal of scale 0, is followed as a text key is. Its levels are the published table's keys, spelled as that table spells them, and the column is written in the category domain, from its values' decimal text. It then holds the metrics that domain forms (`count`, `nullCount` and the withheld `distinctCount`); its `sum`, `min`, `max` and `quantiles` are not formed. Through 0.42.0 such a key was named as not followed, and the history carried it as an untracked column, so a generated history held each entity's key constant across its versions. A key that is neither text nor a whole number (a float, a decimal with a scale, a date) is named as not followed, with the reason "its key is not text or a whole number". A key that is not followed keeps its number domain and every metric it had, whatever the reason.

**At least three keys.** *(since 0.43.0)* A history follows a key into a table of at least three keys. With two, the published totals pin the cells, so a table of fewer than three keys is not followed and the profile is byte for byte that of a profile that follows no key. A table that is not published whole, two relationships on the column, a key over the cap, and a key that a statistic the contract declares reads are not followed either. The most columns a history follows is 32, and it counts the candidates, so a column whose values fail the read keeps its place under that cap. That is the one change for a profile that follows no key.

**Decided by the contract.** *(since 0.43.0)* The keys a history follows are the plan's alone: the contract, and the public keys of the tables released whole. A key that a record then proves is no key of its table is still one of them, so it is written as the category it would be followed as, and only its history is left out. Cells of the key's `initial` and `transitions` are checked exactly as for a text key.

**Children per parent are withheld.** *(since 0.43.0)* A published cell of the key's `initial`, the size of a group and a change into or out of a key are each a floor on the children of that key's parent. So whenever the contract makes a history follow a key, the children per parent of the relationship that keys the column are withheld whole, whatever the records hold, and the report says so under `Not measured`, with a note that holds no count and no structural class:

```text
Not measured: children per parent of cards(branch_id) to branches: its key is one a history may follow by the keys of a table published whole, so it is withheld whatever the records hold.
```

The key's `initial` and `transitions` then go through the ordinary output check, like any categorical column's, and are published as it allows. The key's levels and the reference table stay published.

*Through 0.42.0 the profile decided from the counts. It withheld the key's `initial` and `transitions` whole where their counts, beside the relationship's children per parent, would bound a withheld cell, and so published the children per parent in some profiles and not in others.* That decision read the counts, which on a very small child table could itself narrow a withheld count. A 0.42.0 profile that writes `references` and a history tracking a foreign key over a small table should be regenerated with 0.43.0 before it is shared further.

## Where the time goes: `--timings`

*(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* `--timings` prints, after the report and for each table in profile order, how long the table took to read, measure and check, and then how long the document took to write:

```bash
fluid profile contract.json --source beds=./beds.ndjson --source waterings=./waterings.ndjson --out garden.profile.json --timings
```

```text
Timings for beds: read 0.00 s, measure 0.03 s, check 0.00 s.
Timings for waterings: read 0.00 s, measure 0.05 s, check 0.00 s.
Timings for the document: write 0.01 s; total 0.16 s.
```

Your numbers differ. Read is the source read. Measure forms the table's metrics, statistics, date spans, children per parent, facts and rank correlations. Check is the output checks across a column's statistics and a relationship's counts, and a check made metric by metric counts as measure. Work that spans tables, such as facts and groupings, is shared equally among the tables it names.

The timings are in the report only. The document is the same bytes with and without the flag, so its digest does not change. A private release refuses `--timings` before any record is read, because a duration follows the row count:

```text
CLI command error
❌ profile_timings_with_release  [ERR_PROFILE_TIMINGS_WITH_RELEASE]
  detail: a private release prints nothing that depends on the records outside the noise, and timings follow the row count
  read: nothing: no record was read
  next: leave --timings out of a private release
```

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

*(since 0.33.0, [forge-cli #965](https://github.com/Agenticstiger/forge-cli/pull/965))* The second line of this output reads `Withheld, by the check (CL_CONF_STATUS code): A (small count) 3.`

The document is FLUX's profile format `1-0-0`, or `1-1-0` when it holds a `quantile/2` (see [Default statistics without `--bundle`](#default-statistics-without-bundle)), in canonical JSON (RFC 8785), so the file's own sha256 is the digest. The same forge-cli release, given the same records, writes the same bytes, whichever of the four kinds of source they come from. The document names the release in `_producer`, so another release writes another digest. *(since 0.41.0, [forge-cli #1106](https://github.com/Agenticstiger/forge-cli/pull/1106))* A document that holds one of the time and structure members (a calendar, date pairs, a relationship's dates, structural classes, exposure, periods or a statistic counted per entity) is format `1-3-0` (see [Time and structure statistics](#time-and-structure-statistics)). A default profile of a table with a date or timestamp column holds a calendar. A profile that also holds the 0.40.0 rank-correlation or follow members is `1-4-0`. *(since 0.43.0)* A private release that holds a null count, a noisy history or a noisy query is `1-5-0`. *(since 0.42.0, [forge-cli #1121](https://github.com/Agenticstiger/forge-cli/pull/1121))* A profile that holds `references` is `1-3-0`: see [Reference tables published whole](#reference-tables-published-whole). Pin the digest in the Simulation: copy the line the command printed into the `com.agentics.flux/1` namespace of the Simulation's `extensions`, indented to sit beside `emits`:

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

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* With [`--bundle`](#answering-a-fidelity-block-bundle), the profile answers every property of the block but a correlation, so flux-sim-engine 0.6.2 scores each of them against it, and a property whose groups the checks withheld scores as censored.

The rest of the FLUX documentation is at [agenticstiger.github.io/flux](https://agenticstiger.github.io/flux/).
