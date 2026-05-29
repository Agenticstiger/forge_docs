# Network Safety

`v0.8.6` consolidates every outbound HTTP fetch behind one safe-HTTP layer. The defaults are conservative — most remote operations are off unless you opt in — and the guard runs at the connection layer so that DNS rebinding and IPv4-mapped IPv6 tricks can't sneak past it.

This page describes the **user-visible behaviour**: which flags opt in, which env vars allowlist hosts, where the defaults landed, and which legacy behaviours flipped (the BREAKING ones, listed below).

## Defaults that flipped in v0.8.3 — what you may need to change

| Surface | Old default | New default | Override |
|---|---|---|---|
| `fluid forge --seed-from <url>` | (didn't exist) | Local-only; remote `http(s)` references rejected | `--seed-allow-remote` |
| `fluid opds import <url>` | Followed `http(s)` `contractId` references | Local-only; remote references rejected | `--allow-remote` |
| `BitolOdpsProvider().import_contract(...)` (Python) | `allow_remote=True` | `allow_remote=False` | `allow_remote=True` (kwarg) |
| `ContractResolver(...)` (Python) | `allow_remote=True` | `allow_remote=False` | `allow_remote=True` (kwarg) |
| `forge_copilot_seed.load_seed(...)` (Python) | `allow_remote=True` | `allow_remote=False` | `allow_remote=True` (kwarg) |
| Ollama endpoint | Configurable | Localhost-only (`127.0.0.1` / `::1`) | — (intentional) |
| HTTP redirects on any safe-HTTP client | Followed | Not followed | `follow_redirects=True` (per-call kwarg) |

The CLI flags `--no-remote` / `--seed-no-remote` remain as hidden no-op aliases for back-compat in scripts.

## What the safe-HTTP layer enforces

Every outbound `http(s)` call from `fluid` goes through one factory that applies, in order:

1. **Scheme allowlist** — only `http` and `https`. `file://`, `gopher://`, etc. are rejected.
2. **Post-DNS-resolution private-IP filter** — RFC1918, link-local `169.254.0.0/16`, loopback, reserved, CGNAT, 6to4, NAT64, ORCHIDv2, IPv6-SR, RFC-TEST-NET. IPv4-mapped IPv6 addresses are unwrapped before the check (closes a Python 3.10 / 3.11 stdlib bypass that didn't recurse into IPv4-mapped IPv6 until 3.12+).
3. **Reject on mixed-public-and-private DNS** — if a hostname resolves to both public and private addresses, the entire fetch is refused (the canonical DNS-rebinding mitigation).
4. **Connection-layer DNS pin** — the validated IP is pinned for the lifetime of the connection (httpx's `sni_hostname` extension). A second DNS lookup mid-connection can't redirect to a private IP.
5. **`follow_redirects=False`** — redirects are off by default; the caller has to opt in per request.
6. **Streaming body cap** at `10 MiB` — bounded memory exposure for unknown upstream payload sizes.

The same factory powers seven fetch surfaces in one pass: the contract resolver, the Kafka Connect REST client and its schema-registry client, the Airbyte REST client, the three publish-side catalog registrars (DataHub, OpenMetadata, Data Mesh Manager), the Databricks auth-provider's API check, and the schema-manager remote fetcher.

## Allowlists for outbound integrations

A handful of integrations need to call user-controlled hosts that the post-DNS filter would otherwise reject (e.g. an internal webhook receiver, a self-hosted catalog). Use the matching allowlist env var:

| Variable | Surface |
|---|---|
| `FLUID_WEBHOOK_HOST_ALLOWLIST` | Webhook alerter (`fluid_build/build_runners/_alerter.py`). Comma-separated host suffixes — `corp.example.com,vpn.internal`. |
| `FLUID_FEDERATION_HOST_ALLOWLIST` | Federation digests fetcher. |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | FLUID Command Center publish. |

Allowlists are **suffix matches** — `vpn.internal` permits `app.vpn.internal` but not `vpn.internal-evil.example.com`.

## Master toggles

| Variable | Effect |
|---|---|
| `FLUID_SAFE_MODE` | Master kill-switch. When set, every outbound HTTP fetch is refused — even those that would otherwise have gone through. Useful for air-gapped reviewers. |
| `FLUID_ALLOW_METADATA_SERVICE` | Allow outbound calls to the cloud metadata service (`169.254.169.254`). **Off by default.** Only enable on hosts that need IAM/role auto-discovery and have no untrusted workload sharing the network. |

## Ollama is localhost-only

The Ollama provider is restricted to `127.0.0.1` and `::1`. You cannot point `fluid forge --llm-provider ollama` at a remote Ollama instance — even via an SSH tunnel that terminates locally, the post-DNS filter accepts the local socket. If you need a remote LLM, use one of the SaaS providers (OpenAI / Anthropic / Gemini / Bedrock / Vertex) behind their first-party HTTP — those are not restricted by the SSRF guard, only filtered against the IPv4/IPv6 private-range list.

## How a denied fetch surfaces

Denied fetches raise a typed `NetworkSafetyError` with one of these reasons:

- `scheme_not_allowed` — non-`http(s)` URL.
- `private_address_blocked` — the DNS resolved to a private / loopback / link-local / reserved address.
- `mixed_dns_resolution` — the hostname resolves to a mix of public and private addresses; the fetch is refused without retry.
- `redirect_blocked` — the upstream responded with a 3xx and the caller did not opt in to redirects.
- `body_cap_exceeded` — the streaming download crossed the `10 MiB` cap.

Each error carries `what / where / why / fix / doc` fields per the [typed CLI errors](./typed-cli-errors.md) shape.

## Architecture contracts (enforced in CI)

`v0.8.3` adds two declarative `[tool.importlinter]` contracts in `pyproject.toml`:

1. **`observability ↛ build_runners`** — the observability layer cannot import the build-runner layer. Prevents the cycle that previously broke `cli/__init__.py` import.
2. **`_net` is tier-0** — the canonical post-DNS-resolution SSRF check module has no `fluid_build.*` upstreams. Makes the SSRF gate safely reusable from any layer.

These contracts are enforced by the upstream [`import-linter`](https://pypi.org/project/import-linter/) tool during development and in the `import-hygiene` CI job — they are **not** a runtime CLI feature. There is no `fluid lint-imports` subcommand. Contributors run them with:

```bash
pip install import-linter
lint-imports
```

## See also

- [Environment variables](./environment-variables.md) — full env-var index including the SSRF allowlists
- [`fluid forge`](../cli/forge.md#remote-seeds-opt-in-to-https-fetch) — where `--seed-allow-remote` applies
- [`fluid opds import`](../cli/odps-bitol.md#unified-fluid-opds-since-v0-8-3) — where `--allow-remote` applies
- [Catalog overview](../cli/catalogs/overview.md) — publish-side registrars all use the safe-HTTP layer
