# `fluid providers`

List registered infrastructure providers and their capabilities.

## Syntax

```bash
fluid providers
```

## Example

```bash
fluid providers
```

```json
{
  "providers": [
    "aws",
    "datamesh_manager",
    "gcp",
    "local",
    "redshift",
    "snowflake"
  ]
}
```

## Notes

- Use this when you want to confirm which providers the current install can discover.
- These are deployment targets — providers that `fluid apply` can provision infrastructure against.
- Spec-export formats (ODCS, ODPS, ODPS-Bitol) are **not** providers — they do not deploy infrastructure. List them with [`fluid exporters`](./exporters.md) instead.
- `fluid providers --json` is not a supported flag; the command already emits JSON.
- See the [provider guides](/forge_docs/providers/) for target-specific documentation.
