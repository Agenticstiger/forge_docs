# `fluid auth`

Manage authentication for cloud and data platform providers.

## Syntax

```bash
fluid auth <login|status|logout|list|doctor>
```

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
