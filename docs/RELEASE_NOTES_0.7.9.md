# Fluid Forge Docs Baseline: CLI `0.7.9`

**Release Date:** April 6, 2026  
**Status:** Current docs baseline

## What changed in the docs

- Primary docs now track the promoted `fluid --help` command surface from CLI `0.7.9`
- Home, getting-started, and CLI reference pages were rewritten around the local-first path
- `fluid forge` now appears with current public syntax instead of older `--mode` examples
- The CLI reference distinguishes CLI release `0.7.9` from scaffolded contract schema examples using `fluidVersion: 0.7.2`
- Orchestration guidance now leads with `fluid generate schedule --scheduler airflow`
- `fluid generate-airflow` remains documented as a compatibility shortcut, not the primary docs path

## Notable CLI context

CLI `0.7.9` introduced the friendlier first-run recovery path for `fluid forge` and clarified the default `fluid doctor` behavior, including the explicit `--extended` diagnostics flow.

## Archive note

Older release notes remain available for historical context, including [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
