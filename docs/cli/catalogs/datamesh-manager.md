# Data Mesh Manager Catalog

Source-side catalog adapter for **Data Mesh Manager** (the SaaS data
product registry). Reads registered data products, their owners,
domains, contracts, lineage, and certifications via the DMM REST
API.

> **Recommended for:** organisations using Data Mesh Manager as
> their canonical data-product registry. Forge-cli reads existing
> DMM products and produces a Fluid contract that can be published
> back to DMM (closing the loop with the existing
> [DMM provider](../datamesh-manager.md) on the publish side).

## Install

**Already in core deps** — no optional extra needed. The adapter
uses `httpx` (already installed) over plain HTTPS to the DMM REST
API. No new SDK.

```bash
pip install data-product-forge   # default install is enough
```

## API key & permissions

The adapter is **read-only**. From the DMM UI:

1. Settings → API Keys → New API Key.
2. Scopes: tick **`dataproducts:read`** (and optionally
   **`lineage:read`**, **`glossary:read`**).
3. Copy the generated key (one-time display).

The DMM permission model is API-key-scoped, not role-based — the
key carries exactly the read scopes you ticked.

## Authentication methods

Single auth method: API key over HTTPS Bearer token. No OAuth
needed.

| Method | Setup |
|---|---|
| **`api_key`** ★ | API key from the DMM UI; sent as `Authorization: Bearer <key>` on every request. |

## Setup

```bash
fluid ai setup --source datamesh_manager --name dmm-prod
# ? Catalog: datamesh_manager
# ? Server URL: https://api.datamesh-manager.com
# ? API key: ******                  (stored in OS keyring)
# ✓ Saved to ~/.fluid/sources.yaml
```

Or env vars:

```bash
export DATAMESH_MANAGER_HOST=https://api.datamesh-manager.com
export DATAMESH_MANAGER_API_KEY=dmm-...
```

## End-to-end demo

```bash
fluid ai setup --source datamesh_manager --name dmm-prod

# Forge from all data products in a domain.
fluid forge data-model from-source \
  --source datamesh_manager \
  --credential-id dmm-prod \
  --database commerce \
  --technique dimensional \
  -o commerce.fluid.yaml
```

The DMM `database` parameter maps to the DMM `domain` query
parameter — the adapter forges every data product in the named
domain.

```bash
# Or scope to specific data products by ID.
fluid forge data-model from-source \
  --source datamesh_manager \
  --credential-id dmm-prod \
  --tables customer-orders product-catalog \
  -o orders.fluid.yaml
```

## What lands where

| DMM source | Forge output |
|---|---|
| Data product `name` / `description` | `OSIDataset` name / description |
| Data product `owner` | `metadata.owner.team` |
| Data product `domain` | `metadata.domain` + industry hint |
| Data product `status` (active / deprecated) | `metadata.lifecycle.status` |
| Data product contract | imported as starting point for the new contract (caller may override) |
| DMM lineage edges | `metadata.lineage.upstream[]` + DV2 link inference |
| DMM certifications | `metadata.certification` |

## Per-call HTTP lifecycle

The DMM adapter opens an `httpx.Client` per tool call and exits the
context manager after the response. This means **no MCP-server-
spanning connection state** — important when the adapter runs
inside a long-lived MCP server (`fluid mcp serve`) where pooled
connections could leak credentials between unrelated tool calls.

The pattern is documented in the adapter source (`Pattern 3 —
per-call client lifecycle`) and pinned by
`tests/copilot/catalog/test_catalog_adapter_dmm.py::TestPerCallClientLifecycle`.

## Common errors

### `CatalogPermissionError: 401`
API key invalid, expired, or missing the required scope. Generate
a new key from the DMM UI with `dataproducts:read` ticked.

### `CatalogConnectionError: 404`
404 means **resource not found**, not "auth issue" — the adapter
distinguishes 404 from 401 deliberately so the operator's next
action is "verify the URL or product ID", not "check API keys."

### `CatalogConnectionError: server unreachable`
Check the server URL doesn't have a trailing slash that creates a
double-slash (`https://api.datamesh-manager.com//dataproducts`),
or that you're not behind a corporate proxy that's blocking the
DMM domain.

## See also

- [Catalog index](README.md)
- [DMM provider page](../datamesh-manager.md) — for the
  publish-target side (write contracts BACK to DMM).
