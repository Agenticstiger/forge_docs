# Network Safety

The CLI's remote fetches are conservative: fetching remote contract content is off unless you opt in, and the HTTP client the main fetch surfaces share (`fluid_build.util.safe_http`) checks the address at the connection layer, so DNS rebinding and IPv4-mapped IPv6 tricks cannot sneak past it.

This page describes the user-visible behaviour: which flags opt in, which environment variables allow hosts, where the defaults landed, and which older behaviours changed.

## Defaults that changed in v0.8.3


| Surface | Old default | New default | Override |
|---|---|---|---|
| `fluid forge --seed-from <url>` | (did not exist) | Local only; remote `http(s)` references are rejected | `--seed-allow-remote` |
| `fluid odps import <url>` | Followed `http(s)` `contractId` references | Local only; remote references are rejected | `--allow-remote` |
| `BitolOdpsProvider().import_contract(...)` (Python) | `allow_remote=True` | `allow_remote=False` | `allow_remote=True` (keyword) |
| `ContractResolver(...)` (Python) | `allow_remote=True` | `allow_remote=False` | `allow_remote=True` (keyword) |
| Ollama endpoint | Configurable | Localhost only | None, by design |
| HTTP redirects on a safe-HTTP client | Followed | Not followed | `follow_redirects=True` (per client) |

The CLI flags `--no-remote` and `--seed-no-remote` remain as hidden aliases that do nothing, so older scripts keep working.

## What the safe-HTTP client enforces

The client applies these, in order:

1. **Scheme allowlist.** Only `http` and `https`. `file://`, `gopher://` and the rest are refused.
2. **Post-DNS private-address filter.** Private (RFC 1918), loopback, link-local (`169.254.0.0/16`), multicast, reserved and unspecified addresses, plus carrier-grade NAT, 6to4, NAT64, ORCHIDv2, IPv6 segment routing and the RFC test ranges. IPv4-mapped IPv6 addresses are unwrapped before the check, which closes a bypass that Python before 3.12 had.
3. **Reject mixed DNS answers.** If a hostname resolves to any non-public address, the fetch is refused, so a public A record cannot hide a private AAAA record.
4. **Connection-layer DNS pin.** The validated IP is the one the connection uses (through httpx's `sni_hostname` extension), so a second lookup cannot send the request to a private address. The hostname is kept for TLS and the `Host` header.
5. **No redirects by default.** `follow_redirects=False`; a client has to opt in.
6. **Size cap.** `fetch_bytes` reads the body as a stream and stops at 10 MiB.

These surfaces use that client: the ODPS contract resolver, the Kafka Connect and schema-registry clients, the Airbyte runner, the DataHub, OpenMetadata and Data Mesh Manager registrars, the OpenLineage emitter, the federation fetcher, the schema manager's remote fetch, the forge web tools, and an authentication provider's API check. Other outbound calls do not: LLM provider requests go to the provider's endpoint, `fluid apply --ensure-opentofu` downloads OpenTofu, and the Command Center client and the webhook alerter apply their own host check, described next.

## Allowlists for outbound integrations

A few integrations need to call hosts that the private-address filter would refuse, such as an internal webhook receiver or a self-hosted registry. Use the matching allowlist variable:

| Variable | Surface |
|---|---|
| `FLUID_WEBHOOK_HOST_ALLOWLIST` | The build webhook alerter |
| `FLUID_FEDERATION_HOST_ALLOWLIST` | The federation digest fetcher |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | The Command Center client: detection, the observability reporter and `fluid apply` run reports. Loopback hosts are always allowed |
| `FLUID_OPENLINEAGE_ALLOW_PRIVATE` | The OpenLineage emitter. It allows private addresses by default because lineage receivers are usually internal; `false` restores the public-only check. Link-local and metadata addresses stay blocked either way |

The first three take comma-separated host suffixes, matched exactly or as a dotted suffix: `vpn.internal` permits `app.vpn.internal` but not `vpn.internal-evil.example.com`. A host on the list skips the address check.

## Cloud metadata and the credential resolver

`FLUID_ALLOW_METADATA_SERVICE=1` lets the metadata-source [credential resolver](./credential-resolver.md) fall back to cloud workload identity. It is off by default, and it is not an SSRF switch: it does not relax the checks above.

As of 0.18.1, nothing in the CLI reads `FLUID_SAFE_MODE` or acts on the global `--safe-mode` flag to refuse network calls.

## Ollama is localhost only

The Ollama provider uses `http://localhost:11434` unless `OLLAMA_HOST` names another localhost URL. An `OLLAMA_HOST` that points elsewhere is ignored with a warning, and the default is used. You cannot point `fluid forge --llm-provider ollama` at a remote Ollama instance this way. For a remote model, use a hosted provider (OpenAI, Anthropic, Gemini, Bedrock or Vertex).

## Contract SQL and `$ref`

Two 0.18.0 changes close network and file reads that a contract could previously trigger:

- SQL in a contract runs in a DuckDB sandbox: it cannot read `http(s)://`, `gs://` or Azure URLs, and reaches only declared `s3://` locations. See [DuckDB sandbox](./duckdb-sandbox.md).
- A `$ref` may only name a file inside the contract's directory tree. URL refs, `file://` refs and absolute paths are refused. See [Composing a contract with `$ref`](../concepts/contract-refs.md).

## How a denied fetch surfaces

A refusal by the safe-HTTP client is an `UnsafeURLError`, a `ValueError` subclass. Its message says why, and each address refusal also logs a `ssrf_guard_blocked` warning with the host and address:

- `refusing non-http(s) scheme: 'file'`
- `refusing fetch from non-public address <address> (hostname '<host>')`: the DNS answer is private, loopback, link-local or reserved, including the mixed-answer case.
- `cannot resolve hostname '<host>'`
- `response from '<url>' exceeds <n> bytes`: the body cap.

A redirect is not an error: the client returns the 3xx response and does not follow it. The webhook alerter raises `WebhookSsrfError` and the federation fetcher raises `FederationSsrfError` for the same address refusals, and each message names its allowlist variable.

## Import contracts

`pyproject.toml` declares [import-linter](https://pypi.org/project/import-linter/) contracts that keep this layer reusable: the observability package must not import the build runners, and `fluid_build._net`, which holds the shared address check, must not import other `fluid_build` packages. They are checked in development with `lint-imports`, not at run time.

```bash
pip install import-linter
lint-imports
```

## See also

- [Environment variables](./environment-variables.md): the variables above in one place
- [`fluid forge`](../cli/forge.md#remote-seeds-—-opt-in-to-http-s-fetch): where `--seed-allow-remote` applies
- [`fluid odps import`](../cli/odps-bitol.md#unified-fluid-odps-since-v0-8-3): where `--allow-remote` applies
- [Catalog overview](../cli/catalogs/overview.md): the publish-side registrars
