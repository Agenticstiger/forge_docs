# `fluid roadmap`

Print the engineering roadmap that ships inside the forge-cli package.

## Syntax

```bash
fluid roadmap
```

## What it prints

The output is Markdown. In 0.18.1 it opens like this:

```text
# forge-cli roadmap

forge-cli v1.0 shipped 2026-04-23. The Lean v1 scope previewed several v1.1+
milestones early; they are listed under "Shipped in v1.0" below and have been
retargeted out of the upcoming-milestone track so the banner and `fluid
roadmap` point at the next truly unshipped milestone.
```

Its sections, as printed by `fluid roadmap | grep '^#'`:

```text
# forge-cli roadmap
## Shipped in v1.0 (previewed from v1.1+ roadmap)
### v1.0.1 follow-up (landed 2026-04-24)
### v2-gap close-out (landed 2026-04-24)
### V1 world-class hardening (landed 2026-04-25)
### dbt Mesh preservation constraints (shipped alongside v1.3)
## Milestone v1.2 — Semantic Reuse
## Milestone v1.5 — MCP Server
```

Most of it is a changelog-style history of what landed. The two `Milestone` sections at the end carry target dates of 2026-05-07 and 2026-06-11, and the text does not mark either as shipped. It lists no gate list and no milestone after v1.5, so it is not a view of what is planned next.

Because the output is Markdown, you can save a snapshot:

```bash
fluid roadmap > ROADMAP.snapshot.md
```

## Where to look instead

- **A gate list.** `fluid --help` ends with `Run fluid roadmap for the full gate list`. As of 0.18.1 the roadmap output contains no gate list. The stages that gate a release pipeline are on the [CLI index](./README.md#the-11-stage-pipeline) and in the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md).
- **Provider status.** [Provider Roadmap](../providers/roadmap.md).
- **What shipped in each release.** The release notes, for example [0.18.0](../RELEASE_NOTES_0.18.0.md).
