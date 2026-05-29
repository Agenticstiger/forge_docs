# Fluid Forge Docs Baseline: CLI `0.8.4`

**Release Date:** May 26, 2026
**Status:** Superseded by [`0.8.5`](./RELEASE_NOTES_0.8.5.md) (supersedes [`0.8.3`](./RELEASE_NOTES_0.8.3.md))

## Headline

`0.8.4` delivers three headline improvements: **Bitol ODPS center-staging** (the Open Data Product Standard v1.0.0 is now the promoted default format throughout the CLI, with LF/ODPI v4.1 as a clearly-labelled opt-in), **engine-as-library Phase 1** (the `fluid_build.engine` module is now a clean public API usable outside the CLI), and **world-class DMM lineage UX** (Data Mesh Manager publish output now surfaces access-agreement status inline, with `--auto-approve-access` for sandbox flows, plus five new `fluid dmm` sub-commands for contract lifecycle management and full workspace wipe). No schema break vs `v0.8.3`.

---

## What changed in `v0.8.4`

### 1 — Bitol ODPS v1.0.0 center-stage, LF/ODPI v4.1 opt-in

**Standards command spelling normalized to `fluid odps`** — the unified dispatch command's canonical spelling fixes an earlier letter-swap. The prior spelling is kept as a silent back-compat alias (deprecation WARNING).

| Command / flag | Canonical form in `v0.8.4` |
|---|---|
| Unified standards export | `fluid odps export` *(default spec: Bitol 1.0.0)* |
| LF/ODPI v4.1 export | `fluid odps export --spec odps-v4.1` |
| One-shot export | `fluid export-odps` |
| `generate standard` default | `--format odps` *(Bitol, center-stage)* |

All old spellings continue to work but emit a deprecation WARNING. Update your scripts at your convenience — they will not break until the next major release.

**`fluid generate standard`** — format table now reads:

- `--format odps` → Bitol ODPS v1.0.0 (**center-stage, default**)
- `--format odcs` → ODCS v3.1.0 (unchanged)
- `--format odps-v4.1` → LF/ODPI ODPS v4.1 (**opt-in**)

The standards environment-variable prefix is `ODPS_*` (`ODPS_INCLUDE_BUILD_INFO`, `ODPS_INCLUDE_EXECUTION_DETAILS`, `ODPS_TARGET_PLATFORM`, `ODPS_VALIDATE_OUTPUT`). Earlier prefix names remain as deprecated aliases.

See the updated [`fluid odps`](./cli/odps.md) and [`fluid generate standard`](./cli/generate.md#fluid-generate-standard) pages.

### 2 — Engine-as-library Phase 1

`fluid_build.engine` is now a clean importable library, not just a CLI internal. Phase 1 exposes:

- `Engine.validate(contract)` — run the same validation pipeline as `fluid validate` programmatically.
- `Engine.plan(contract, provider)` — produce a `PlanResult` without writing files.
- `Engine.apply(plan, provider, *, dry_run=False)` — execute a plan returned by `Engine.plan`.

The module is usable from Python scripts, notebooks, and CI helpers without spawning a subprocess:

```python
from fluid_build.engine import Engine

engine = Engine()
result = engine.validate("contract.fluid.yaml")
plan = engine.plan("contract.fluid.yaml", provider="local")
engine.apply(plan, dry_run=True)
```

The existing CLI stages (`fluid validate`, `fluid plan`, `fluid apply`) continue to work as before — they now delegate to this library internally. All plan-binding cryptographic checks (`bundleDigest` + `planDigest`) apply equally to the library path.

### 3 — Data Mesh Manager lineage UX improvements

**New `fluid dmm` sub-commands** for full contract lifecycle management and sandbox teardown:

| Command | What it does |
|---|---|
| `fluid dmm list-contracts [--format json\|table]` | List all published data contracts in the namespace |
| `fluid dmm get-contract CONTRACT_ID` | Fetch a single contract by ID |
| `fluid dmm delete-contract CONTRACT_ID [--yes]` | Delete a contract by ID |
| `fluid dmm wipe [--yes]` | Delete **all** data products + data contracts (sandbox/CI only) |

**Access-agreement visibility in `fluid dmm publish` output.** The publish panel now displays generated access agreements inline. Agreements that are still `PENDING` are highlighted in yellow with a reminder to approve them in the DMM UI (or via `--auto-approve-access`).

**`--auto-approve-access` / `DMM_AUTO_APPROVE_ACCESS`** — when set, the publisher POSTs the `/approve` endpoint after creating each access agreement. Use for local sandboxes and demo environments; production review flows should leave this off and approve through the DMM UI.

**Team auto-creation hardened** — team creation now always includes `type: "Data Product Team"` (required by Entropy Data CE 2.x). If DMM rejects member emails, the team is retried without `members` while preserving the contact email.

**Access slug unified** — internal slug renamed from `__consumes__` to `__uses__` to match the DMM native identifier. Existing agreements created by older CLI versions are unaffected; only new agreements created by `v0.8.4+` use the new slug.

See the updated [`fluid datamesh-manager`](./cli/datamesh-manager.md) page.

---

## Notable for upgraders

- **Standards command spelling normalized to `fluid odps`** — the prior spelling continues to work until the next major release. CI scripts that parse exact CLI output may see the command name reflected as `odps` in structured output; update pipelines that depend on that field.
- **`--spec odpi-4.1` → `--spec odps-v4.1`** — the old `--spec odpi-4.1` token is accepted with a WARNING and redirected automatically. Mechanical find-and-replace in your scripts is safe.
- **Standards env vars use the `ODPS_*` prefix** — the earlier prefix still works and emits a deprecation WARNING. Update CI env-var exports at your convenience.
- **`fluid export-odps`** — the one-shot export command. Default output path is `runtime/exports/product.odps.json`.
- **`fluid dmm wipe` is destructive** — requires `--yes` or an interactive confirmation. Never pipe `yes |` in production.

---

## What changed in the docs

- **[`fluid odps`](./cli/odps.md)** — fully rewritten to document the renamed unified command with Bitol center-stage, LF/ODPI opt-in, `import` subcommand, and back-compat notes.
- **[`fluid odps-bitol`](./cli/odps-bitol.md)** — updated unified-dispatch section to reflect `fluid odps` name; deprecation note for `--spec odpi-4.1`.
- **[`fluid export-odps`](./cli/export-odps.md)** — new page for the one-shot export command.
- **[`fluid generate standard`](./cli/generate.md#fluid-generate-standard)** — format table updated; `odps-v4.1` added; env-var prefix updated to `ODPS_*`.
- **[`fluid datamesh-manager`](./cli/datamesh-manager.md)** — new sub-commands (`list-contracts`, `get-contract`, `delete-contract`, `wipe`), access-agreement visibility and auto-approve behavior documented.
- **`RELEASE_NOTES_0.8.4.md`** — this file.

---

## Installing

```bash
pip install --upgrade data-product-forge
pip install "data-product-forge==0.8.4"

# Verify
fluid version
# -> 0.8.4
```

---

## Archive note

Older release notes remain available: [`0.8.3`](./RELEASE_NOTES_0.8.3.md), [`0.8.0`](./RELEASE_NOTES_0.8.0.md), [`0.7.11`](./RELEASE_NOTES_0.7.11.md), [`0.7.9`](./RELEASE_NOTES_0.7.9.md), [`0.7.1`](./RELEASE_NOTES_0.7.1.md).
