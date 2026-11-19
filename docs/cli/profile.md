# `fluid profile`

Profile one expose's records where they live, and write a profile document of output-checked aggregates. A FLUX Simulation pins the document by its digest, so the FLUX engine reads aggregates of the real data and never a record of it.

*(since 0.31.0, [forge-cli #909](https://github.com/Agenticstiger/forge-cli/pull/909), [forge-cli #925](https://github.com/Agenticstiger/forge-cli/pull/925), [forge-cli #946](https://github.com/Agenticstiger/forge-cli/pull/946), [forge-cli #949](https://github.com/Agenticstiger/forge-cli/pull/949), [forge-cli #951](https://github.com/Agenticstiger/forge-cli/pull/951))*

FLUX's statistic registry, `flux-stats`, reads every value and forms every statistic. The fidelity check uses the same registry, so a profile and a check of the same records hold the same numbers.

The `[profile]` extra installs DuckDB and `flux-stats` from PyPI. 0.34.0 needed `>=0.6.2,<0.7`. *(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* It needs `flux-stats[yaml]>=0.7.0,<0.8`. Without flux-stats, `fluid profile` stops before it reads anything and says what to install:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: fluid profile forms every statistic with flux-stats, the statistic registry FLUX shares with its fidelity check, and flux-stats is not installed. It needs flux-stats[yaml]>=0.7.0,<0.8; install it with: pip install 'data-product-forge[profile]'
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
fluid profile CONTRACT --source SOURCE [--expose ID] [--table NAME] [--out FILE] [--fractional-bits N] [--bundle DIR] [--env ENV]
```

| Argument | What it does |
|---|---|
| `CONTRACT` | The FLUID contract (or a stage-1 bundle `.tgz`) that declares the expose. Its `exposeId` keys the profile's table, and each column's type gives the domain it is read in. |
| `--source` | Where the records live. See [Sources](#sources). |
| `--expose`, `--expose-id` | The expose to profile. Optional when the contract has one expose. |
| `--table` | The table of a database `--source`, as `name` or `schema.name`. Refused for a file. |
| `--out` | Where to write the document. Default: `<exposeId>.profile.json` in the current directory. |
| `--fractional-bits` | The grid [`mean/1`](#the-mean-1-statistic) is formed on, in steps of 2^-N: 0 to 128, default 16. Set it to the fidelity block's `encoding.fractionalBits`. |
| `--bundle` | *(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* A FLUX bundle directory: the profile answers the fidelity block its one Simulation declares for the expose, on the block's grid, and a different `--fractional-bits` is refused. See [Answering a fidelity block](#answering-a-fidelity-block-bundle). |
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

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* [`--bundle`](#answering-a-fidelity-block-bundle) writes the statistic each property of a fidelity block declares, a grouped `mean/1`, the histograms, `support/1` and `quantile/1` among them, and still no `correlation/1`.

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

`--bundle` needs flux-stats 0.6.2 or newer, the first release that holds the fidelity grammar, and through 0.34.0 the `[profile]` extra asked for `>=0.6.2,<0.7`. *(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* It asks for `flux-stats[yaml]>=0.7.0,<0.8`, the first release that holds the readers and the check below. With an older flux-stats, `--bundle` stops before it reads anything:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: --bundle reads the fidelity block with flux-stats, and the installed flux-stats lacks flux_stats.fidelity. It needs flux-stats[yaml]>=0.7.0,<0.8
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
- Through 0.34.0 the checks did not close one gap. A reader can still subtract one histogram's published counts from another's, or from a level histogram's group size, and read a withheld cell, a zero included, to within the rounding. forge-cli plans to close it with FLUX's `check_edge_counts`, which a flux-stats release has to carry first, and to ship that in a later release.

*(since 0.35.0, [forge-cli #1021](https://github.com/Agenticstiger/forge-cli/pull/1021))* Through 0.34.0 the last point above was an open gap. Now `fluid profile` passes every histogram, level histogram and quantile of a column to flux-stats' `check_edge_counts` in one call, and publishes what it lets through. A histogram and a coarser one of one column, or a published cell and the column's count, no longer give a withheld cell back by subtraction, and a cell that does goes with it. A level histogram is checked over its levels as it is over bins, so one small level withholds a neighbour. A histogram that does not sit on the column's one partition of bins is withheld, and so is a group whose rounded counts no longer prove its quantile. The summary counts a cell or group withheld for its size or rounding as `A`, and one withheld so that another cannot be recovered as `D`. The check does not see a column's `support/1`, the group sizes of a statistic grouped by the column, or a declared level that holds no record, which is absent from a grouped statistic.

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

*(since 0.32.0, [forge-cli #959](https://github.com/Agenticstiger/forge-cli/pull/959))* With [`--bundle`](#answering-a-fidelity-block-bundle), the profile answers every property of the block but a correlation, so flux-sim-engine 0.6.2 scores each of them against it, and a property whose groups the checks withheld scores as censored.

The rest of the FLUX documentation is at [agenticstiger.github.io/flux](https://agenticstiger.github.io/flux/).
