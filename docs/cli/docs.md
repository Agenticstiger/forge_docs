# `fluid docs`

Generate a static, browsable catalog of the contracts in a repository: one `index.html` that lists them, one page per contract, and an `index.json` with the same list as data. The output is plain files you can open from disk or publish on any static host.

## Syntax

```bash
fluid docs [--src DIR | --files GLOB] [--out DIR]
```

## Examples

Catalog every contract under `products/` into `docs/`:

```bash
fluid docs
```

```text
docs/
├── contract-gold-customer-analytics-360-v1.html
├── index.html
└── index.json
```

Choose the contracts with a glob and write somewhere else:

```bash
fluid docs --files 'products/*/contract.fluid.yaml' --out site/catalog
```

The result has the same three kinds of file, in `site/catalog/`.

Scan a different directory:

```bash
fluid docs --src services --out site/docs
```

## Options

| Option | Description |
| --- | --- |
| `--src` | Directory to scan recursively for root contracts. Default `products`. See [Which contracts are listed](#which-contracts-are-listed). |
| `--files` | A glob of contract files. When set it wins over `--src`; `**` is expanded. The glob follows symlinks. |
| `--out` | Output directory, created if it does not exist. Default `docs`. An empty `--out` is refused with `--out is empty: name the directory to write the catalog to`. |

`--src` and `--files` only choose which contracts go in. Both write the same output.

## Which contracts are listed

`--src` lists a product's **root contract** only: a file named
`contract.fluid.yaml`, `contract.fluid.yml` or `contract.fluid.json`. The
overlay `contract.fluid.prod.yaml` beside a contract is the environment's
patch, not a product, so it gets no page and no row.

The scan walks the tree instead of globbing it:

- A directory name with glob characters (`my [team] products`) is a
  directory name. Before 0.26.0 it silently gave an empty catalog.
- A symlinked directory is not followed, so two links to `.` no longer hang
  the run, and a link out of `--src` lists nothing outside it.
- A contract file that is a symlink is listed when the file it names is
  inside `--src` and is not already listed under its own path. One that leads
  out of `--src` is skipped.
- A hidden directory (one whose name starts with `.`) is skipped.

`--files` takes a glob, which does follow links, for a tree that needs them.

When nothing matches `--src` or `--files`, the command still exits `0` and
writes an `index.html` and an `index.json` with no contracts.

## What it writes

| File | Contents |
| --- | --- |
| `index.html` | A self-contained page: inline CSS, a small script, no external assets. It lists the contracts in a table with a search box that filters rows in the browser. |
| `contract-<slug>.html` | One page per contract: a metadata table, the exposed datasets, the upstream products it consumes, and a link back to the index. The slug is the contract `id` in lower case with runs of other characters turned into hyphens, so `gold.customer.analytics_360_v1` becomes `gold-customer-analytics-360-v1`. A slug is at most 100 characters; a longer id is cut and ends in a hash of the whole id. Two contracts with one id get a page each. |
| `index.json` | One object per contract, sorted by `id`. |

An `index.json` entry looks like this:

```json
{
  "path": "products/customer360/contract.fluid.yaml",
  "slug": "gold-customer-analytics-360-v1",
  "id": "gold.customer.analytics_360_v1",
  "name": "Customer 360 Analytics",
  "description": "Production-ready Customer 360 with RFM analysis, CLV, and churn prediction",
  "fluidVersion": "0.7.5",
  "kind": "DataProduct",
  "owner": {
    "team": "customer-analytics",
    "email": "customer-analytics@company.com"
  },
  "domain": "Customer Experience",
  "layer": "Gold",
  "productType": "CDP",
  "tags": [
    "customer-360",
    "rfm-analysis",
    "clv",
    "churn-prediction"
  ],
  "exposes_count": 2,
  "consumes_count": 3
}
```

## What each contract is read as

`fluid docs` reads each contract through the loader `fluid validate` uses, without an environment:

- **Fragments are resolved.** A root that lists its exposes as `$ref` pointers, as `fluid split` writes it, is read whole, so the page names the exposes by their `exposeId` and `exposes_count` counts the exposes, not the pointers. The YAML goes through the size and alias guard.
- **The 0.7.x shapes are read.** Columns come from `exposes[].contract.schema` (a legacy top-level `schema` still reads), Nullable follows `required` and PII follows `sensitivity`, `domain` and `tags` come from the top level or from `metadata`, and a `description` object renders its purpose, usage and limitations.
- **No overlay is applied.** The catalog describes the base contract. To catalog an environment's version, run [`fluid bundle`](./bundle.md) with `--env` and point `--files` at the bundled file.

## A contract that cannot be listed

One bad contract is a row in the catalog, not the end of the run.

**A contract that does not load** is a row with its error and no page. `index.html` shows the error in the row, and `index.json` has `"id": null` and an `error` field that starts with `not loaded:`. Before 0.26.0 the row linked to a page the run never wrote:

```json
{
  "path": "products/broken/contract.fluid.yaml",
  "id": null,
  "error": "not loaded: $ref target not found: nope.yaml (resolved to /work/products/broken/nope.yaml), at JSON pointer '/builds/0' in ..."
}
```

**A contract holding an odd value** is listed like the rest. A value of an unexpected type (an `id` that is a number, `tags: [1, 2]`, a YAML date or `!!set`, a non-finite float, an integer too long to print, `exposes: 5`, a column `sensitivity` that is a list, a string with a lone surrogate) used to stop the whole catalog with `docs_failed` and a bare Python message, or wrote an `index.json` that strict JSON parsers reject (`NaN`). Now an odd character is shown escaped, a set is written as a sorted list, a non-finite float or an over-long integer as text, and `index.json` is strict JSON with the key spelling json uses (`true`, `null`), as before. A value that cannot be listed at all is a row with an `error` that starts with `not listed:`.

## When a run fails

A failing run leaves the catalog the last run wrote, never a broken one. Every file is rendered and encoded first. Each is then written whole to a temporary file beside its target, and only when all are written are they moved in, pages before the index, so the index never links a page that is not there. A run that fails

- while rendering writes nothing;
- while writing keeps the previous catalog;
- while moving files in leaves no dead link.

A run that fails removes the directories it made itself, and a later run removes the temporary files a killed run left beside the catalog's files, once they are over an hour old. A symlink planted in `--out` is replaced, not written through.

Before 0.26.0, `index.html` was opened for writing before it was rendered and `index.json` was streamed into an open file, so a failed run could leave an empty `index.html` or a cut-off `index.json`, and an id of 242 characters or more made a page name the file system refused after the index already linked it.

## Notes

- Re-run it in CI after contracts change and publish the output directory; the files are plain static assets.
- For a summary of one product rather than a catalog of many, see [`fluid status`](./status.md).
