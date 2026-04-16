# `fluid import`

Scan an existing directory and generate FLUID contracts from discovered assets.

## Syntax

```bash
fluid import
```

## Key options

| Option | Description |
| --- | --- |
| `--provider` | Provider for the generated contracts |
| `--dir`, `-C` | Directory to scan |
| `--yes`, `-y` | Skip the confirmation prompt |

## Examples

```bash
fluid import
fluid import --dir ./legacy-dbt
fluid import --provider snowflake
fluid import --yes
```

## Notes

- This is the promoted migration path for existing dbt, Terraform, or SQL projects.
- If you want a clean greenfield start instead, use [`fluid init`](./init.md) or [`fluid forge`](./forge.md).
