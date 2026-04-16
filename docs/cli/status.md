# `fluid status`

Print a one-page summary of the FLUID product in the current directory.

The summary covers: identity (product id, domain, schema version), workspace location, authoring mode, the last `fluid forge` run, the configured CI provider, and whether the deployed state is in drift against the contract.

## Syntax

```bash
fluid status
```

## Key options

`fluid status` takes no options — it runs against the project in the current working directory and prints the summary in under half a second.

## Examples

```bash
cd my-data-product
fluid status
```

## Notes

- Run it from the project root (the directory that contains `contract.fluid.yaml`).
- For deeper health checks, use [`fluid doctor`](./doctor.md) (with `--extended` for workspace diagnostics).
- To see what would change against deployed resources, use [`fluid diff`](./diff.md) or [`fluid verify`](./verify.md).
