# `fluid generate vector`

Review-only emit of a **pgvector RAG target** from a FLUID contract. For every expose bound to `pgvector`, it compiles the `ai-embeddable` columns into an embeddings table + ANN index so the data product can be consumed directly by retrieval-augmented generation (RAG) / AI applications.

::: tip Available in `0.11.0` — preview, opt-in under `fluidVersion: 0.7.5`
The `fluid generate vector` command ships in **`v0.11.0`**. The **vector / embeddings output
port** itself is a preview capability: the `vectorConfig` binding block is served and fully
validatable, but only when a contract explicitly declares `fluidVersion: "0.7.5"` — the schema
default stays on the current stable version, so existing contracts are untouched. `vectorConfig`
graduates to default-on when `0.7.5` is promoted to stable. See
[Product types & the schema lifecycle](../data-products/product-type.md).
:::

## What it emits

`fluid generate vector <contract>` writes two review artifacts to the output directory:

| File | Contents |
|---|---|
| `embeddings.sql` | `CREATE EXTENSION IF NOT EXISTS vector`, a one-row-per-chunk embeddings table (`<expose>_embeddings`), and the ANN index. |
| `vector_manifest.json` | RAG provenance — the embedding model, dimensions, distance metric, source key, and the text columns being embedded. |

The embeddings table follows the standard RAG shape:

```sql
CREATE TABLE kb_article_embeddings (
    id            bigserial PRIMARY KEY,
    source_id     bigint,              -- FK back to the source row (sourceKeyColumn)
    chunk_index   int,
    chunk_text    text,
    embedding     vector(1536),        -- dimensions from vectorConfig
    embedding_model text,
    created_at    timestamptz DEFAULT now()
);
CREATE INDEX kb_article_embeddings_embedding_idx
    ON kb_article_embeddings USING hnsw (embedding vector_cosine_ops);
```

Only columns the [`ai_ready` agent](./agents.md) labels `ai-embeddable: "true"` become embedding targets — every other column is skipped, so PII and structural columns never enter the vector store by accident.

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
fluidVersion: "0.7.5"          # opt into the preview schema
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

- **Upstream:** the [`ai_ready` agent](./agents.md) stamps `ai-embeddable: "true"` on safe free-text columns during authoring. This port consumes exactly those labels.
- **Identifiers:** every emitted table / index / column name is routed through FLUID's central SQL-identifier validation before interpolation — no raw string concatenation into DDL.
- **Prior art:** the DDL grammar follows the [pgvector](https://github.com/pgvector/pgvector) README; the `(model, dimensions, embed-fields)` config surface mirrors established embedding-sink connectors.

## See also

- [`fluid generate`](./generate.md) — the parent command and its other targets.
- [Builds, exposes & bindings](../concepts/builds-exposes-bindings.md) — how output ports are declared.
- [Consuming a data product](../data-products/consume.md).
