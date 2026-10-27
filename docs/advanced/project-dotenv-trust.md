---
title: What a project's .env may set
description: A project's dotenv files may carry credentials but not settings that widen a sandbox, change trust, or change where data and credentials are sent — what is refused, what you see when it is, and where to set it instead.
---

# What a project's `.env` may set

A project's dotenv files travel with the project. Somebody other than the person running
`fluid` may have written them, and on a cloned repository usually did. They are meant to carry
credentials. They are not allowed to carry a setting that decides what the CLI may do.

::: tip Since `0.20.0`
Advisory B of the `0.20.0` security release
([GHSA-58px-v64p-6ppm](https://github.com/Agenticstiger/forge-cli/security/advisories/GHSA-58px-v64p-6ppm)).
Before it, a committed `.env` could widen the DuckDB sandbox, move where the CLI read trusted
configuration, or point one of your credentials at a host the project chose.
:::

## Which files, and in what order

`fluid apply` and `fluid publish` hydrate the project's dotenv files at start, from the
directory you run the command in; `fluid verify` does the same for the project root it
resolves, and every credential lookup reads them too. Later files win:

1. `.env`
2. `.env.<environment>` — the `--env` value, so `.env.prod` for `--env prod`
3. `.env.local`
4. `FLUID_SECRETS_FILE`, if you exported one, loaded last and over the process environment

Only the first three are *project* files, and only they are filtered. `FLUID_SECRETS_FILE` is
yours: the variable itself is operator-only, so a path a project file sets is ignored and the
file it names is never read.

Project values are read **literally**. `${VAR}` is not expanded, so a project file cannot copy
a value out of your environment into a name that is allowed to load.

Names are compared upper-cased, because Windows environment names are case-insensitive:
`https_proxy` is `HTTPS_PROXY`. The filter is by variable name and never by file name, so on a
case-insensitive filesystem `.Env` is filtered exactly as `.env` is.

## Credentials load. Settings do not

A project file may still hold what it is for: `FLUID_API_KEY`, `FLUID_BEARER_TOKEN`,
`FLUID_LLM_API_KEY`, a catalog token, the PII hashing and encryption keys, a warehouse
password. It may also hold the values the contract or your own credentials already decide —
`FLUID_ENV`, `FLUID_PROJECT`, `FLUID_REGION`, `FLUID_SOURCE_DATABASE` — and the budgets,
timeouts, retries and limits.

What it may not set is any variable that

- **widens a sandbox or a confinement root** — `FLUID_DUCKDB_ALLOWED_DIRS`, `FLUID_REF_ROOT`,
  `FLUID_UPSTREAM_CONTRACTS`, `FLUID_WORKSPACE_ROOT`, `FLUID_LOCAL_DUCKDB_PATH`;
- **moves where the CLI reads trusted configuration, or writes state, audit and logs** —
  `FLUID_SECRETS_FILE`, `FLUID_ENCRYPTION_KEY`, `FLUID_HOME`, `FLUID_CONFIG`,
  `FLUID_STATE_BACKEND`, `FLUID_AUDIT_ROOT`, `FLUID_LOG_FILE`, and the directories those
  resolve against: `HOME`, `USERPROFILE`, the XDG variables, `APPDATA`, `LOCALAPPDATA`,
  `ProgramData`, `TMPDIR` / `TEMP` / `TMP`;
- **changes an authentication or trust mode** — `FLUID_SAFE_MODE`, `FLUID_ALLOW_*`,
  `FLUID_MCP_AUTH_MODE`, `FLUID_MCP_TRUSTED_PROXIES`, every `*_ALLOWLIST`, the TLS, CA and
  proxy settings in either case (`HTTPS_PROXY` / `https_proxy`, `SSL_CERT_FILE`,
  `REQUESTS_CA_BUNDLE`), git's transport settings (`GIT_SSL_*`, `GIT_PROXY_*`, `GIT_TRACE*`),
  `PGSSLMODE`, `DMM_ALLOW_INSECURE_HTTP`;
- **changes where data or credentials are sent** — `FLUID_COMMAND_CENTER_URL` and
  `_ENABLED`, `FLUID_API_URL`, the catalog, lineage and LLM endpoints, `FLUID_LLM_PROVIDER`,
  `FLUID_RUNNER_HOST_OVERRIDE`, `DMM_API_URL`, `DATAHUB_GMS_HOST`, `OPENLINEAGE_URL`,
  `OTEL_EXPORTER_OTLP_*ENDPOINT`, `AWS_ENDPOINT_URL*`, `VAULT_ADDR`, `OLLAMA_HOST`;
- **chooses what program or library runs** — `PATH`, `PYTHONPATH`, `LD_*`, `DYLD_*`,
  `ComSpec`, `SystemRoot`, `NODE_OPTIONS`, `GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `GIT_DIR`,
  `DBT_EXECUTABLE`, `TF_CLI_CONFIG_FILE`, `AWS_CONFIG_FILE`,
  `AWS_SHARED_CREDENTIALS_FILE`, `KUBECONFIG`, `CLOUDSDK_CONFIG`, `DOCKER_HOST`;
- **lets another tool re-read the project's files without the filter** —
  `PYTHON_DOTENV_DISABLED`, `LITELLM_MODE`.

`FLUID_DBZ_*` is protected as a whole prefix: the Debezium runner writes those itself and a
project file has nothing to supply there. The full list is
`fluid_build/credentials/protected_env.py` in forge-cli.

::: tip Two more since `0.23.0`
`FLUID_ACQUISITION_SECRET_REF_ALLOWLIST`, which allows an acquisition source's `env://`
reference against a remote host, and `TESTCONTAINERS_HOST_OVERRIDE`, which rewrites a
contract-declared loopback host to a reachable one, joined the list in `0.23.0`
([forge-cli #751](https://github.com/Agenticstiger/forge-cli/pull/751)). Both decide where a
credential may be sent, so neither may come from a file beside the contract.
:::

### An unlisted name fails closed

A `FLUID_*` name nobody has listed is protected anyway when its shape says it decides
something: one ending in `_URL`, `_ENDPOINT`, `_HOST`, `_ALLOWLIST`, `_BLOCKLIST`, `_ROOT`,
`_DIR`, `_DIRS`, `_PATH`, `_FILE`, `_DSN`, `_HOME`, `_BACKEND`, `_PROXIES`, `_MCP`,
`_COMMAND`, `_ARGS`, `_MCP_ENV` or `_EXECUTABLE`, or containing `_ALLOW_`, `_TRUSTED_`,
`_AUTH_MODE`, `_JWT_` or `_INSECURE`. `_MCP_ENV` rather than a bare `_ENV`, because
`FLUID_ENV` is the environment's name and loads.

So a new operator setting is refused from a project file before anyone remembers to list it.
A test in forge-cli fails on any `FLUID_*` name that appears in the package and is neither
classified as protected, nor as deliberately loadable, nor as not read from the environment at
all.

## What you see when something is ignored

One warning per run, naming the variables and the file that set each, never a value:

```text
WARNING  Ignored 2 settings from project dotenv files: FLUID_DUCKDB_ALLOWED_DIRS (.env),
         HTTPS_PROXY (.env.local). A project file may hold credentials, but not settings
         that widen a sandbox, change authentication or trust, or change where data and
         credentials are sent. If you meant to set them, export them in your shell or CI
         environment instead.
```

A name you have already exported to a non-blank value is left out of the warning: your value
is the one in effect, and nothing was ignored.

Export it in your shell or your CI job, or put it in a `FLUID_SECRETS_FILE` that you export.
Both are trusted, because both come from outside the project.

## Third-party endpoints follow a pairing rule, not a ban

A project that brings its own service legitimately names it, so an endpoint such as
`OPENAI_BASE_URL`, `PGHOST`, `SNOWFLAKE_ACCOUNT` or `DATABRICKS_HOST` is not banned outright.
A project file may set one **only for a credential it supplies itself**. The endpoint is
ignored when

- a credential of the same service is set in your real environment or your
  `FLUID_SECRETS_FILE` — the SDK would otherwise send your credential to the project's host;
  or
- the service also finds a credential of yours outside the environment (a keyring, a stored
  CLI login, an SDK config file, cloud default credentials) and the project files do not
  supply the one every reader of that endpoint sends in its place.

That second clause is why a decoy does not work. A project credential a reader consults only
*after* the keyring, or never, is not what goes out, so it pairs nothing and the endpoint stays
ignored. A project name that differs from yours only in case does not load either.

The refusal says which credential it would have carried:

```text
WARNING  Ignored 1 endpoint setting from project dotenv files: PGHOST (.env, would receive
         PGPASSWORD). A project file may not point a credential you hold outside the project
         at a host the project chose. Export it in your shell or CI environment, or put the
         credential in the same project file.
```

The last clause appears only where a credential in the project file would actually pair the
endpoint. While a switch is set, or you hold a credential of that service, nothing in the
project file can pair it and the advice does not offer that.

A name no group lists is handled by shape, the same way: an endpoint-looking name is refused
while a `<PREFIX>_*` credential-looking name of the same prefix is set in your real
environment. This is how npm binds an auth token to the registry host it was issued for, and
how git matches a stored credential to a URL's host.

### A Snowflake account from the project pins every Snowflake reader

While a Snowflake account from the project's files is in effect, every Snowflake reader — the
credential resolver, OpenTofu, the hosted MCP server, dlt — takes credentials only from the
environment and the project files. A Snowflake `authenticator` other than `snowflake` that the
project sets is refused outright, so a project cannot sign in with your browser session or your
identity provider.

### dlt destinations are default-deny

dlt layers each value it finds on top of the operator's credentials, and it reads a
destination's credentials from the environment under every section path it tries —
`DESTINATION__<NAME>__CREDENTIALS__<FIELD>`, the shorter `DESTINATION__CREDENTIALS__` and
`CREDENTIALS__` sections, each also behind the pipeline name, and a configuration nested
inside the credentials under each of those extended by the nested configuration's name. A
project that set any one of them could move or reshape your connection with your password
still on it.

So every one of those names a project file sets pins the destination: the dlt runner builds
the destination's credentials from the project's own values, or fails closed and names what is
missing. That holds at any depth, under every name dlt reads the field under, the `query` map
and its single keys included, and for every destination type.

The exceptions are the fields that choose something *inside* the account you are already
connected to:

| Destination | Fields a project file may still set |
|---|---|
| postgres, redshift | `database`, `connect_timeout`, `client_encoding`, `session_timezone` |
| snowflake | `database`, `warehouse`, `role` |

`PGHOSTADDR` is yours alone, which closes every libpq reader at once. A destination you
exported — its own dlt host, or a connection string naming a host — stays yours against the
project's FLUID endpoint variables (`POSTGRES_HOST`, `SNOWFLAKE_ACCOUNT`, `REDSHIFT_HOST`); a
dlt credentials field the project sets still pins it.

## dbt and litellm no longer re-read the project's files

dbt loads the nearest `.env` when it starts and litellm loads one when it is imported, either
of which would have read the project's files straight past this filter. `fluid` sets
`PYTHON_DOTENV_DISABLED` at start-up and again once it has read a project's files, and
forwards it to the dbt container; a scheduled apply keeps a `PYTHON_DOTENV_DISABLED` that the
Airflow worker's operator set.

With dbt-core 1.12 or later, dbt therefore no longer finds a `.env` above the contract. Export
the variable and list its name in `FLUID_DBT_FORWARD_ENV` for the dbt container, keep the
`.env` in the directory you run `fluid` from, or set `PYTHON_DOTENV_DISABLED=0` for a checkout
you trust.

A python build step is your own code, so it still loads its own dotenv file.

## Related

- [Environment variables](./environment-variables.md): what each variable does
- [Credential resolver](./credential-resolver.md): where a credential is looked up, and in what order
- [DuckDB sandbox for contract SQL](./duckdb-sandbox.md): the confinement `FLUID_DUCKDB_ALLOWED_DIRS` widens, and its own limits
- [Network safety](./network-safety.md): which outbound fetches are allowed
