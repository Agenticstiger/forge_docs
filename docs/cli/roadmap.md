# `fluid roadmap`

Print the shipped and upcoming Fluid Forge roadmap from the CLI.

## Syntax

```bash
fluid roadmap
```

## When to use it

Use `fluid roadmap` when you want the branch-local view of:

- shipped forge data-model and AI hardening work
- current milestone focus
- deferred items that are intentionally not part of the current release
- notes that matter to operators, such as deterministic generation and MCP readiness

## Example

```bash
fluid roadmap
```

The output is Markdown, so it can be redirected into a file when you need a snapshot for release review:

```bash
fluid roadmap > ROADMAP.snapshot.md
```

For provider roadmap information in the public docs, see [Provider Roadmap](../providers/roadmap.md).
