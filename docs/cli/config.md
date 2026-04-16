# `fluid config`

Get or set workspace defaults such as provider, project, and region.

## Syntax

```bash
fluid config <list|set|get>
```

## Commands

| Command | Description |
| --- | --- |
| `list` | Show current context |
| `set` | Set a key |
| `get` | Read a key |

## Examples

```bash
fluid config list
fluid config set provider gcp
fluid config set project my-gcp-project
fluid config set region us-central1
fluid config get provider
```
