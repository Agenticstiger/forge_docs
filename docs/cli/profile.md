# `fluid profile`

Profile one expose's records where they live, and write a profile document of output-checked aggregates. A FLUX Simulation pins the document by its digest, so the FLUX engine reads aggregates of the real data and never a record of it.

*On forge-cli `main`, not yet in a release ([forge-cli #909](https://github.com/Agenticstiger/forge-cli/pull/909)).*

::: warning Groundwork: it does not profile yet
FLUX's statistic registry forms every statistic, and the fidelity check uses the same registry, so a profile and a check of the same records hold the same numbers. The registry is becoming its own package, `flux-stats`, which is not published yet. Until it is, `fluid profile` stops before it reads anything:

```text
❌ profile_statistics_unavailable  [ERR_PROFILE_STATISTICS_UNAVAILABLE]
  detail: fluid profile forms every statistic with flux-stats, the statistic registry FLUX shares with its fidelity check, and flux-stats is not published yet
  read: nothing: no record was read
  next: pip install 'data-product-forge[profile]' once flux-stats is published
```

The rest of this page describes the command as forge-cli's `main` builds it.
:::

## Where it runs

The profiler is the one part of FLUX that reads records. It runs inside the environment that holds the data, with that environment's own access to it. Only the profile document leaves: no record, no sample of records, and no per-record value. This is the boundary FLUX's ADR 0003 draws, and everything that crosses it has passed the checks below.

## Syntax

```bash
fluid profile CONTRACT --source SOURCE [--expose ID] [--table NAME] [--out FILE] [--env ENV]
```

| Argument | What it does |
|---|---|
| `CONTRACT` | The FLUID contract (or a stage-1 bundle `.tgz`) that declares the expose. Its `exposeId` keys the profile's table, and each column's type gives the domain it is read in. |
| `--source` | Where the records live. See [Sources](#sources). |
| `--expose`, `--expose-id` | The expose to profile. Optional when the contract has one expose. |
| `--table` | The table of a database `--source`, as `name` or `schema.name`. Refused for a file. |
| `--out` | Where to write the document. Default: `<exposeId>.profile.json` in the current directory. |
| `--env` | An environment overlay to apply to the contract first. |

Install the extra, which adds DuckDB:

```bash
pip install 'data-product-forge[profile]'
```

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

A withheld value keeps its SDMX `CL_CONF_STATUS` code and carries no value. Every metric also carries `sampleSize`, the band its number of records lies in. For a withheld count the band is `0` to `9`, and for a published one it is the counts that round to it. Neither says more than the code or the rounded count.

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

The document is FLUX's profile format `1-0-0` in canonical JSON (RFC 8785), so the file's own sha256 is the digest. The same forge-cli release, given the same records, writes the same bytes, whichever of the four kinds of source they come from. The document names the release in `_producer`, so another release writes another digest. Pin the digest in the Simulation:

```yaml
extensions:
  com.agentics.flux/1:
    profile:
      digest: sha256:32aefe6ed451030bb4961edc5750d8f4cd0ea1b05a741168390abc1faba19285
```

Nothing is written, and no directory is made, until the profile is formed. The document is written readable by you alone, and never through a symbolic link: a link at the target is refused, and so is an `--out` that names the source file. The default name is `<exposeId>.profile.json` only when the exposeId holds nothing but letters, digits, `_`, `.` and `-`. Otherwise name the file with `--out`.

Each refusal names a stable code, for example `profile_expose_not_found`, `profile_source_unreadable`, `profile_value_refused` or `profile_out_is_a_link`, and nothing is written. A refusal names a column, a row or line number and the kind of value at fault, never the value itself.
