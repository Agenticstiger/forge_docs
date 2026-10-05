# `fluid status`

Print a one-page summary of the FLUID product you are standing in: who owns it, how its contract is laid out on disk, when `fluid forge` and `fluid init` last ran, and whether the CI files FLUID generated have been edited since.

`fluid status` reads local files only. It makes no network call and does not look at deployed resources.

## Syntax

```bash
fluid status
```

`fluid status` takes no options. It walks up from the current directory to the nearest directory that holds a `contract.fluid.yaml`, so you can run it from a subdirectory of the product. If it finds none, it summarises the current directory and shows `—` for every row it cannot fill.

## Example

```bash
cd my-data-product
fluid status
```

```text
╭──────────────────────────────── fluid status ────────────────────────────────╮
│                                                                              │
│    Product         gold.customer.analytics_360_v1  (Customer 360             │
│                    Analytics)                                                │
│    Domain          Customer Experience                                       │
│    Owner           customer-analytics  (workspace: proj)                     │
│    Workspace       proj                                                      │
│                    /path/to/proj                                             │
│    Authoring       flat                                                      │
│    Last forge      2026-10-05T00:00:52.759945Z (flow=template)               │
│    Last init       2026-10-05T00:00:52.763881Z                               │
│    CI              —                                                         │
│    Drift           —                                                         │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
Next:  fluid validate  fluid plan --env dev  fluid forge --ci <provider>
```

This is the output for a product scaffolded with `fluid init --quickstart` and no CI files yet. The command exits `0` even when it cannot read part of the state, so a pipeline step that runs it does not fail on a partial workspace.

## What each row means

| Row | Where it comes from |
| --- | --- |
| **Product** | The contract's `id` and `name`. |
| **Domain** | The contract's top-level `domain`; if that is empty, `metadata.domain`. |
| **Owner** | `metadata.owner.team` (or `metadata.owner` when it is a plain string), with the workspace name appended when there is one. |
| **Workspace** | The `name` in `fluid.workspace.yaml`, and the directory that holds it. |
| **Authoring** | `flat` or `fragment-first`. See [Authoring: flat or fragment-first](#authoring-flat-or-fragment-first). |
| **Last forge** | The `generated_at` time and `flow` recorded in the product's `.fluid/forge-receipt.json`. |
| **Last init** | The `generated_at` time in the workspace's init receipt. |
| **CI** | The provider, complexity and number of files recorded in the product's `.fluid/ci-state.json`. Written when `fluid forge` scaffolds CI files. |
| **Drift** | Whether those generated CI files still match what was recorded. See [What Drift measures](#what-drift-measures). |

The schema version (`fluidVersion`) is not a row in the panel. It appears only in the plain-text layout that replaces the panel when the Rich library is not installed. To see it, run [`fluid validate`](./validate.md), whose output names the schema it validated against.

## Authoring: flat or fragment-first

`Authoring` tells you how the contract is stored:

| Value | Meaning |
| --- | --- |
| `flat` | One `contract.fluid.yaml` holds the whole contract. |
| `fragment-first (N fragments)` | The root contract points at separate files with `$ref`, and `N` YAML files sit under `fragments/`. When the product has an `overlays/` directory, the count of `*.yaml` overlays is added: `fragment-first (3 fragments, 2 overlays)`. |

The detection is a directory test, not a read of the contract. A product counts as fragment-first when a `fragments/` directory next to the contract contains at least one `*.yaml` file. Three consequences follow:

- Files ending in `.yml` are not counted. A `fragments/` directory that holds only `.yml` files reports `flat`.
- A layout whose fragments live under another directory name reports `flat`, even if the root contract is full of `$ref` pointers. The directory name `fragments/` is a convention the CLI depends on.
- The overlay count comes from `overlays/*.yaml` only; `.yml` and `.json` overlays are not counted there.

The layout is described in [Contract fragments](../concepts/fragments.md); the workspace line comes from [`fluid.workspace.yaml`](../concepts/workspaces.md). [`fluid split`](./split.md) writes the `fragments/` layout and [`fluid bundle`](./bundle.md) resolves it back into one document. `fluid validate`, `fluid plan` and `fluid apply` resolve the `$ref` pointers themselves; see [Composing a contract with `$ref`](../concepts/contract-refs.md).

Here is the same product after `fluid split contract.fluid.yaml`:

```text
│    Authoring       fragment-first (3 fragments)                                                            │
```

## What Drift measures

The `Drift` row is **CI scaffold drift**. It compares the CI files FLUID generated (a GitHub Actions workflow, a `Jenkinsfile`, and so on) with the fingerprints recorded in `ci-state.json` when they were written. It does not inspect the data platform and says nothing about whether deployed tables match the contract.

| Row text | Meaning |
| --- | --- |
| `—` | No CI files were scaffolded for this product, so there is nothing to compare. |
| `✓ clean (3/3 pristine)` | No recorded file differs from its recorded fingerprint. A recorded file that was deleted from disk is not counted as drift; it lowers the first figure instead, as in `clean (2/3 pristine)`. |
| `⚠ drifted: 1, unknown: 0, pristine: 2/3` | One recorded file was edited by hand since FLUID generated it. |

The `unknown` figure counts files that exist but that the state file does not record. `fluid status` only inspects the files the state file lists, so as of 0.18.1 it reads `0`.

To find out whether the deployed state has drifted from the contract, use [`fluid diff`](./diff.md) or [`fluid verify`](./verify.md).

## Notes

- Run `fluid status` after a `git pull` to see whether a teammate re-scaffolded CI, and before editing a generated pipeline by hand to know whether you would overwrite a file that is already customised.
- For health checks of the CLI and the machine it runs on, use [`fluid doctor`](./doctor.md).
