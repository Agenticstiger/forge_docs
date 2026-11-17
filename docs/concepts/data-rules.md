---
title: Rules about valid data
description: Declare in the contract what valid data looks like (derived columns, checks, dependencies, identifier formats, placeholders and shared attributes) in one SQL subset that every consumer reads alike.
---

# Rules about valid data

*On forge-cli `main`, not yet in a release ([forge-cli #911](https://github.com/Agenticstiger/forge-cli/pull/911)).*

The fields on this page need `fluidVersion: 0.7.7`. That schema is an opt-in preview: a contract that does not declare it stays on 0.7.6. A 0.7.6 contract that uses one of these fields fails `fluid validate`, and the message tells you to declare 0.7.7. Every field is optional, so a contract without them validates, exports and digests exactly as before.

## Why

Some of what makes data valid is more than a type. A gross amount follows from the net amount and the tax rate. A due date comes after the issue date. An age follows from a birth date. A group id determines its name. An identifier has the format its source system gives it.

Until now the contract had two places for such a rule, and neither fits:

- `contract.quality[]` holds a free SQL check in the warehouse's dialect. It is exported to ODCS, but nothing says which column the check determines, and FLUX, the synthetic-data engine that reads FLUID contracts, never reads it.
- `validationRules` with `type: regex` can check an identifier, but a regex cannot be enumerated, so a generator cannot produce unique values from it.

The fields here put the rules in the contract, in one small language, so that dbt, ODCS and FLUX consumers all read the same rule and reach the same verdict on the same row. `contract.quality[]` keeps its meaning: it is where a check that needs SQL outside this language belongs.

| What you declare | Where | Section |
| --- | --- | --- |
| Checks, derived columns, summaries over child rows, functional dependencies | `exposes[].contract.invariants[]` | [Invariants](#invariants) |
| The SQL subset those texts are written in | `check`, `expr`, `when`, `aggregate.filter` | [FLUID SQL/1](#fluid-sql-1) |
| Identifier formats | `exposes[].contract.schema[].identifierFormat[]` | [Identifier formats](#identifier-formats) |
| Placeholder values | `exposes[].contract.schema[].placeholders` | [Placeholders](#placeholders) |
| Attributes that two tables carry | `semantics.relationships[].sharedColumns[]`, `schema[].sharedAttribute` | [Shared attributes](#shared-attributes) |

## Invariants

An invariant is one rule about the rows of one expose. It has an `id` and exactly one of four forms.

| Form | Written as | Says |
| --- | --- | --- |
| Check | `check` | This predicate holds on every covered row. |
| Derive from an expression | `derive` and `expr` | This column equals this expression of the row. |
| Derive from child rows | `derive` and `aggregate` | This column equals a summary of the rows of another expose that point here. |
| Dependency | `dependency` | Equal values in the `from` columns mean equal values in the `to` columns. |

This contract uses all four. It is valid as written: run it with `fluid validate contract.fluid.yaml --offline`. It also prints two warnings about MetricFlow entity pairs for its relationships, which have nothing to do with these rules.

```yaml
fluidVersion: 0.7.7
kind: DataProduct
id: gold.billing.invoices
name: Invoices
metadata:
  layer: Gold
  owner:
    team: billing-platform
exposes:
  - exposeId: invoices
    kind: table
    binding:
      platform: snowflake
      format: snowflake_table
      location: {database: BILLING, schema: CDP, table: INVOICES}
    contract:
      schema:
        - {name: invoice_id, type: string, required: true}
        - {name: contract_id, type: string}
        - {name: net, type: "decimal(12,2)"}
        - {name: tax_rate, type: "decimal(5,4)"}
        - {name: gross, type: "decimal(12,2)"}
        - {name: billed_base_fee, type: "decimal(12,2)"}
        - {name: issue_date, type: date}
        - {name: due_date, type: date}
        - {name: group_id, type: string}
        - {name: group_name, type: string}
      invariants:
        - id: gross_from_net
          derive: gross
          expr: "ROUND(net * (1 + tax_rate), 2)"
        - id: due_after_issue
          check: "issue_date <= due_date"
          mustBeLessOrEqualTo: 0.5
          unit: percent
        - id: billed_base_fee_from_lines
          derive: billed_base_fee
          aggregate:
            function: sum
            column: amount
            from: invoice_lines
            via: invoice
            filter: "kind = 'base_fee'"
            ifNone: 0
        - id: base_fee_is_monthly_fee
          check: "billed_base_fee = contract.monthly_fee"
        - id: group_name_by_id
          dependency: {from: [group_id], to: [group_name], bothWays: true}
    semantics:
      relationships:
        - {name: contract, to: contracts, fromColumns: [contract_id], toColumns: [contract_id], cardinality: many_to_one}

  - exposeId: invoice_lines
    kind: table
    binding:
      platform: snowflake
      format: snowflake_table
      location: {database: BILLING, schema: CDP, table: INVOICE_LINES}
    contract:
      schema:
        - {name: line_id, type: string, required: true}
        - {name: invoice_id, type: string}
        - name: kind
          type: string
          validationRules:
            - {type: enum, constraint: "base_fee,usage"}
        - {name: amount, type: "decimal(12,2)"}
    semantics:
      relationships:
        - {name: invoice, to: invoices, fromColumns: [invoice_id], toColumns: [invoice_id], cardinality: many_to_one}

  - exposeId: contracts
    kind: table
    binding:
      platform: snowflake
      format: snowflake_table
      location: {database: BILLING, schema: CDP, table: CONTRACTS}
    contract:
      schema:
        - {name: contract_id, type: string, required: true}
        - {name: monthly_fee, type: "decimal(12,2)"}
```

An `id` matches `^[A-Za-z][A-Za-z0-9_]*$` and is unique within the contract: across all exposes, and against every `dq.rules[].id` and `contract.quality[].rule`. Reports, tests and exported rules name the rule by it.

| Key | Meaning |
| --- | --- |
| `check` | A FLUID SQL/1 predicate over the row. |
| `derive` | The column the invariant determines, with exactly one of `expr` and `aggregate`. |
| `expr` | The column's value, a FLUID SQL/1 expression over the row. |
| `aggregate` | The column's value as a summary over child rows. `function` is `count`, `sum`, `min` or `max`. `from` is the child expose, and `via` is a relationship that the child declares and that points back here. `column` is the child column to summarize: `count` takes none, `sum` needs a number of bounded scale (an integer or `decimal(p, s)` column), and `min` and `max` a number, string, date or timestamp. `filter` keeps only the children for which a predicate is true. `ifNone` replaces a NULL summary, as `COALESCE` would, and has the summary's type (a number, a string, or a date as `YYYY-MM-DD`). Without `ifNone`, SQL's rules apply: `sum`, `min` and `max` of nothing are NULL, and `count` is 0. |
| `dependency` | `{from, to, bothWays}`. `bothWays: true` adds the reverse direction and takes one column on each side. |
| `when` | A predicate that selects the rows the invariant covers. Not accepted on a `dependency`. |
| `severity` | `error` (the default), `warning` or `info`, the words `contract.quality[]` uses. |
| `description` | Prose. |

A summary is declared on the parent expose, as a structure and not as an aggregate written inside an expression. A path such as `contract.monthly_fee` reads a column of the row that a relationship reaches.

### Which rows an invariant covers

A row is covered when `when` is true. Without `when`, every row is covered. A row on which a compared value is NULL is still covered, and it usually violates the rule. Write `when: "first_use_date IS NOT NULL"` to leave such rows out.

Several `derive` invariants may determine one column. Each but the last needs a `when`: a derive without one covers every remaining row, so a derive after it covers none and is an error. A row is covered by the first one, in declaration order, whose `when` holds, as in SQL's `CASE WHEN`. A row that none covers takes the column's other source. In this example, Swiss orders ship for a flat fee and every other order pays 5 percent of the net:

```yaml
      invariants:
        - id: shipping_by_country
          derive: shipping_fee
          expr: "10.00"
          when: "country = 'CH'"
        - id: shipping_default
          derive: shipping_fee
          expr: "ROUND(net * 0.05, 2)"
```

A path through a relationship whose foreign key is NULL, or matches no row, gives NULL for every column it reads. A path, a summary or a shared attribute never goes through a relationship whose target declares a validity window, and `fluid validate` reports that as an error. See [Relationships and validity windows](./semantic-layer.md#relationships-and-validity-windows-need-the-0-7-7-preview).

### How many violations are allowed

By default an invariant holds only when no covered row violates it. To allow a share of violations, write one ODCS operator and a `unit`. The operator is one of `mustBe`, `mustBeLessThan`, `mustBeLessOrEqualTo`, `mustBeGreaterThan`, `mustBeGreaterOrEqualTo` or `mustBeBetween: [lo, hi]`. The band is on the number of violating rows.

| Operator | The invariant holds when the violating rows are |
| --- | --- |
| `mustBe: n` | exactly n |
| `mustBeLessThan: n`, `mustBeLessOrEqualTo: n` | fewer than n, or at most n |
| `mustBeGreaterThan: n`, `mustBeGreaterOrEqualTo: n` | more than n, or at least n |
| `mustBeBetween: [lo, hi]` | from lo to hi, both included, with lo below hi |

- At most one operator per invariant. Without one, the invariant means `mustBe: 0`. ODCS's `mustNotBe` and `mustNotBeBetween` are not accepted, because neither describes a band to generate within.
- `unit: rows` is the default and counts rows. `unit: percent` is violating rows times 100 divided by covered rows, and 0 when no row is covered.
- A number is an exact decimal with at most 15 significant digits. `0.5` is one half, not the nearest binary double.
- "Holds on about 98 percent of real rows" is `mustBeBetween: [1.5, 2.5]` with `unit: percent`.

The band is a rule. A measured share is a statistic and does not belong in the contract.

### What counts as a violation

| Form | A covered row violates the invariant when |
| --- | --- |
| `check` | The predicate is not TRUE. The language is two-valued, so a NULL comparison is FALSE. |
| `derive` with `expr` | The column `IS DISTINCT FROM` the value. A NULL value and a NULL column agree. |
| `derive` with `aggregate` | The parent's column `IS DISTINCT FROM` the summary over its children. |
| `dependency` | The row does not carry its key's most common `to` value. |

For a dependency, the violating rows of one key are its covered rows minus the rows that carry its most common `to` value. A NULL in a `to` column counts as a value. This is the g3 measure from the approximate-dependency literature: the fewest rows to remove so that the dependency holds. With `bothWays`, the forward and the reverse dependency are counted separately, and each count must meet the band. A row with a NULL in a `from` column is not covered.

## FLUID SQL/1

The texts in `check`, `expr`, `when` and `aggregate.filter` are written in FLUID SQL/1. It is a closed subset of SQL: a text outside it is a validation error, not an extension point. It is closed so that every consumer gives the same verdict on the same row. The `fluidVersion` names the version, so 0.7.7 carries FLUID SQL/1, and there is no language key.

What is in it:

| Group | Members |
| --- | --- |
| Operators | `+ - * /`, unary `-`, `= <> != < <= > >=`, `AND`, `OR`, `NOT`, `IN`, `NOT IN`, `BETWEEN`, `NOT BETWEEN`, `IS [NOT] NULL`, `IS [NOT] DISTINCT FROM` |
| Functions | `ROUND(x, s)`, `ROUND(x, s, 'HALF_TO_EVEN')`, `COALESCE(a, b, ...)`, `DAYS_BETWEEN(a, b)`, `MONTHS_BETWEEN(a, b)`, `YEARS_BETWEEN(a, b)` |
| Conditionals | Searched `CASE WHEN c THEN v ... [ELSE v] END` |
| Literals | Numbers (`3`, `1.50`), strings (`'base_fee'`), `TRUE`, `FALSE`, `NULL`, `DATE '2026-11-16'` |
| Names | A column of the row, or `relationship.column` for a column of the row that one relationship reaches |

A path crosses one link. A path over several links is not in the subset; `sharedAttribute` covers the common case across tables.

This contract fragment uses several of them. It is valid as written, in a contract that declares the columns it names:

```yaml
      invariants:
        - id: tier_from_net
          derive: tier
          expr: "CASE WHEN net >= 1000 THEN 'gold' WHEN net >= 100 THEN 'silver' ELSE 'basic' END"
        - id: age_as_of_2026
          derive: age_days
          expr: "DAYS_BETWEEN(order_date, DATE '2026-11-16')"
        - id: rounded_to_even
          derive: "Net Amount"
          expr: "ROUND(net * (1 - COALESCE(discount_rate, 0)), 2, 'HALF_TO_EVEN')"
```

### Names

Keywords and function names are case-insensitive. A column name is case-sensitive and is spelled exactly as in `contract.schema[].name`. Double-quote a name that is a keyword (`"end"`) or that does not match `[A-Za-z_][A-Za-z0-9_]*` (`"Net Amount"`), and write `""` for a quote inside it. Function names are not keywords, so a column may be called `round`. A string literal compared with a column that has an `enum` rule, or listed in an `IN` against one, must be one of its values or placeholders: `kind = 'other'` is an error when the enum is `base_fee,usage`.

The text has no `;`, and `--` and `/*` are refused outside a string, because SQL reads them as comments. A text is at most 4,096 code points long after NFC normalization, and so is its canonical form (which adds a space after each comma). It nests at most 64 levels deep: every operator, `NOT`, minus sign, call, `CASE` and pair of parentheses is one level, so a chain of 64 `AND`s is too deep.

### Two-valued truth

FLUID SQL/1 has no "unknown". Every predicate is TRUE or FALSE. A comparison with a NULL operand is FALSE, and so is `IN` and `NOT IN` with a NULL on the left. That makes a row's verdict the same in every engine. It also means two spellings that SQL treats alike differ here, and only on NULL:

| Written | When `a` is NULL |
| --- | --- |
| `a <> b` | FALSE |
| `NOT (a = b)` | TRUE |
| `x NOT IN ('XX', 'YY')` | FALSE |
| `NOT x IN ('XX', 'YY')` | TRUE |

For a null-safe comparison, write `a IS NOT DISTINCT FROM b`. The `NULL` literal itself is refused as an operand of a comparison, because the comparison would always be FALSE. The validator points you to `IS NULL`.

### Exact numbers and scales

Every number is exact. `+`, `-` and `*` are exact, and `/` gives the exact quotient, so `1 / 3` is one third. `x / 0` is NULL, so evaluation never raises.

Every number also has a scale: a literal has its written scale, a column its declared scale, `+` and `-` take the larger, `*` takes the sum, and `/` is unbounded. A derived value has to fit its column. If its scale is larger than the column's, `fluid validate` fails and says to wrap it in `ROUND(x, 2)`. Without that, `net * (1 + tax_rate)` has scale 6 and cannot fill a `decimal(12,2)` column.

`ROUND(x, s)` rounds ties away from zero, as warehouses round fixed-point numbers: 2.5 becomes 3 and -2.5 becomes -3. `ROUND(x, s, 'HALF_TO_EVEN')` rounds ties to the even neighbor. `'HALF_AWAY_FROM_ZERO'` spells the default. `s` is an integer literal from 0 to 38, the widest `DECIMAL` scale.

A float column is read as the shortest decimal that converts back to the same double, and it cannot be the target of a `derive`.

### Dates

`DAYS_BETWEEN`, `MONTHS_BETWEEN` and `YEARS_BETWEEN` count whole units from the first date to the second, and the result is an exact integer. Age is `YEARS_BETWEEN(birth_date, snapshot_date)`. The as-of date is a column or a `DATE` literal. No function reads the clock.

::: warning MONTHS_BETWEEN is not DATEDIFF
`DATEDIFF`, `DATE_DIFF` and similar functions count the unit boundaries crossed. `DATEDIFF(month, '2026-01-31', '2026-02-01')` is 1, while `MONTHS_BETWEEN(DATE '2026-01-31', DATE '2026-02-01')` is 0. Oracle, Snowflake and Spark also have a `MONTHS_BETWEEN(d1, d2)` of their own that returns a fraction and takes its arguments the other way round. FLUID's functions are neither of those. The consumers render them from the parsed expression and never pass the name to an engine.
:::

A date never meets a timestamp in a comparison, because FLUID SQL/1 has no `CAST`.

### What is not in it

String functions and `LIKE`, regular expressions, `CAST`, timestamp literals, date arithmetic other than the differences, `ABS`, `LEAST`, `GREATEST`, `NULLIF`, parameters, the clock, aggregates and windows inside an expression, subqueries, and paths over several links. If a check needs one of these, move it to `contract.quality[]`, which keeps free SQL in the warehouse's dialect. `fluid validate` says so when it finds such a text in an invariant.

## Identifier formats

`identifierFormat` is a list of alternatives. A value has the format when it is one of an alternative's `prefixes`, followed by a string that its `mask` matches. Without `prefixes`, there is one empty prefix. Only string-family columns take a format.

A mask is written after COBOL picture strings:

| Symbol | Matches |
| --- | --- |
| `9` | A digit, 0 to 9. |
| `A` | An upper-case ASCII letter, A to Z. |
| `X` | An upper-case ASCII letter or a digit. |
| `\` | Makes the next character literal, so `\A` is the letter A. |
| any other printable ASCII character | Itself. |

A mask is 1 to 64 characters long and has at least one symbol. There are no repeat counts, so write `99999` and not `9(5)`. Prefixes are a separate list, so a prefix such as `ACC` needs no escaping. Lower-case letters work as literals, but there is no symbol for a variable lower-case letter; a `validationRules` regex covers that.

```yaml
        - name: tower_id
          type: string
          identifierFormat:
            - prefixes: [MSC, TWR]
              mask: "99999"
            - prefixes: ["LEGACY-"]
              mask: "A9-99AA"
```

Consumers get one anchored regex per column. This example compiles to:

```text
^((MSC|TWR)[0-9]{5}|LEGACY-[A-Z][0-9]-[0-9]{2}[A-Z]{2})$
```

Only groups, alternation, character ranges and counts appear, so the same text works as ECMA-262 (ODCS `logicalTypeOptions.pattern`), POSIX ERE, RE2 and Python. Python consumers match it with `re.fullmatch`.

A mask also says how many values exist: an alternative holds the number of prefixes, times 10 for each `9`, times 26 for each `A`, times 36 for each `X`. A generator can enumerate them and make every value unique.

- **No overlap.** Two alternatives may not accept the same value, because a value would not say which alternative made it. `fluid validate` reports the first value that both accept. Make the alternatives differ in a literal, or in length.
- **Uniqueness** comes from the column's key or unique flag, not from the format.
- **Regex rules.** A `validationRules` entry with `type: regex` and an `identifierFormat` both apply. `fluid validate` notes a column that declares both.
- **Foreign keys.** A column in a relationship's `fromColumns` carries the values of the matching `toColumns` column, so it has that column's format. It may repeat the format identically. A different one is an error, and so is a format on the foreign key when its target has none. The RFC also gives the foreign key the target's placeholders, so a copied placeholder is exempt on both sides; the checks that read values come with the dbt and ODCS steps.
- **Placeholders are exempt.** A placeholder value, described next, is not checked against the format.

## Placeholders

A placeholder is a value that stands in for a real value that is not known yet, such as `TBD_0042` in place of a product code.

```yaml
        - name: product_code
          type: string
          identifierFormat:
            - {prefixes: [P], mask: "99999"}
          placeholders:
            values: ["XXXXX"]
            prefixes: ["TBD_"]
            mustBeLessOrEqualTo: 1
            unit: percent
```

- A value is a placeholder when it equals one of `values` or starts with one of `prefixes`. Matching is exact and case-sensitive. NULL is never a placeholder.
- A placeholder is exempt from the column's own value checks: `identifierFormat`, `validationRules` and the column's enum. Everywhere else, in invariants, keys and relationships, it is an ordinary value.
- One operator and a `unit`, as in [How many violations are allowed](#how-many-violations-are-allowed), bound the number of placeholder rows. Without an operator, placeholders are declared but not bounded: consumers report them and do not fail on them.
- Only string-family columns take placeholders.

A placeholder is not a sentinel. A sentinel stands in for no value at all, such as `UNKNOWN` in place of NULL. Sentinels stay in a column's `quality[]` as ODCS `missingValues`. The same text should not be both.

## Shared attributes

Two tables sometimes carry one attribute, and names do not tell you which. `status` on accounts and `status` on contracts usually differ. The contract says it in one of two ways, and `fluid validate` never infers it from names.

**Through one link, `sharedColumns`.** List the columns on the relationship. Each listed column is in both exposes' schemas under the same name. On every row whose link reaches a target row, the column `IS NOT DISTINCT FROM` the target's. Rows whose foreign key is NULL or matches no row are not covered. The relationship's own key columns are not listed, because they agree by definition.

```yaml
    semantics:
      relationships:
        - {name: account, to: accounts, fromColumns: [account_id], toColumns: [account_id], cardinality: many_to_one, sharedColumns: [status]}
```

The entry is short for a `derive` invariant with `expr: "account.status"` and `when: "account.account_id IS NOT NULL"`, so a row whose link reaches no account is not covered. A lower share is written as that invariant, with its operator.

**Across several links, `sharedAttribute`.** Give the columns the same `sharedAttribute` name.

```yaml
        # on accounts
        - {name: segment, type: string, sharedAttribute: customer_segment}
        # on invoices, which reaches accounts through contracts
        - {name: customer_segment, type: string, sharedAttribute: customer_segment}
```

- The **owner** is the member that every other member reaches through relationships, following `to`, on exactly one path. Each hop is a relationship that its own expose declares.
- On every row of another member whose path reaches an owner row, the value agrees with the owner's. A broken path, a NULL foreign key or an orphan on any hop leaves the row uncovered.
- It is an error to have no owner, two candidates, two paths to the owner, one expose carrying the attribute twice, or members of different types.
- A name matches `^[A-Za-z][A-Za-z0-9_.]*$` and is local to the contract.
- `semanticType` keeps its meaning, a kind of value such as `email`. Two columns with the same `semanticType` are not one attribute.

**One source per column.** A column has at most one source among: the `derive` invariants on it (several with `when` count as one), the `to` side of a dependency, a `sharedColumns` entry, and membership of a `sharedAttribute` other than the owner. A column with two sources is an error that names both. A format is not a source: on a column that one of these fills, `identifierFormat` only checks the values.

## What `fluid validate` reports

`fluid validate` parses every text with its own parser, resolves every name, and checks types and scales. It reports two kinds of finding. Each has a JSON pointer to the field and the code `ERR_CONTRACT_DATA_RULES`. The pointer shows in `--format json`, in `issues[]`.

**Errors** fail validation. They include: an unknown name or a text outside FLUID SQL/1, a type or scale error, a string literal outside its column's enum, an id that another rule already uses, a band that does not fit (two operators, a percent over 100, a range whose ends are reversed), a format or placeholders on a column that is not a string, a cycle among derived columns, a column with two sources, overlapping masks, a foreign key whose format differs from its target's, a `sharedAttribute` with a missing or ambiguous owner, and a path through a relationship whose target has a validity window.

**Notes** never fail validation, and `--strict` does not count them. They are: same-named columns on the two ends of a relationship that nothing relates, a division or float arithmetic (exact here and approximate in engines), a column with both a format and a regex rule, and a `contract.quality[]` expression that could become an invariant.

These outputs are from the CLI on forge-cli `main`, run as `fluid validate contract.fluid.yaml --offline`. The first three start from a small contract with one `invoices` expose and one change, as stated. The overlap and note outputs come from small contracts of their own.

An accepted contract. Its one `invoices` expose declares `gross_from_net`, `due_after_issue` and `group_name_by_id`, and nothing is flagged:

```text
✅ Valid FLUID contract (schema v0.7.7)
Validation completed in 0.359s
```

A scale error. `gross_from_net` is written `expr: "net * (1 + tax_rate)"`, without `ROUND`:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.248s

Validation Errors:
==================
 1. exposes[invoices].contract.invariants[gross_from_net].expr: the value has scale 6 and gross has scale 2: wrap it in ROUND(x, 2)
```

The same finding in `--format json` carries the pointer and the code:

```text
      "severity": "error",
      "code": "ERR_CONTRACT_DATA_RULES",
      "pointer": "/exposes/0/contract/invariants/0/expr",
      "fix": "wrap the value in ROUND(x, s) with the column's scale",
```

SQL outside the subset. `gross_from_net` is written `expr: "UPPER(invoice_id)"`:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.309s

Validation Errors:
==================
 1. exposes[invoices].contract.invariants[gross_from_net].expr: not FLUID SQL/1 at character 1: UPPER(...) is not in FLUID SQL/1: FLUID SQL/1 has no string functions; SQL outside FLUID SQL/1 belongs in contract.quality[]
```

Overlapping alternatives. A `tower_id` column declares `{prefixes: [TWR], mask: "99999"}` and `{prefixes: [TWR], mask: "X9999"}`:

```text
❌ Invalid FLUID contract (1 error(s)) (schema v0.7.7)
Validation completed in 0.138s

Validation Errors:
==================
 1. exposes[towers].contract.schema[tower_id].identifierFormat: alternatives 0 and 1 overlap: 'TWR00000' has both formats, so a value would not say which alternative made it; make the alternatives differ in a literal, or in length
```

A note. Two exposes, `contracts` and `accounts`, both have a `status` column and a relationship between them, and nothing says whether it is one attribute. The result is valid and the exit code is 0:

```text
✅ Valid FLUID contract (schema v0.7.7)
Validation completed in 0.126s

Validation Notes:
=================
 1. exposes[contracts].semantics.relationships[account]: exposes[contracts] and exposes[accounts] both have status, and nothing says whether they are one attribute (names never decide it); list it in sharedColumns if the values agree through the link, or relate the two with an invariant
```

Adding `sharedColumns: [status]` to that relationship removes the note.

## What consumers do today

The declarations travel with the contract. What reads them in this version:

| Consumer | What it does |
| --- | --- |
| `fluid validate` | Runs the lint above. |
| ODCS export | Carries the declarations through `fluidExtras`, so FLUID to ODCS and back to FLUID loses none. See [ODCS](../cli/odcs.md). |
| dbt bridge | Output is unchanged. |
| MCP `describe` | Returns the invariants, formats, placeholders and shared attributes. See [`fluid mcp`](../cli/mcp.md). |
| Contract digest | Covers every field here, so changing a rule changes the digest. |

Two consumers come later: executable ODCS quality rules rendered from the invariants, and a dbt test (`fluid_rule`) for each one. Until they land, an invariant is declared and validated, but dbt does not yet run it against warehouse data.

## The conformance vectors

`fluid_build/fluid_sql/fluid-sql-vectors.json` ships in the forge-cli wheel. Each vector gives a text, its verdict (accepted, or refused with a reason), its syntax tree, its canonical text, its type and scale, and its value against given rows. forge-cli's validator runs the file, and DuckDB must agree with the SQL rendering of every accepted vector. flux-expr/2, the expression language of FLUX, runs the same file through its own parser. The vectors define the subset, and neither parser does.

## Where to look next

- [RFC: Rules about valid data](https://github.com/Agenticstiger/forge-cli/blob/main/RFC-data-rules.md): the full spec, including the grammar, the SQL renderings and the consumer matrix.
- [The semantic layer](./semantic-layer.md): relationships, and the validity windows that a path may not cross.
- [Quality, SLAs and lineage](./quality-sla-lineage.md): `dq.rules` and `contract.quality[]`, where checks in the warehouse's own SQL belong.
- [Fields that need a preview schema](../reference/preview-fields.md): which fields need a preview schema. To opt in to these, declare `fluidVersion: "0.7.7"`.
- [`fluid validate`](../cli/validate.md): the command and its flags.
