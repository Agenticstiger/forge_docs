# `fluid auth`

Manage authentication for cloud and data-platform providers: sign in, see who you are signed in as, sign out, and audit how your credentials are stored.

## Syntax

```bash
fluid auth                                    # a guide: the verbs and a suggested next step
fluid auth <login|status|logout|doctor> [PROVIDER]
fluid auth list
```

`PROVIDER` is a positional argument that follows the verb. There is no `--provider` option on `fluid auth`: the top-level `--provider` option selects the infrastructure provider for other commands and is a different thing.

## Examples

```bash
fluid auth login gcp
fluid auth status
fluid auth status aws
fluid auth logout aws
fluid auth logout databricks dev
fluid auth doctor
fluid auth doctor --fix
fluid auth list
```

Running `fluid auth` with no verb prints a short guide that lists each verb with an example. When local auth state is already present it marks `status` as the suggested first step, and otherwise it suggests `login`.

## Commands

| Command | Description |
| --- | --- |
| `login [PROVIDER]` | Authenticate with a provider. A provider is required; without one the command exits `1`. |
| `status [PROVIDER]` | Show authentication status. Without a provider it checks them all. |
| `logout [PROVIDER] [PROFILE]` | Sign out of a provider. A provider is required; without one the command exits `1`. For `databricks`, name the one profile to remove from the config file (see [below](#databricks-logout)). |
| `list` | List the providers and their aliases. |
| `doctor [PROVIDER] [--fix]` | Audit credential hygiene. Without a provider it covers them all. |

### Providers

```bash
fluid auth list
```

```text
🔐 Available Authentication Providers
==================================================
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Provider     ┃ Aliases     ┃ Description                           ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ google_cloud │ gcp, google │ Google Cloud Platform                 │
│ aws          │ amazon      │ Amazon Web Services                   │
│ azure        │ microsoft   │ Microsoft Azure                       │
│ snowflake    │             │ Snowflake Data Cloud                  │
│ databricks   │             │ Databricks Unified Analytics Platform │
└──────────────┴─────────────┴───────────────────────────────────────┘

Usage: fluid auth login <provider>
```

::: warning Known issue in 0.18.1: only `gcp`, `aws` and `snowflake` work as the PROVIDER argument
`fluid auth list` advertises five providers and their aliases, but the provider you type after a verb is also checked against the registry of infrastructure providers, which holds `aws`, `datamesh_manager`, `gcp`, `local`, `redshift` and `snowflake`. A name outside it is rejected with exit `2` before the auth code runs:

```bash
fluid auth status azure
```

```text
⚠️ Unknown provider 'azure' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
⚠️ Provider 'azure' requires --project to be specified
```

`azure` and the aliases `google_cloud`, `google`, `microsoft` and `amazon` all fail this way. Use `gcp` and `aws` for those two clouds. For Azure, sign in with the platform's own tooling, then run `fluid auth status` with **no provider**: without an argument the command checks every provider and does not go through the registry check.

`databricks` failed this way too until 0.26.0, which added the Databricks provider ([forge-cli #769](https://github.com/Agenticstiger/forge-cli/pull/769)) to that registry. `fluid auth status databricks` and `fluid auth logout databricks` now work.
:::

## `fluid auth status`

`status` shows one row per provider with a status (`Authenticated`, `Not Authenticated` or `Error`) and the account or reason behind it. A provider whose own CLI is missing shows `Error` with the reason, as in `SnowSQL CLI not installed` for Snowflake.

The exit code is `0` only when every provider it checked is authenticated. `fluid auth status` with no provider returns `1` on a machine where any one of the five is not signed in, so do not use the bare form as a pass/fail gate. Check the one provider you need:

```bash
fluid auth status gcp && fluid plan contract.fluid.yaml --env gcp
```

## `fluid auth logout`

Logout removes the credential `fluid auth login` saved for the provider. For `databricks` it works on one profile of the config file (`~/.databrickscfg`, or the file `DATABRICKS_CONFIG_FILE` names), because that file belongs to the Databricks CLI, SDK, dbt and terraform and holds every profile.

<a id="databricks-logout"></a>

```bash
fluid auth logout databricks dev
```

- It removes only the profile you name, keeps the others, writes the file back owner-only (`0600`) and never deletes it. The token it held stays valid until it is revoked in the workspace.
- With no profile named, a file that holds profiles is left alone and the command exits `1`, listing them. `DATABRICKS_CONFIG_PROFILE` is quoted in that hint, never acted on.
- An OAuth profile (`auth_type = databricks-cli`) is left to `databricks auth logout --profile=<name> --delete`, which clears its cached tokens.
- A hard-linked file, or one that belongs to another user (a logout under `sudo`), is left as it is.

Before 0.26.0 the command never got this far: the CLI refused `databricks` as an unknown provider. The library call `AuthManager.logout("databricks")` deleted the whole file ([forge-cli #772](https://github.com/Agenticstiger/forge-cli/pull/772)). See [Databricks](../providers/databricks.md#fluid-auth-logout-databricks).

## `fluid auth doctor`

`doctor` audits how credentials are stored and used on this machine. It prints a table with a `PASS`, `WARN`, `FAIL` or `INFO` row for each check:

| Check | What it looks at |
| --- | --- |
| CI Environment | Whether the process runs in CI, and which CI system. |
| OIDC Availability | In CI only: whether OIDC tokens are available to exchange for short-lived credentials. `WARN` when none are, with a pointer to workload identity federation. |
| OS Keyring | Whether the `keyring` library is importable, so secrets can live in the operating system's keyring. |
| `.env` Permissions, `.env.local` Permissions | For each file in the current directory: `FAIL` when it is readable by group or others. |
| Encryption Key Perms | `FAIL` when `~/.fluid/.key` has any mode other than `0600`. |
| Long-Lived Credential | In CI only: `WARN` for each of `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `GOOGLE_APPLICATION_CREDENTIALS` and `SNOWFLAKE_PASSWORD` that is set, with the short-lived alternative. |
| `<provider>` Auth | `PASS` with the credential type, `WARN` when expired, `INFO` when not signed in. |
| `<provider>` Scope Guidance | A note on least-privilege scopes, for the providers that have one. |

The options:

| Option | Description |
| --- | --- |
| `PROVIDER` | Audit one provider. Without it, audit them all. |
| `--fix` | Fix what can be fixed: set the mode of `.env`, `.env.local` and `~/.fluid/.key` to `0600`. Nothing else is changed. |

The exit code is `1` when any check is `FAIL` and `0` otherwise. A `WARN`, such as a long-lived key in CI, does not fail the run.

## Notes

- To see which infrastructure providers FLUID has loaded, which is a different list from the one `fluid auth list` prints, use [`fluid providers`](./providers.md).
- For the environment variable and secret-store side of credentials, see [`fluid secrets`](./secrets.md).
