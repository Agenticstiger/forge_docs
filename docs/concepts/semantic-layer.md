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
- **Value-revealing aggregates over PII are redacted.** `min`, `max`, `median`
  and `percentile` over a column marked `sensitivity: pii` return a cell value,
  so their results are masked like a raw PII column. `count`,
  `count_distinct`, `sum` and `avg` stay visible. That does not make them safe
  over PII: an equality filter on a column that is not restricted can narrow a
  `sum` or `avg` to one row, and the aggregate is then that row's value. To keep
  a column out of query results, deny it to the caller with
  [`policy.authz.columnRestrictions`](./governance-policy.md#column-restrictions-policy-authz-columnrestrictions),
  which also rejects the column as a filter key.

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
name already used. A contract with no `semantics` block produces no
`semantic_models.yml` at all.

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
- [`fluid mcp`](../cli/mcp.md#the-four-agent-tools): the four agent tools and
  their arguments.
- [Forge Data Model](../forge-data-model.md): forge a contract, its logical
  model and the OSI sidecar.
- [Builds, exposes and bindings](./builds-exposes-bindings.md): where an expose
  sits in the contract.
