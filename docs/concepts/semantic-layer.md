---
title: The semantic layer
description: Declare measures, dimensions and metrics once in exposes[].semantics, then query them over MCP, ship them to dbt MetricFlow, or hand them to OSI tools.
---

# The semantic layer

An expose can carry a `semantics` block: the entities, dimensions, measures
and metrics that say what its columns mean. The block lives in the contract,
next to the schema it describes, and three parts of the CLI read it:

| Consumer | Command | What it does with `semantics` |
|---|---|---|
| Governed MCP `query` tool | [`fluid mcp output-port serve`](../cli/mcp.md#consumer-fluid-mcp-output-port-serve) | Compiles a metric or measure, plus dimensions and filters, to parameterised SQL and runs it |
| dbt MetricFlow | [`fluid generate transformation`](../cli/generate.md#fluid-generate-transformation) | Writes `models/semantic_models.yml` and a time-spine model into the generated dbt project |
| dbt importer | [`fluid import dbt`](../cli/import.md#importing-a-dbt-project) | Reads a manifest's `semantic_models` and `metrics` back into `exposes[].semantics` |

A fourth artifact, the OSI sidecar, is written by `fluid forge data-model` from
its logical model rather than from the contract block. See
[The OSI sidecar](#the-osi-sidecar).

## Example

A small orders table, bound to a local CSV so it runs without a warehouse:

```text
orders/
├── contract.fluid.yaml
└── orders.csv
```

```yaml
# orders/contract.fluid.yaml
fluidVersion: 0.7.5
kind: DataProduct
id: sales.orders_metrics
name: Orders metrics
domain: sales
metadata:
  layer: Gold
  owner:
    team: sales-analytics
    email: sales-analytics@example.com
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./orders.csv
        table: orders
    contract:
      schema:
        - { name: order_id, type: INTEGER, required: true }
        - { name: customer_id, type: STRING }
        - { name: order_date, type: DATE }
        - { name: status, type: STRING }
        - { name: amount, type: DECIMAL }
    semantics:
      name: orders
      description: One row per order.
      defaultAggTimeDimension: order_date
      entities:
        - { name: order, type: primary, expr: order_id }
        - { name: customer, type: foreign, expr: customer_id }
      dimensions:
        - { name: order_date, type: time, typeParams: { timeGranularity: day } }
        - { name: status, type: categorical }
      measures:
        - { name: revenue, agg: sum, expr: amount }
        - { name: order_count, agg: count, expr: order_id }
      metrics:
        - name: completed_revenue
          type: simple
          measure: revenue
          filter: "status = 'completed'"
        - { name: orders, type: simple, measure: order_count }
```

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.5)
Validation completed in 0.003s

$ fluid mcp output-port list contract.fluid.yaml

Exposes in contract.fluid.yaml (1 total):

  • orders  (table)
      title:  <unset>
      engine: local/csv → ./orders.csv
      tools:  describe, sample, query  [semantics]
```

The `query` tool is listed because the expose has a `semantics` block with at
least one metric, measure or dimension. Without one, the server offers
`describe` and `sample` only.

An agent connected to `fluid mcp output-port serve contract.fluid.yaml` that
calls `query` with `{"metric": "completed_revenue"}` gets the metric's filter
applied and sees the SQL that ran:

```json
{
  "exposeId": "orders",
  "columns": ["completed_revenue"],
  "rows": [{ "completed_revenue": 460.0 }],
  "rowCount": 1,
  "truncated": false,
  "compiled": {
    "sql": "SELECT SUM(amount) AS completed_revenue\nFROM orders\nWHERE (status = 'completed')\nLIMIT 100",
    "parameters": null
  }
}
```

With `{"metric": "orders", "dimensions": ["status"]}` the dimension is added to
the `SELECT` and the `GROUP BY`:

```text
SELECT status AS status, COUNT(order_id) AS orders
FROM orders
GROUP BY status
ORDER BY orders DESC, status ASC
LIMIT 100
```

A time dimension is truncated to its declared grain, here
`DATE_TRUNC('day', order_date)`. The
[MCP output port walkthrough](../walkthrough/mcp-output-port.md) shows how to
drive the server from the MCP Inspector or an editor.

## The `semantics` block

The block is MetricFlow-shaped: names and meanings follow dbt's semantic
models, spelled in camelCase.

| Key | Holds | Notes |
|---|---|---|
| `name`, `description` | What the model represents | |
| `defaultAggTimeDimension` | The time dimension measures aggregate over by default | Overridden per measure with `aggTimeDimension` |
| `entities[]` | Join keys: `name`, `type` (`primary`, `foreign`, `unique`, `natural`), `expr` | `expr` defaults to the entity name |
| `dimensions[]` | Grouping axes: `name`, `type` (`categorical`, `time`), `expr`, `typeParams.timeGranularity` | Granularities: `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year` |
| `measures[]` | Aggregations: `name`, `agg`, `expr`, `aggTimeDimension`, `nonAdditiveDimension`, `createMetric` | `agg`: `sum`, `avg`, `count`, `count_distinct`, `min`, `max`, `median`, `percentile` |
| `metrics[]` | Named KPIs: `name`, `type` (`simple`, `derived`, `ratio`), `measure`, `filter`, `inputMetrics`, `expr`, `numerator`, `denominator`, `owner` | |
| `tags`, `labels` | Discovery metadata | |

The block, and each entry in its lists, rejects keys it does not declare, so a
typo fails `fluid validate`.

### Percentile measures need the 0.7.6 preview

`agg: percentile` exists in the stable 0.7.5 schema, but the percentile value
itself, `aggParams`, is only in the **0.7.6 preview**:

```yaml
fluidVersion: "0.7.6"
# ...
      measures:
        - name: p90_amount
          agg: percentile
          expr: amount
          aggParams:
            percentile: 0.9              # 0..1; 0.5 when omitted
            useDiscretePercentile: false # true = PERCENTILE_DISC
```

Under `fluidVersion: 0.7.5` the same measure fails validation:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
...
 1. exposes[0].semantics.measures[2]: Additional properties are not allowed
('aggParams' was unexpected)
```

A percentile measure without `aggParams` is read as the median (0.5) by both
the MCP compiler and the MetricFlow export, so the two consumers return the
same number. Through the MCP `query` tool, the measure above compiles to
`PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount)`.

### Relationships and validity windows need the 0.7.7 preview

*(since 0.31.0, [forge-cli #894](https://github.com/Agenticstiger/forge-cli/pull/894))*

Two fields are in the **0.7.7 preview** schema only. `relationships` names a
foreign key from one expose to another expose of the same contract. A
`validityParams` entry on a time dimension marks one end of the validity window
of a type II slowly changing dimension (SCD). This contract has an `orders`
expose and a `customer_history` expose that keeps one row per version of a
customer:

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: sales.orders_history
name: Orders with customer history
domain: sales
metadata:
  layer: Gold
  owner:
    team: sales-analytics
exposes:
  - exposeId: orders
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./orders.csv
        table: orders
    contract:
      schema:
        - { name: order_id, type: INTEGER, required: true }
        - { name: customer_id, type: STRING }
        - { name: order_date, type: DATE }
        - { name: amount, type: DECIMAL }
    semantics:
      name: orders
      defaultAggTimeDimension: order_date
      entities:
        - { name: order, type: primary, expr: order_id }
        - { name: customer, type: foreign, expr: customer_id }
      dimensions:
        - { name: order_date, type: time, typeParams: { timeGranularity: day } }
      measures:
        - { name: revenue, agg: sum, expr: amount }
      relationships:
        - name: orders_to_customer_history
          to: customer_history
          fromColumns: [customer_id]
          toColumns: [customer_id]
          cardinality: many_to_one
          joinType: left
  - exposeId: customer_history
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./customer_history.csv
        table: customer_history
    contract:
      schema:
        - { name: customer_id, type: STRING, required: true }
        - { name: segment, type: STRING }
        - { name: valid_from, type: TIMESTAMP }
        - { name: valid_to, type: TIMESTAMP }
    semantics:
      name: customer_history
      entities:
        - { name: customer, type: natural, expr: customer_id }
      dimensions:
        - { name: segment, type: categorical }
        - name: valid_from
          type: time
          typeParams:
            timeGranularity: day
            validityParams: { isStart: true }
        - name: valid_to
          type: time
          typeParams:
            timeGranularity: day
            validityParams: { isEnd: true }
```

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.7)
Validation completed in 0.013s
```

A relationship has five required fields and one optional one:

| Field | Holds |
|---|---|
| `name` | The relationship's name. Names must differ within one expose |
| `to` | The `exposeId` of the target. It must be an expose of the same contract |
| `fromColumns` | The foreign-key columns of the expose that declares the relationship, in key order |
| `toColumns` | The key columns of the target, in the order of `fromColumns` |
| `cardinality` | `many_to_one` or `one_to_one`. Required |
| `joinType` | `left` (the default) keeps rows with no match. `inner` drops them |

Declare a relationship on the many side, the expose that holds the foreign key.
The two column lists pair up by position, so they must have the same length and
every column must be one the expose declares in `contract.schema`. A composite
key is one relationship with two columns in each list, not two relationships.
Against a target that has a validity window, the one matching row is the
version valid at the time of the declaring row. *(since 0.41.0, [forge-cli #1099](https://github.com/Agenticstiger/forge-cli/pull/1099))* A relationship
names that time with `asOf`, and a rule can read the window's target by entity
or as of a date: see
[Versioned tables](#versioned-tables-window-conventions-and-as-of-reads).

A validity window is how the contract says a table keeps history. A model that
uses `validityParams` needs exactly:

- two time dimensions, one with `validityParams: { isStart: true }` and one with
  `validityParams: { isEnd: true }`, and
- one `natural` entity, the key whose versions the window separates
  (`customer` above).

A contract that declares `fluidVersion: "0.7.6"` and uses either field fails
validation, and the error says which version to set:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (3 error(s)) (schema v0.7.6)
Validation completed in 0.008s

Validation Errors:
==================
 1. exposes[0].semantics: 'relationships' (named relationships between exposes) is a field of the 0.7.7 preview schema: set the contract's fluidVersion to 0.7.7 to use it
 2. exposes[1].semantics.dimensions[1].typeParams: 'validityParams' (the validity window of a slowly changing dimension) is a field of the 0.7.7 preview schema: set the contract's fluidVersion to 0.7.7 to use it
 3. exposes[1].semantics.dimensions[2].typeParams: 'validityParams' (the validity window of a slowly changing dimension) is a field of the 0.7.7 preview schema: set the contract's fluidVersion to 0.7.7 to use it
```

On 0.7.7, `fluid validate` also checks what the schema cannot. With `to:
customers` in place of `to: customer_history`:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.012s

Validation Errors:
==================
 1. exposes[orders].semantics.relationships[0].to: 'customers' is not an exposeId of this contract (customer_history, orders). A relationship joins two exposes of one contract.
```

The same checks reject lists of different lengths, a column the expose does not
declare, a repeated relationship name, and a window that is not two time
dimensions beside one natural entity.

A one-column relationship also gets a warning when no entity pair matches it,
because the dbt export joins by entity name (see
[dbt MetricFlow](#dbt-metricflow)). Renaming the natural entity above to
`client` gives:

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.7)
⚠️  1 warning(s)
Validation completed in 0.012s

Validation Warnings:
====================
 1. exposes[orders].semantics.relationships[0]: no entity pair matches this relationship, and the dbt MetricFlow export joins by entity name, so it will not follow the relationship. Declare an entity with expr 'customer_id' on exposes[orders] (type foreign) and one of the same name with expr 'customer_id' on exposes[customer_history] (type natural).
```

### Versioned tables: window conventions and as-of reads

*(since 0.41.0, [forge-cli #1099](https://github.com/Agenticstiger/forge-cli/pull/1099))*

A type II table repeats its natural key once per version, so a foreign key into it names an entity, not a row. Through 0.40.1, a FLUID SQL/1 path and a `sharedColumns` entry could not read such a table through a relationship, and `fluid validate` refused both (see [FLUID SQL/1](./data-rules.md#fluid-sql-1)). The 0.7.7 preview now has four more members. Two state the window's conventions, one describes the natural entity's life, and one lets a relationship read the version valid on a date. All four are optional. A contract that declares none of them validates and exports as before.

This contract has a `station_version` expose, one row per version of a weather station, and a `reading` expose that relates to it twice:

```yaml
fluidVersion: "0.7.7"
kind: DataProduct
id: weather.stations
name: Weather stations
domain: weather
metadata:
  layer: Gold
  owner:
    team: weather-platform
exposes:
  - exposeId: station_version
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./station_version.csv
        table: station_version
    contract:
      schema:
        - { name: station_id, type: INTEGER, required: true }
        - { name: valid_from, type: DATE }
        - { name: valid_to, type: DATE }
        - { name: is_current, type: BOOLEAN }
        - { name: status, type: STRING }
        - { name: commissioned_on, type: DATE }
        - { name: network_id, type: INTEGER }
        - { name: sensor_model, type: STRING }
      invariants:
        - id: network_stable_per_station
          dependency: { from: [station_id], to: [network_id] }
    semantics:
      name: station_version
      entities:
        - name: station
          type: natural
          expr: station_id
          lifecycle:
            activation: commissioned_on
            endMarker: { column: status, value: DECOMMISSIONED }
            currentFlag: { column: is_current, value: true }
      dimensions:
        - name: valid_from
          type: time
          typeParams:
            timeGranularity: day
            validityParams: { isStart: true }
        - name: valid_to
          type: time
          typeParams:
            timeGranularity: day
            validityParams: { isEnd: true, openEnd: "9999-12-31", chain: dayBefore }
  - exposeId: reading
    kind: table
    binding:
      platform: local
      format: csv
      location:
        path: ./reading.csv
        table: reading
    contract:
      schema:
        - { name: reading_id, type: INTEGER, required: true }
        - { name: station_id, type: INTEGER }
        - { name: reading_date, type: DATE }
        - { name: network_id, type: INTEGER }
        - { name: sensor_model, type: STRING }
        - { name: temperature_c, type: DOUBLE }
    semantics:
      name: reading
      entities:
        - { name: station, type: foreign, expr: station_id }
      relationships:
        - name: station
          to: station_version
          fromColumns: [station_id]
          toColumns: [station_id]
          cardinality: many_to_one
          sharedColumns: [network_id]
        - name: station_on_date
          to: station_version
          fromColumns: [station_id]
          toColumns: [station_id]
          cardinality: many_to_one
          asOf: reading_date
          sharedColumns: [sensor_model]
```

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.7)
Validation completed in 0.423s

Validation Notes:
=================
...
```

The two notes are about columns both exposes carry that the relationship in question does not copy (`sensor_model` on `station`, `network_id` on `station_on_date`). They are notes, and the contract stays valid.

The two relationships state two rules: a reading's network is its station's network (`station`), and a reading's sensor model is the one its station had on the reading date (`station_on_date`).

#### The window's conventions

Two members go on the `validityParams` of the dimension that has `isEnd: true`. On the other bound, `fluid validate` reports them as misplaced:

| Member | Values | Default | Meaning |
|---|---|---|---|
| `openEnd` | `null`, or a literal of the end column's type, such as `"9999-12-31"` | `null` | What the end of a version holds while the entity continues. Under `null`, an end that is NULL is open. Under a literal, an end equal to it is open. An open version is valid from its start on. |
| `chain` | `nextStart`, `dayBefore` or `none` | `nextStart` | How a closed version's end meets the same entity's next start. `nextStart`: the end equals the next start, as dbt snapshots write it, and a version is valid on `[start, end)`. `dayBefore`: the end is the day before the next start, as Kimball's type 2 writes it, and a version is valid on `[start, end]`. It takes `DATE` columns only. `none`: versions may leave gaps, and a version is valid on `[start, end]`. |

A window that declares neither keeps the meaning it had on 0.7.7 before: `openEnd: null` and `chain: nextStart`. Versions of one entity are not expected to overlap, and only the last is open. Neither `fluid validate` nor the exported rules check the data for that; [what a read does](#reading-a-versioned-table-through-a-relationship) when they do is below.

#### The natural entity's life cycle

`lifecycle` goes on the `natural` entity of a model that declares a window. It has three optional members, and at least one is required:

| Member | Holds | Declares |
|---|---|---|
| `activation` | A column of the expose, of the window's type | Every version of an entity holds one value there: the start of the entity's first version |
| `endMarker` | `{column, value}`: a column of the expose, and a literal of its type | An entity ends with a final version that holds `value` in `column`. That version's start is the entity's end, and no earlier version holds `value` |
| `currentFlag` | `{column, value}` | `column` holds `value` on exactly one version of each entity: its last |

`fluid validate` checks that each column is declared in `contract.schema`, that `activation` has the window's type, and that each `value` is a literal its column can hold. The dbt export reads a boolean `endMarker` (see [dbt MetricFlow](#dbt-metricflow)), and the ODCS export carries all three. No export checks the data against `activation` or `currentFlag`.

#### Reading a versioned table through a relationship

A relationship **reaches an entity** when its target declares a window and its `toColumns` are exactly the target's natural entity. Only such a relationship can be read. It reads in one of two ways, by entity or as of a date.

**By entity.** A FLUID SQL/1 path (`station.network_id`) or a `sharedColumns` entry may name the natural key, and any column that is stable per entity. A column is stable per entity when the target declares a `dependency` invariant whose `from` is exactly the natural entity's column and whose `to` holds the column. In the contract above, `network_stable_per_station` makes `network_id` stable, so the `station` relationship may copy it. Any other column is refused, because the versions of one entity may disagree on it. The join reads one row per entity: an entity whose versions disagree on a column reads NULL, and the row is not covered by the rule.

**As of a date.** `asOf` names a `DATE`, `TIMESTAMP` or `TIMESTAMPTZ` column of the expose that declares the relationship, of the same type as the target's window columns. A date never meets a timestamp, and a timestamp never meets a timestamptz. A path through such a relationship may read any column of the version, and `sharedColumns` may copy any column. On each row, the relationship reaches the version valid on the `asOf` date, by the window's `chain`:

- A version is valid from its start. It is valid up to its end, not including the end under `nextStart` and including it under `dayBefore` and `none`. An open version never ends.
- A date before the entity's first start, after a closed last version or in a gap reaches no version. A path then reads NULL, and the row is not covered by `sharedColumns`.
- A row reaches at most one version. Where versions of an entity overlap, only the one that starts last on or before the date can be read. If that version is not valid on the date, the row reaches no version, even when an earlier one is.
- From the day two versions of an entity start together, the entity reaches no version, until a later version starts. Earlier dates read the version before.
- Under an `openEnd` literal, a version whose end is NULL is not a version the rules can read.

One expose may reach a target through several as-of relationships, one for each date. A `maintenance_event` row names the version it closes and the one it opens:

```yaml
    contract:
      schema:
        - { name: event_id, type: INTEGER, required: true }
        - { name: station_id, type: INTEGER }
        - { name: event_date, type: DATE }
        - { name: day_before, type: DATE }
        - { name: sensor_model_before, type: STRING }
        - { name: sensor_model_after, type: STRING }
      invariants:
        - id: model_before
          derive: sensor_model_before
          expr: version_before.sensor_model
        - id: model_after
          derive: sensor_model_after
          expr: version_after.sensor_model
    semantics:
      name: maintenance_event
      entities:
        - { name: station, type: foreign, expr: station_id }
      relationships:
        - name: version_before
          to: station_version
          fromColumns: [station_id]
          toColumns: [station_id]
          cardinality: many_to_one
          asOf: day_before
        - name: version_after
          to: station_version
          fromColumns: [station_id]
          toColumns: [station_id]
          cardinality: many_to_one
          asOf: event_date
```

`day_before` can be a column the source writes, or one the contract derives with `derive: day_before` and `expr: ADD_DAYS(event_date, -1)`. A `station_current` expose that repeats the current version declares one as-of relationship with `asOf: snapshot_date` and `sharedColumns: [sensor_model, status]`.

A summary (`aggregate`) into a versioned table is still refused. So is a path or a shared column that reads neither by entity nor as of a date.

#### What the exported rules read

The data rules are written in SQL for the expose's platform, in the [ODCS export](../cli/odcs.md#declared-invariants-as-quality-rules) and in [`fluid generate dbt-tests`](../cli/generate.md#declared-rules-as-dbt-tests). The two relationships above give these two rules on `reading`, written for the `local` binding (DuckDB). To show what each join reads, the tables below select the joined column beside each reading, from the join of the exported rule run in DuckDB. The rule itself returns the number of covered and violating rows. The `station_version` table holds two versions each of stations 1, 2 and 3. Station 2's second version has the status `DECOMMISSIONED`, and station 3's two versions hold different `network_id` values. Station 9 has no version.

```console
$ fluid generate standard contract.fluid.yaml --format odcs --out odcs-out/
✓ Wrote 2 ODCS v3.1.0 doc(s) to odcs-out/
```

```text
station.network_id
┌────────────┬────────────┬──────────────┬─────────────────┐
│ reading_id │ station_id │ reading_date │ read_network_id │
│   int32    │   int32    │     date     │      int32      │
├────────────┼────────────┼──────────────┼─────────────────┤
│          1 │          1 │ 2024-03-15   │              10 │
│          2 │          1 │ 2024-06-30   │              10 │
│          3 │          1 │ 2024-07-01   │              10 │
│          4 │          1 │ 2023-12-31   │              10 │
│          5 │          2 │ 2024-05-01   │              20 │
│          6 │          3 │ 2024-05-01   │            NULL │
│          7 │          9 │ 2024-05-01   │            NULL │
└────────────┴────────────┴──────────────┴─────────────────┘

station_on_date.sensor_model
┌────────────┬────────────┬──────────────┬───────────────────┐
│ reading_id │ station_id │ reading_date │ read_sensor_model │
│   int32    │   int32    │     date     │      varchar      │
├────────────┼────────────┼──────────────┼───────────────────┤
│          1 │          1 │ 2024-03-15   │ A                 │
│          2 │          1 │ 2024-06-30   │ A                 │
│          3 │          1 │ 2024-07-01   │ B                 │
│          4 │          1 │ 2023-12-31   │ NULL              │
│          5 │          2 │ 2024-05-01   │ A                 │
│          6 │          3 │ 2024-05-01   │ A                 │
│          7 │          9 │ 2024-05-01   │ NULL              │
└────────────┴────────────┴──────────────┴───────────────────┘
```

Station 1's first version ends on 2024-06-30 with sensor model `A`, and its open version starts on 2024-07-01 with `B`. Reading 2 is on the last day of the first version, so `chain: dayBefore` reads `A`. Reading 4 is before the station's first start, so it reads NULL. Station 3's two versions disagree on the network, so reading 6 reads NULL by entity, while the as-of read still reaches its version of 2024-05-01. Station 9 has no version.

The as-of read joins on the key and the interval. For `dayBefore` with `openEnd: "9999-12-31"`, the exported rule's join ends with:

```text
"l1"."valid_from" <= "t"."reading_date" AND ("l1"."fluid_next_start" IS NULL OR "t"."reading_date" < "l1"."fluid_next_start") AND ("l1"."valid_to" = DATE '9999-12-31' OR "t"."reading_date" <= "l1"."valid_to")
```

Under the default window (`nextStart`, `openEnd: null`) the same join ends with `AND ("l1"."valid_to" IS NULL OR "t"."reading_date" < "l1"."valid_to")`.

An `openEnd` literal is written into the SQL for `DATE` windows. On a window of timestamps, a literal is exported as a `text` rule that says why, and `openEnd: null` still exports as SQL. The export logs this warning:

```text
2 declared rule(s) on expose 'maintenance_event' are exported as ODCS text rules, not executable quality rules (model_before, model_after): the open end '9999-12-31T00:00:00' of exposes[station_version] is not a date literal, and FLUID SQL/1 writes no other literal of the window's type. The declarations ride along under customProperties.fluidExtras. Run `fluid validate` on the contract, or bind the expose to a platform forge writes SQL for, to get sql rules.
```

The ODCS standard has no field for a window's conventions or for `asOf`. The export carries each expose's `semantics` unchanged under the `customProperties` entry named `fluidExtras`, in `exposes.<exposeId>.semantics`, for ODCS v3.1.0 and v3.2.0, and an import reads it back as written.

#### Examples of what `fluid validate` refuses

Each of these is an error:

```console
$ fluid validate contract.fluid.yaml
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.173s

Validation Errors:
==================
 1. exposes[reading].semantics.relationships[station].sharedColumns: station reads exposes[station_version], which declares a validity window, by entity, and sensor_model is not stable per entity, so its versions may disagree on the value to copy; declare the column stable per entity (a dependency from the natural key to it), or name an asOf column on the relationship

Validation Notes:
=================
...
```

That is `sensor_model` in the `station` relationship's `sharedColumns`. A FLUID SQL/1 path is refused with other words. For the check `station.sensor_model = sensor_model`:

```text
exposes[reading].contract.invariants[chk].check: station reads exposes[station_version], which declares a validity window, by entity, and sensor_model is not stable per entity, so its versions may disagree on it: declare the column stable per entity (a dependency from the natural key to it), or name an asOf column on the relationship (at character 1)
```

The others, each from a contract changed in one place:

| Change | Error |
|---|---|
| `asOf` on a relationship whose target declares no window | `exposes[reading].semantics.relationships[2].asOf: the target expose declares no validity window, so there is no version to pick. Declare validityParams on its time dimensions, or remove asOf.` |
| `asOf` on a relationship whose `toColumns` are not the natural entity (and no `sharedColumns` on it, which would be refused too) | `exposes[reading].semantics.relationships[1].asOf: toColumns must be exactly ['station_id'], the column of the natural entity 'station', since asOf picks one version of one natural key.` |
| `asOf` names a column that is not a date or time | `exposes[reading].semantics.relationships[1].asOf: 'temperature_c' is number, but asOf names the date or time to pick the version at. Name a date, timestamp or timestamptz column.` |
| `asOf` is a timestamp and the window is dates | `exposes[reading].semantics.relationships[1].asOf: 'reading_date' is timestamp, but the target's window columns are date. A date never meets a timestamp: name a column of the window's type.` |
| `openEnd` is not a literal of the end column's type | `exposes[station_version].semantics.dimensions[1].typeParams.validityParams.openEnd: 'never' is not a date literal, the type of 'valid_to'. Write a YYYY-MM-DD date.` |
| `chain: dayBefore` on timestamp columns | `exposes[station_version].semantics.dimensions[1].typeParams.validityParams.chain: dayBefore ends a version the day before the next starts, which takes date columns, but 'valid_from' and 'valid_to' are timestamp. Use chain: nextStart or none, or declare the columns as date.` |
| `lifecycle` on an entity that is not `natural` | `exposes[station_version].semantics.entities[1].lifecycle: the entity is 'unique', but a life cycle describes the versions of a natural key. Make it type: natural, or remove lifecycle.` |
| `lifecycle` on a `natural` entity of a model with no window | `exposes[reading].semantics.entities[1].lifecycle: the model declares no validityParams, so there are no versions for a life cycle to describe. Declare the validity window, or remove lifecycle.` |
| A `lifecycle` column that is not in `contract.schema` | `exposes[station_version].semantics.entities[0].lifecycle.endMarker.column: 'state' is not a column of exposes[station_version]. Name a column its contract.schema declares.` |
| `openEnd` or `chain` on the `isStart` dimension | `exposes[station_version].semantics.dimensions[0].typeParams.validityParams.chain: chain describes how a version ends, so it belongs on the isEnd dimension. Move it there, or remove it.` |
| A column with two sources, such as a `derive` on a column that `sharedColumns` already fills | `exposes[reading].contract.schema[sensor_model]: 2 sources: derive invariant model; sharedColumns of relationship station_on_date. ...` |

The four new members are fields of the 0.7.7 preview. A contract that declares `fluidVersion: "0.7.6"` and uses `lifecycle` fails with `exposes[0].semantics.entities[0]: 'lifecycle' (the life cycle of a versioned entity) is a field of the 0.7.7 preview schema: set the contract's fluidVersion to 0.7.7 to use it`. `openEnd` and `chain` sit inside `validityParams`, and `asOf` on a relationship, which the 0.7.6 schema already reports as preview fields.

### Names dbt MetricFlow holds once

*(since 0.31.0, [forge-cli #906](https://github.com/Agenticstiger/forge-cli/pull/906))*

`fluid validate` compares the names of entities and dimensions the way the
[dbt export](#dbt-metricflow) writes them: every character that is not a
letter, a digit or `_` becomes `_`. Two cases warn:

- **A dimension has the name of an entity or another dimension of its
  expose.** They share one namespace in a semantic model, so the export keeps
  the first, entities before dimensions, and drops the dimension.
- **A name is a dimension of one expose and an entity of another.** dbt gives
  a name one element type across the semantic models of a project, so
  `dbt parse` rejects the export whenever the project declares a metric.

Entities of one name in several exposes are how MetricFlow joins them, so
they do not warn. An `orders` expose with an entity and a dimension both named
`region`, next to a `stores` expose with a `region` dimension, gives:

```console
$ fluid validate contract.fluid.yaml
✅ Valid FLUID contract (schema v0.7.6)
⚠️  2 warning(s)
Validation completed in 0.023s

Validation Warnings:
====================
 1. exposes[orders].semantics.dimensions[0]: dimension 'region' and entity 'region' are one dbt MetricFlow name, 'region'. Entities and dimensions share one namespace in a semantic model, so the dbt export keeps entity 'region' and drops this dimension. Rename one of them.
 2. exposes[stores].semantics.dimensions[0]: the dbt MetricFlow name 'region' is a dimension of exposes[stores] and an entity of exposes[orders]. dbt MetricFlow gives a name one element type across the semantic models of a project, so `dbt parse` rejects the export whenever the project declares a metric. Rename one of them.
```

They are warnings, so `fluid validate --strict` fails on them.

## How each consumer reads the block

### MCP `query` tool

[`fluid mcp output-port serve`](../cli/mcp.md#consumer-fluid-mcp-output-port-serve)
binds one expose and offers `query` when its `semantics` declares a metric,
measure or dimension. A call names a `metric` or a `measure`, optional
`dimensions`, and optional equality `filters`; the compiler turns that into
SQL. The agent never writes SQL on this path (`query_sql`, which accepts free
SQL, is a separate tool that is off unless the server runs with `--allow-sql`).

What the compiler does, as of 0.18.1:

- **Identifiers are validated** before they are placed in the SQL, and filter
  values are passed as bound parameters, not literals.
- **A metric's `filter` is applied** as a `WHERE` predicate. A filter that does
  not pass the expression allowlist (MetricFlow Jinja such as a
  `Dimension(...)` template, for example) makes the call fail rather than run
  unfiltered.
- **Only `simple` metrics are answered.** A `derived` or `ratio` metric is
  refused:

  ```json
  {
    "error": "QueryValidationError",
    "tool": "query",
    "message": "Metric 'refund_rate' has type 'ratio'; Phase-1 query supports only 'simple' metrics. Use a measure directly or wait for Phase-2 derived/ratio support."
  }
  ```

  Query the underlying measures instead, or let dbt MetricFlow answer the
  metric.
- **On an expose with restricted or redacted columns, expressions are checked more strictly.** *(since 0.41.0, [forge-cli #1105](https://github.com/Agenticstiger/forge-cli/pull/1105))*
  On an expose with restricted columns, every dimension, measure, metric `filter` and filter key
  is evaluated over the columns `contract.schema` declares, less the restricted ones. On an expose
  with restricted or redacted columns, or with row filters, a subquery in one is refused. On an
  expose with `sensitivity: pii`, `phi` or `sensitive` columns, an expression that selects columns
  without naming them (`COLUMNS(...)`, `IDENTIFIER(...)`, a `*` that stands for columns, the table
  as a whole-row value) is refused, while `count(*)` and `count(DISTINCT email)` still run. See
  [Restricted columns on the query tools](../advanced/mcp.md#restricted-columns-on-the-query-tools).
- **Value-revealing aggregates over PII are redacted.** `min`, `max`, `median`
  and `percentile` over a column marked `sensitivity: pii` return a cell value,
  so their results are masked like a raw PII column. `count`,
  `count_distinct`, `sum` and `avg` stay visible. That does not make them safe
  over PII: an equality filter on a column that is not restricted can narrow a
  `sum` or `avg` to one row, and the aggregate is then that row's value. To keep
  a column out of query results, deny it to the caller with
  [`policy.authz.columnRestrictions`](./governance-policy.md#column-restrictions-policy-authz-columnrestrictions),
  which also rejects the column as a filter key.

Relationships (0.7.7 preview) are returned by the `describe` tool with the rest
of the `semantics` block. A relationship that declares `asOf` can be read by `query`:
name `<relationship>.<column>` as a dimension or a filter key, and the call reads
the version of the target valid on each row's `asOf` value. See
[Reading an as-of relationship through `query`](../advanced/mcp.md#reading-an-as-of-relationship-through-query).
*On forge-cli's `fix/row-filter-followups` branch ([forge-cli #1117](https://github.com/Agenticstiger/forge-cli/pull/1117)), not yet on `main` or in a release.*
A relationship without `asOf` is not joined, and a `query` over a type II
dimension of the served expose reads every version of a row.

Governance on this path (agent policy, row filters, authentication) is
described in [MCP Server → The contract is the policy](../advanced/mcp.md#the-contract-is-the-policy).

### dbt MetricFlow

For a contract whose build uses `engine: dbt`,
[`fluid generate transformation`](../cli/generate.md#fluid-generate-transformation)
adds a semantic layer to the dbt project it writes whenever an expose has a
`semantics` block. Adding a dbt build to the example contract:

```yaml
builds:
  - id: orders
    engine: dbt
    pattern: hybrid-reference
    repository: ./dbt_project
    properties:
      model: orders
```

```console
$ fluid generate transformation contract.fluid.yaml -q
Generated 6 files (dbt engine):

  dbt_project/dbt_project.yml
  dbt_project/profiles.yml
  dbt_project/models/
    metricflow_time_spine.sql
    semantic_models.yml
  dbt_project/models/marts/
    orders.sql
    schema.yml
```

```yaml
# dbt_project/models/semantic_models.yml (abridged)
semantic_models:
- name: orders
  model: ref('orders')
  description: One row per order.
  defaults:
    agg_time_dimension: order_date
  entities:
  - name: order
    type: primary
    expr: order_id
  ...
  measures:
  - name: revenue
    agg: sum
    expr: amount
  ...
metrics:
- name: completed_revenue
  label: completed_revenue
  type: simple
  type_params:
    measure: revenue
  filter: status = 'completed'
...
models:
- name: metricflow_time_spine
  description: Day-grain time spine required by the MetricFlow semantic layer.
  time_spine:
    standard_granularity_column: date_day
  ...
```

The mapping is mostly a rename (camelCase to snake_case, `aggParams` to
`agg_params`). The generator also fills in what MetricFlow requires and the
contract may leave out:

- **A primary entity.** When none is declared, one is derived from the
  expose's key column, then from the first `unique` entity, then from the first
  schema column. A model where none can be derived is skipped with a warning.
- **An aggregation time dimension.** Taken from `defaultAggTimeDimension`, else
  the first time dimension. When there is no time dimension at all, that
  model's measures and metrics are dropped and its entities and dimensions are
  still written.
- **A time granularity** of `day` when a time dimension declares none, and a
  `label` equal to the metric name.
- **A day-grain time spine**, `models/metricflow_time_spine.sql`, because
  `dbt parse` rejects a semantic layer without one.

A metric whose inputs are missing is skipped, and so is a second metric with a
name already used. The entities, dimensions and measures of one model share
one namespace: of two with one name, the generator keeps the first (entities,
then dimensions, then measures) and drops the other, and `fluid validate`
warns (see [Names dbt MetricFlow holds once](#names-dbt-metricflow-holds-once)).
A contract with no `semantics` block produces no `semantic_models.yml` at all.

*(since 0.31.0, [forge-cli #906](https://github.com/Agenticstiger/forge-cli/pull/906))* A collection that is not a list, such as
`entities: 5` in a contract nobody validated, is read as empty, with a
warning; the generator used to stop with a `TypeError`.

A dimension with `validityParams` (0.7.7 preview) is exported to dbt's
type II SCD shape. The two bounds become `validity_params` with `is_start` and
`is_end`, and the model gets `primary_entity:` naming the natural entity. For
`customer_history` above, the generated `semantic_models.yml` has:

```yaml
- name: customer_history
  model: ref('customer_history')
  primary_entity: customer
  entities:
  - name: customer
    type: natural
    expr: customer_id
  dimensions:
  - name: segment
    type: categorical
  - name: valid_from
    type: time
    type_params:
      time_granularity: day
      validity_params:
        is_start: true
  - name: valid_to
    type: time
    type_params:
      time_granularity: day
      validity_params:
        is_end: true
```

dbt rejects some elements beside a window, so the generator drops them with a
warning: primary and unique entities, and measures. It also drops a `natural`
entity that has no window, because dbt accepts one only beside a window.

*(since 0.41.0, [forge-cli #1099](https://github.com/Agenticstiger/forge-cli/pull/1099))* The semantic model of a window also carries the
window's conventions in `config.meta.snapshot_config`, in dbt's own snapshot
key names, for every window, including the one in the example above. Through
0.40.1 no model had a `snapshot_config`. For the `station_version` window of
[Versioned tables](#versioned-tables-window-conventions-and-as-of-reads), the
model starts like this on `main`:

```yaml
- name: station_version
  model: ref('station_version')
  config:
    meta:
      snapshot_config:
        unique_key: station_id
        snapshot_meta_column_names:
          dbt_valid_from: valid_from
          dbt_valid_to: valid_to
        dbt_valid_to_current: cast('9999-12-31' as date)
  primary_entity: station
```

| Key | From the contract |
|---|---|
| `unique_key` | The natural entity's column |
| `snapshot_meta_column_names` | `dbt_valid_from` and `dbt_valid_to` name the start and end columns. `dbt_is_deleted` names the column of a boolean `lifecycle.endMarker` whose `value` is `true` |
| `dbt_valid_to_current` | The `openEnd` literal, cast to the end column's type: `cast('9999-12-31' as date)` for a date column, `cast('9999-12-31T00:00:00' as timestamp)` for a timestamp column. A literal that is not an ISO date or timestamp matching the column's declared type is left out, with a warning |
| `hard_deletes` | `new_record`, for that boolean end marker |

That window has `openEnd: "9999-12-31"` and a string end marker, so the model has no `dbt_is_deleted` and no `hard_deletes`. With a boolean `is_deleted` column as the end marker (`value: true`), it also carries `dbt_is_deleted: is_deleted` under `snapshot_meta_column_names` and `hard_deletes: new_record`.

MetricFlow joins a window on `[start, end)`. A `chain` of `dayBefore` or `none` makes a version valid on `[start, end]`, so the generator logs a warning, because the end day of such a version reads no version in MetricFlow:

```text
semantic_models: expose 'station_version' declares chain 'dayBefore', so a closed version is valid on [start, end]; MetricFlow joins a window on [start, end), so the end day of a version reads no version there
```

Relationships are not exported. MetricFlow joins two semantic models by entity
name, so the foreign entity on `orders` and the entity of the same name on the
target are what it follows. When a one-column relationship has no such pair,
`fluid validate` warns (see the example above), so the contract and the dbt
project do not drift apart.

The `filter` is copied as written. MetricFlow expects filters written against
its own dimension references, so a plain SQL predicate that the MCP compiler
accepts may need rewriting before dbt's semantic layer will run it; the
generated project's parse check (`--dbt-validate`) is the place to find out.

### Importing from dbt

[`fluid import dbt`](../cli/import.md#importing-a-dbt-project) reads the
`semantic_models` and `metrics` from a dbt manifest into each matching
expose's `semantics`. What the contract schema cannot hold (window groupings,
cumulative and conversion metrics, `agg_params` on a contract older than the
0.7.6 preview) is listed in the import report rather than written.

With the 0.7.7 preview, the import also recovers what dbt holds for a type II
SCD and for joins:

- **`validity_params`** become `typeParams.validityParams` on the dimension.
- **Relationships** are derived from the entity graph. For each `foreign`
  entity, the import writes a `many_to_one` relationship to each expose of the
  same contract that holds a `primary`, `unique` or `natural` entity of that
  name, on the two entities' columns, as MetricFlow joins them.
- **What cannot be written is reported.** A target in another product (a split
  import) and an entity whose key is an expression, not a column, appear in the
  import report, because a relationship names an expose of its own contract and
  real columns.
- **The contract moves to `fluidVersion: 0.7.7`** only when it carries one of
  these fields. Every other imported contract keeps the stable version.

## The OSI sidecar

[`fluid forge data-model`](../forge-data-model.md) writes a `semantics` block on
each expose it generates and, next to the contract, a standalone
[Open Semantic Interchange (OSI)](https://github.com/open-semantic-interchange/OSI)
document for tools that read OSI directly:

```console
$ fluid forge data-model from-ddl --ddl orders.sql --source-type postgres \
    --deterministic --output orders.fluid.yaml
deterministic mode enabled; staged LLM calls are disabled
Validation passed (score=10)
Wrote OSI sidecar orders.fluid.yaml.semantics.osi.yaml
Wrote contract orders.fluid.yaml
Wrote logical sidecar orders.fluid.yaml.model.json
Wrote model document orders.fluid.yaml.model.md
```

```yaml
# orders.fluid.yaml.semantics.osi.yaml (abridged)
version: 0.1.1
semantic_model:
- name: orders
  description: Semantic model for orders
  ...
  datasets:
  - name: orders
    source: orders
    primary_key:
    - order_id
    fields:
    - name: order_id
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: order_id
  ...
```

- The sidecar is built from the forged logical model (`*.model.json`), not
  from the contract's `semantics` block. Editing `semantics` in the contract
  afterwards does not change it; re-forge to regenerate both.
- The OSI document's relationships are also written into the contract. With the
  0.7.7 preview, when both datasets of a relationship are exposes of the
  contract (the `flat` technique, one expose per dataset) and declare its
  columns, `fluid forge data-model` puts it on the from expose's
  `semantics.relationships` 1:1, composite keys included, and sets
  `fluidVersion: 0.7.7`. A contract with no relationship keeps the stable
  version.
- `--osi-sidecar-format json` writes `*.semantics.osi.json` instead. That is
  the form dbt Core 1.12 and later reads from a project's `OSI/` directory.
- As of 0.18.1 the sidecar is always written: `--emit-osi-sidecar` is on by
  default and the command has no flag that turns it off.

## Where `semantics` comes from

- **`fluid forge data-model`** writes one on the exposes it generates.
- **`fluid import dbt`** maps one from a manifest's semantic models.
- **You author it.** The `fluid init --quickstart` contract (the
  `customer-360` template) has no `semantics` block, so its exposes get no
  `query` tool and no `semantic_models.yml` until you add one.

## Related

- [MCP output port walkthrough](../walkthrough/mcp-output-port.md): serve an
  expose to an agent and call `query` end to end.
- [`fluid mcp`](../cli/mcp.md#the-agent-tools): the four agent tools and
  their arguments.
- [Forge Data Model](../forge-data-model.md): forge a contract, its logical
  model and the OSI sidecar.
- [Builds, exposes and bindings](./builds-exposes-bindings.md): where an expose
  sits in the contract.
