# `fluid auth`

Manage authentication for cloud and data platform providers.

## Syntax

```bash
fluid auth                                # interactive guide (no verb → friendly panel)
fluid auth <login|status|logout|list|doctor>
```

::: tip Bare invocation is friendly
Running `fluid auth` with no verb renders a Rich panel listing every action
with a one-line description and a quick-start.  When local auth state is
already present the guide highlights `status`; otherwise it highlights
`login` as the right starting move.
:::

## Commands

| Command | Description |
| --- | --- |
| `login` | Authenticate with a provider |
| `status` | Show authentication status |
| `logout` | Log out from a provider |
| `list` | List supported auth providers |
| `doctor` | Audit credential hygiene and security posture |

## Examples

```bash
fluid auth login gcp
fluid auth status
fluid auth logout aws
fluid auth doctor
fluid auth list
```
