---
title: Contract reference
description: Field-by-field reference for the FLUID contract schema, generated from the schemas bundled in the CLI. Stable 0.7.5, and the 0.7.6 preview delta.
---

# Contract reference

The fields of the FLUID contract schema, each with its type, whether it is required, the values it allows, its default and what it means. A script renders the tables from the JSON Schema files that ship inside the CLI package, the files `fluid validate` checks a contract against, and CI fails when a committed page no longer matches them.

| Page | What it lists | Status |
| --- | --- | --- |
| [Schema 0.7.5](./contract-0.7.5.md) | The fields of the schema, from `fluidVersion` down to nested keys | Stable |
| [Schema 0.7.6 preview](./contract-0.7.6-preview.md) | What 0.7.6 adds to 0.7.5, changes in it, and removes from it, field by field | Preview, opt-in |
| [Fields that need 0.7.6](./preview-fields.md) | The preview fields by the CLI release that introduced them, with validated examples | Preview, opt-in |

## Find a field

Take this fragment of a contract:

```yaml
exposes:
  - exposeId: orders
    binding:
      platform: aws
      encryption:
        kms: product
```

`kms` is addressed as `exposes[].binding.encryption.kms`: `.` steps into an object and `[]` stands for "each item of this list". Search the page for that path. The row for it sits on the [0.7.6 preview delta](./contract-0.7.6-preview.md), because `binding.encryption` exists only in the preview schema.

## How to read a row

Each page is a set of tables with these columns.

| Column | What it holds |
| --- | --- |
| Path | The field's address from the contract root. `[]` marks the items of a list. `<key>` stands for any key of a map, as in `labels.<key>`. |
| Type | The JSON Schema type. `array of string` is a list of strings. `object (map)` is an object whose keys you choose. |
| Required | `yes` when the field must be present inside its parent object. The parent can itself be optional, so a `yes` under an optional block binds only once you write the block. |
| Allowed values | The enum, pattern, length or range the schema enforces. A long list or pattern is folded into an expandable summary. |
| Default | The `default` the schema declares. An empty cell means the schema declares none. |
| Description | The schema's own description, unedited. |

Four more conventions:

- An object typed plainly `object` rejects keys the schema does not list. `object (open)` accepts extra keys as well as the listed ones. `object (free-form)` has no listed keys.
- A row whose description starts "Only when ..." exists only under that condition. The `builds[].properties` rows work this way: which keys are valid depends on the build's `pattern`.
- A row that says "When `platform` is `gcp`: ..." in its Allowed values adds a constraint that applies under that condition. `exposes[].binding.encryption.kms` carries two of these.
- Where one definition is used at several paths, its rows are listed once. The other paths get a single row that says "Same fields as ..." and names the first path. The legacy `build` block points at `builds[]` this way.

The generated pages state the CLI package version and the schema file they came from, so you can tell which release a table describes.

## Stable and preview

A contract declares the schema it is written against in `fluidVersion`. The CLI bundles several schema versions and validates a contract against the one it names:

```text
✅ Valid FLUID contract (schema v0.7.5)
```

- **0.7.5 is stable.** It is the newest stable schema bundled with the CLI. The [0.7.5 page](./contract-0.7.5.md) is the complete reference.
- **0.7.6 is a preview.** A contract opts in with `fluidVersion: "0.7.6"`. A contract that declares 0.7.5 has fields such as `binding.encryption`, `lifecycle.expire` and `consumes[].upstreamWorkspace` rejected by `fluid validate` as unexpected keys. A few delta rows, such as the masking `params` keys, are accepted by 0.7.5 because it left their parent open; [preview-fields](./preview-fields.md) names them. The [preview delta](./contract-0.7.6-preview.md) lists what differs.
- **0.7.1 to 0.7.4** are also bundled, and a contract that names one of them validates against it. They are not rendered here.

Which versions are stable and which are preview comes from the CLI itself, so the generated pages follow a promotion in a later release rather than going stale. The 0.7.6 schema is bundled in the CLI package. On 5 Oct 2026 the spec site's schema address for 0.7.6 (`/schema/fluid-schema-0.7.6.json`) returned 404, so read the preview from the package or from this reference.

To see the schema file your own CLI uses:

```bash
python -c "import fluid_build, pathlib; print(pathlib.Path(fluid_build.__file__).parent / 'schemas')"
```

## The vendor-neutral spec

FLUID is also published as a vendor-neutral specification at [open-data-protocol.github.io/fluid](https://open-data-protocol.github.io/fluid/). The CLI prints the same address in the footer of `fluid --help`. The spec site publishes JSON Schema files and an HTML rendering of the 0.7.5 spec.

This reference answers a narrower question: what does the CLI you installed accept? On 5 Oct 2026 the 0.7.5 schema file served from the spec site did not contain `exposes[].binding.vectorConfig`, which the 0.7.5 schema bundled in the pinned CLI does. `fluid validate` uses the bundled file, so when the two differ, this reference is the one that matches your validation result.

## How the pages are generated

`scripts/gen_contract_reference.py` reads the schemas from the installed `data-product-forge` package and writes the two `contract-*.md` pages. Besides that package it reads only the version pin file: no network, no clock. The same schemas produce the same bytes.

```bash
pip install data-product-forge==<pinned version>
python scripts/gen_contract_reference.py            # rewrite the pages
python scripts/gen_contract_reference.py --check    # fail if the committed pages drifted
```

The pinned version is the one in `docs/.vuepress/cli-version.json`, and the script refuses to run against any other. The CLI/docs consistency workflow runs the `--check` form, so a CLI bump that changes a schema fails the check until the pages are regenerated and committed. The script also stops on a schema keyword it does not know how to render, so a release that adds one cannot be documented with that keyword silently missing.

The pages written by hand are this one and [Fields that need 0.7.6](./preview-fields.md). The generator does not touch them.

## Related

- [What is a contract](../concepts/contract.md): the model the fields express.
- [Builds, exposes and bindings](../concepts/builds-exposes-bindings.md): how the three core blocks fit together.
- [`fluid validate`](../cli/validate.md): checking a contract against its schema.
- [Composing a contract with `$ref`](../concepts/contract-refs.md): split a contract across files.
