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
| `--src` | Directory to scan recursively for `contract.fluid.*` files. Default `products`. |
| `--files` | A glob of contract files. When set it wins over `--src`; `**` is expanded. |
| `--out` | Output directory, created if it does not exist. Default `docs`. |

`--src` and `--files` only choose which contracts go in. Both write the same output.

## What it writes

| File | Contents |
| --- | --- |
| `index.html` | A self-contained page: inline CSS, a small script, no external assets. It lists the contracts in a table with a search box that filters rows in the browser. |
| `contract-<slug>.html` | One page per contract: a metadata table, the exposed datasets, the upstream products it consumes, and a link back to the index. The slug is the contract `id` in lower case with runs of other characters turned into hyphens, so `gold.customer.analytics_360_v1` becomes `gold-customer-analytics-360-v1`. |
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
  "domain": null,
  "layer": "Gold",
  "productType": "CDP",
  "tags": null,
  "exposes_count": 2,
  "consumes_count": 3
}
```

## What it does not do

`fluid docs` reads each file as written, with a plain YAML or JSON parse. As of 0.18.1 that has four consequences:

- **No overlays and no `$ref`.** An environment overlay is not applied, and a fragment-first root contract is not resolved. For a root that lists its exposes as `$ref` pointers, the page shows the exposes as `expose-0`, `expose-1` instead of by name, and counts the pointers. To catalog a fragment-first product, run [`fluid bundle`](./bundle.md) first and point `--src` or `--files` at the bundled file.
- **Columns are read from `exposes[].schema`.** Contracts written by `fluid init`, and the 0.7.x schemas, put the columns under `exposes[].contract.schema`. For those contracts the drill-in page shows an empty schema table with the text `No schema columns defined.` even though the contract declares columns.
- **`domain` and `tags` come from `metadata`.** A contract that keeps `domain` at the top level, as `fluid init` writes it, gets `"domain": null` in `index.json`.
- **No match is not an error.** When nothing matches `--src` or `--files`, the command still exits `0` and writes an `index.html` and an `index.json` with no contracts.

A contract that cannot be parsed appears in `index.json` with `"id": null` and an `error` field and gets no page of its own.

## Notes

- Re-run it in CI after contracts change and publish the output directory; the files are plain static assets.
- For a summary of one product rather than a catalog of many, see [`fluid status`](./status.md).
