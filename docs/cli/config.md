# `fluid config`

Read and write three keys, `provider`, `project` and `region`, in `.fluid/context.json` in the current directory.

## Syntax

```bash
fluid config                  # interactive guide (no verb → friendly panel)
fluid config <list|set|get>
```

::: tip Bare invocation is friendly
Running `fluid config` with no verb
renders a Rich panel listing `list`, `get`, and `set` with example
invocations.  When `.fluid/context.json` already exists in the cwd the
guide highlights `list`; otherwise it points the operator at `set` as
the right starting move.
:::

## Commands

| Command | Description |
| --- | --- |
| `list` | Print the whole file as JSON. Prints `{}` when there is none. |
| `set KEY VALUE` | Set a key. `KEY` must be `provider`, `project` or `region`. Creates `.fluid/context.json` when needed. |
| `get KEY` | Print one key's value. |

## Examples

```bash
fluid config list
fluid config set provider gcp
fluid config set project my-gcp-project
fluid config set region us-central1
fluid config get provider
```

```text
gcp
```

```bash
fluid config list
```

```json
{
  "provider": "gcp",
  "project": "my-gcp-project",
  "region": "us-central1"
}
```

## What reads these values

As of 0.18.1 `fluid plan` did not read these keys from `.fluid/context.json`. In a measured run, `fluid config set provider nope` followed by `fluid plan contract.fluid.yaml` planned normally: the plan took its provider from the contract's `binding.platform`, and `fluid validate` ignored the key too. To choose a provider for a command, pass the global `--provider` flag or set `FLUID_PROVIDER` (see [`fluid providers`](./providers.md#when-a-provider-cannot-be-found)). The same goes for `--project` and `FLUID_PROJECT`, and for `--region` and `FLUID_REGION`.

This is separate from [`fluid.workspace.yaml`](./workspace.md#the-workspace-config-file-fluid-workspace-yaml), the workspace-root file that `fluid init` writes and that does feed defaults to `fluid init` and `fluid forge`.
