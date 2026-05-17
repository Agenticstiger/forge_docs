---
title: CLI by task
description: Forge command reference organized by what you're trying to do, not by command name.
---

# CLI by task

The [CLI Reference](../) lists every command alphabetically — useful as a lookup, but if you arrived here trying to **do** something specific, this index is faster.

## I want to…

| Task | Walkthrough | Key commands |
|---|---|---|
| **Deploy a data product to a new cloud** | [Switch clouds with one line](./switch-clouds) | `init` · `validate` · `plan` · `apply` |
| **Add quality rules to my product** | [Add a quality rule](./add-quality-rules) | `validate` · `test` · `verify` |
| **Debug a failed pipeline run** | [Debug a 3am incident](./debug-failed-run) | `runs status` · `runs logs` · `runs diff` · `ship` |
| **Add AI / agent access governance** | [Gate LLM access with agentPolicy](./agent-governance) | `policy-check` · `policy-apply` · `mcp serve` |

Each task page is a narrative — start at the top, follow along, end with a working result. They're complementary to (not a replacement for) the [alphabetical CLI reference](../).

## Why both?

- **Alphabetical reference** ([../README.md](../)) — *"What does `fluid policy-apply --mode check` do?"* (lookup)
- **Task pages** (this section) — *"I just got paged at 3am, what do I do?"* (narrative)

Both exist because both questions get asked. Bookmark the one that matches how you read docs.

## See also

- [Concepts](/forge_docs/concepts/) — the conceptual reference (one-time read, deep)
- [Recipes](/forge_docs/recipes/) — small one-page solution patterns (drop-in copy/paste)
- [Walkthroughs](/forge_docs/walkthrough/local) — full-length end-to-end builds
