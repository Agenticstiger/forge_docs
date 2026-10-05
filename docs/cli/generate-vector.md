# `fluid generate vector`

Review-only emit of a **pgvector RAG target** from a FLUID contract. For every expose bound to `pgvector`, it compiles the `ai-embeddable` columns into an embeddings table + ANN index so the data product can be consumed directly by retrieval-augmented generation (RAG) / AI applications.

::: tip Stable since `0.12.0` (shipped as a preview in `0.11.0`)
The `fluid generate vector` command ships in **`v0.11.0`**. As of **`v0.12.0`**, schema `0.7.5`
is promoted to **stable** and is the default for untagged contracts — the `vectorConfig` binding
block is default-available and no longer needs an explicit `fluidVersion: "0.7.5"` opt-in pin.
(Contracts that pin an older `fluidVersion` must bump to `0.7.5+` to use it.) See
[Product types & the schema lifecycle](../data-products/product-type.md).
:::

## What it emits

`fluid generate vector <contract>` writes two review artifacts to the output directory:

| File | Contents |
|---|---|
| `embeddings.sql` | `CREATE EXTENSION IF NOT EXISTS vector`, a one-row-per-chunk embeddings table (`<expose>_embeddings`), and the ANN index. |
| `vector_manifest.json` | RAG provenance — the embedding model, dimensions, distance metric, source key, and the text columns being embedded. |

The embeddings table is one row per chunk. For the `kb_articles` expose of the `pgvector-rag-output-port` example, `embeddings.sql` is:

```sql
-- FLUID vector output port (pgvector) — generated, do not edit by hand.
-- product: knowledge.support.articles
CREATE EXTENSION IF NOT EXISTS vector;

-- expose: kb_articles  (embeddable column(s): title, body)
-- model: text-embedding-3-small  dimensions: 1536  metric: cosine
CREATE TABLE IF NOT EXISTS "kb_article_embeddings" (
    id bigserial PRIMARY KEY,
    source_key text,
    source_column text NOT NULL,
    content text NOT NULL,
    embedding vector(1536),
    embedding_model text,
    chunk_index integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS "kb_article_embeddings_embedding_idx"
    ON "kb_article_embeddings" USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

The command prints where it wrote and how to apply it:

```text
Wrote pgvector target: runtime/vector/embeddings.sql +
runtime/vector/vector_manifest.json  (1 expose(s), 2 embeddable column(s))

Review and apply the embeddings table with psql:
  psql <dsn> -f runtime/vector/embeddings.sql
```

Only columns labelled `ai-embeddable: "true"` (the label the [`ai_ready` agent](./agents.md) stamps) become embedding targets. A column without the label is not embedded: `locale` and `article_id` in the example are not.

## Syntax

```bash
fluid generate vector [contract] [--out DIR] [--env NAME]
```

| Option | Description |
|---|---|
| `contract` | Path to the FLUID contract file (`contract.fluid.yaml`). |
| `--out`, `-o DIR` | Output directory for `embeddings.sql` + `vector_manifest.json`. Default `runtime/vector`. |
| `--env NAME` | Environment overlay name (matches your contract's overlay block, e.g. `dev` / `staging` / `prod`). |

## The `vectorConfig` binding

Declare a `vector` expose bound to `pgvector`, and drive the DDL from `binding.vectorConfig`:

```yaml
fluidVersion: "0.7.5"          # stable since 0.12.0 — also the default for untagged contracts
# ...
exposes:
  - exposeId: kb_articles
    kind: vector
    binding:
      platform: pgvector
      format: pgvector_table
      location:
        database: rag
        schema: public
        table: kb_articles
      vectorConfig:
        dimensions: 1536                       # must match your embedding model
        embeddingModel: text-embedding-3-small
        vectorType: vector                     # pgvector column type
        indexType: hnsw                        # hnsw (default) | ivfflat | none
        distanceMetric: cosine                 # cosine (default) | l2 | inner_product | l1
        sourceKeyColumn: article_id            # FK back to the source row
        table: kb_article_embeddings           # embeddings table name
        hnsw:
          m: 16
          efConstruction: 64
```

| `vectorConfig` field | Meaning |
|---|---|
| `dimensions` | Vector width — must equal your embedding model's output dimension (e.g. `1536` for `text-embedding-3-small`). |
| `embeddingModel` | The model that produced the vectors; recorded in the manifest for provenance. |
| `indexType` | `hnsw` (default, best recall/speed), `ivfflat`, or `none` (exact scan). |
| `distanceMetric` | `cosine` (default) / `l2` / `inner_product` / `l1` — selects the pgvector operator class on the index (`vector_cosine_ops`, etc.). |
| `sourceKeyColumn` | Column that links each chunk back to its source row. |
| `hnsw` / `ivfflat` | Index-tuning knobs (`m`, `efConstruction` for HNSW; `lists` for IVFFlat). |

## Examples

```bash
# Emit the embeddings DDL + manifest for review
fluid generate vector contract.fluid.yaml

# Choose an output directory
fluid generate vector contract.fluid.yaml --out runtime/vector

# Per-environment overlay
fluid generate vector contract.fluid.yaml --env staging
```

Inspect `embeddings.sql` and `vector_manifest.json`, then run the SQL against your Postgres+pgvector instance and point your RAG pipeline at the resulting table.

## How it fits

- **Upstream:** the [`ai_ready` agent](./agents.md) stamps `ai-embeddable: "true"` on safe free-text columns during authoring. This port reads those labels.
- **Identifiers:** every emitted table / index / column name is routed through FLUID's central SQL-identifier validation before interpolation — no raw string concatenation into DDL.
- **Prior art:** the DDL grammar follows the [pgvector](https://github.com/pgvector/pgvector) README; the `(model, dimensions, embed-fields)` config surface mirrors established embedding-sink connectors.

## See also

- [`fluid generate`](./generate.md) — the parent command and its other targets.
- [Builds, exposes & bindings](../concepts/builds-exposes-bindings.md) — how output ports are declared.
- [Consuming a data product](../data-products/consume.md).
