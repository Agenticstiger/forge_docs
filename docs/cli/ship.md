# `fluid ship`

Run a contract through the 11-stage pipeline in one command: bundle, validate, generate artifacts, validate artifacts, diff, plan, apply, policy-apply and verify, with publish and schedule-sync when you ask for them. It runs the same way on a laptop and in CI.

*(since 0.31.0, [forge-cli #917](https://github.com/Agenticstiger/forge-cli/pull/917))* `fluid ship` runs the 11-stage pipeline. Through 0.30.1 it was a four-stage macro that chained `validate → bundle → plan → apply`; that page text is kept in [The four-stage macro (0.30.1 and earlier)](#the-four-stage-macro-0-30-1-and-earlier). See [The 11-stage runner in 0.31.0](#the-11-stage-runner-in-0-31-0).

::: tip Where this fits
`fluid ship` landed in `0.8.3` alongside the day-2 ops surface.
:::

## Syntax

```bash
fluid ship [contract-path] [options]
```

## The 11-stage runner in 0.31.0

*(since 0.31.0, [forge-cli #917](https://github.com/Agenticstiger/forge-cli/pull/917))*

`fluid ship` runs the [11-stage pipeline](../walkthrough/11-stage-pipeline.md) itself, the same way on a laptop and in CI. Each stage is its own `fluid` process with the argv the generated pipelines use, and stage 7 applies the reviewed `runtime/plan.json` against the bundle stage 1 froze, never a re-plan from the contract. `--explain` prints the plan for your contract and runs nothing:

```text
$ fluid ship --explain
fluid ship: 9 stage(s) selected (env=dev, mode=amend, contract=contract.fluid.yaml)
   1 bundle              run      fluid bundle contract.fluid.yaml --env dev --format tgz --out runtime/bundle.tgz
   2 validate            run      fluid validate runtime/bundle.tgz --env dev --report runtime/validate-report.json --strict
   3 generate-artifacts  run      fluid generate artifacts runtime/bundle.tgz --env dev --contract-path contract.fluid.yaml --out dist/artifacts/
   4 validate-artifacts  run      fluid validate-artifacts dist/artifacts/ --report runtime/validate-artifacts-report.json --strict
   5 diff                run      fluid diff runtime/bundle.tgz --exit-on-drift --env dev --out runtime/diff-report.json
   6 plan                run      fluid plan runtime/bundle.tgz --out runtime/plan.json --mode amend --env dev --check-sovereignty
   7 apply               run      fluid apply runtime/plan.json --bundle runtime/bundle.tgz --mode amend --env dev --ensure-opentofu --report runtime/apply-report.html
   8 policy-apply        run      fluid policy-apply dist/artifacts/policy/bindings.json --mode enforce
   9 verify              run      fluid verify runtime/bundle.tgz --strict --env dev --out runtime/verify-report.json
  10 publish             not run  (opt-in: pass --publish or set RUN_STAGE_10_PUBLISH=true)
  11 schedule-sync       not run  (opt-in: pass --schedule-sync or set RUN_STAGE_11_SCHEDULE_SYNC=true)
```

Stages 10 and 11 run only when asked for, with `--publish` and `--schedule-sync` or their [switches](#stage-switches-and-knobs). A stage with nothing to do is skipped with its reason: stage 3 for a reference-only contract (through 0.32.0; see [Reference-only contracts](#reference-only-contracts)) or with `--no-generate-artifacts`, stage 4 when stage 3 generates no `dist/artifacts/`, stage 8 without `dist/artifacts/policy/bindings.json`, stages 9 to 11 after a dry-run apply, and stage 11 without a scheduler or without DAGs in `dist/artifacts/schedule/`. After a dry-run apply in the same pipeline, stage 8 checks the policy bindings instead of enforcing them.

### Select stages

```bash
fluid ship --until plan                  # stages 1-6, then review runtime/plan.json
fluid ship --stage apply,verify --yes    # apply the reviewed plan, then verify it
fluid ship --stage 6-9 --skip-stage policy-apply --yes
```

Stage names and numbers both work, and a range can use names (`--stage plan-verify`). `--publish` and `--schedule-sync` add their stage under `--stage` too. A stage whose input is missing is refused before any stage runs: `--stage apply` without `runtime/plan.json` exits 2 and names stage 6. After `--until`, ship prints the `--stage` value that goes on from there. After a failure it says to run the same command again, or to go on from the failed stage with the same bundle, for example `--stage 5-10` when `--publish` is set, so plan and apply run again before publish.

### Options

Each option takes the flag, then the variable the generated pipelines export, then the default.

| Option | Variable | Default | Description |
|---|---|---|---|
| `[contract-path]` | | `contract.fluid.yaml` in the current directory | The contract. |
| `--env <env>` | `FLUID_ENV` | `dev` | Environment overlay for every stage that reads one. It must start with a letter and hold only letters, digits, `.`, `_` and `-`, at most 64 characters: another name exits 2 before stage 1, because a later stage would refuse it. |
| `--yes`, `-y` | | | Passed to `fluid apply`. Needed in CI. |
| `--dry-run` | | | Same as `--apply-mode dry-run`: apply changes nothing in the target. Plan still writes `runtime/plan.json`. |
| `--apply-mode <mode>` | `APPLY_MODE` | `amend` | Mode for plan and apply: `dry-run`, `create-only`, `amend`, `amend-and-build`, `replace`, `replace-and-build`. |
| `--build-id <id>` | `APPLY_BUILD_ID` | the contract's only build | For `amend-and-build` and `replace-and-build`. An empty value means no build id. |
| `--allow-data-loss` | `ALLOW_DATA_LOSS=true` | | Passed to `fluid apply`. |
| `--no-verify-digest` | `NO_VERIFY_DIGEST=true` | | Passes `--no-verify-plan-binding --no-verify-federation` to `fluid apply`. |
| `--no-generate-artifacts` | | | Skips stage 3. |
| `--require-artifacts <keys>` | | | *(since 0.33.0, [forge-cli #971](https://github.com/Agenticstiger/forge-cli/pull/971))* Fails the run unless stage 3 writes what it promised. See [Requiring artifacts](#requiring-artifacts). |
| `--release-dir <dir>` | | | *(since 0.33.0, [forge-cli #980](https://github.com/Agenticstiger/forge-cli/pull/980))* Publishes the run as a release in a new directory once every stage it ran passed. See [Publishing a release](#publishing-a-release). |
| `--artifacts <lock>` | `RELEASE_ARTIFACTS` | | *On forge-cli `main`, not yet in a release ([forge-cli #1115](https://github.com/Agenticstiger/forge-cli/pull/1115)).* Seals the external files the lock lists into the release. Needs `--release-dir`, and the variable is read only by a run that seals a release. See [Sealing external files](#sealing-external-files). |
| `--journal-dir <dir>` | | | *(since 0.33.0, [forge-cli #1003](https://github.com/Agenticstiger/forge-cli/pull/1003))* Keeps a stage journal in `dir`, and refuses a rerun whose earlier outcome is unknown. A `--release-dir` run keeps one in `.fluid/ship-journal` without it. See [The stage journal](#the-stage-journal). |
| `--acknowledge-inspected <stage>` | | | *(since 0.33.0, [forge-cli #1003](https://github.com/Agenticstiger/forge-cli/pull/1003))* Reruns a stage whose unknown outcome you inspected, and records it. Name or number; repeatable or comma-separated. |
| `--publish` | | | Runs stage 10. |
| `--target <catalog>` | `PUBLISH_TARGETS` (space-separated; the older `CATALOG` too) | `datamesh-manager` | Catalog to publish to; repeatable. A target names a catalog, never an endpoint: one with `:` exits 2 when stage 10 will publish. |
| `--schedule-sync` | | | Runs stage 11. |
| `--scheduler`, `--scheduler-destination`, `--scheduler-environment-name`, `--scheduler-location`, `--scheduler-workspace` | `SCHEDULER`, `SCHEDULER_DESTINATION`, `SCHEDULER_ENVIRONMENT_NAME`, `SCHEDULER_LOCATION`, `SCHEDULER_WORKSPACE` | | Stage 11's scheduler and its `schedule-sync` options. |
| `--schedule-sync-dry-run` | `SCHEDULE_SYNC_DRY_RUN=true` | | Passes `--dry-run` to `schedule-sync`. |
| `--until <stage>` | | | Stops after that stage. |
| `--stage <spec>` | | | Runs only these stages: `7`, `6-9`, `plan,apply`. |
| `--skip-stage <stage>` | | | Skips a stage; repeatable. `--skip-stage apply` is a pipeline without stage 7, so a dry-run mode no longer skips stages 9 to 11, and stage 8 enforces the bindings, as the Jenkins pipeline does. |
| `--explain` | | | Prints the resolved plan and runs nothing. Exits 0, or 2 when ship refuses its arguments; a stage a real run would refuse for a missing input shows as a warning line. |
| `--ci-output` | | `auto` | Log grouping: `auto`, `github`, `gitlab`, `azure`, `plain`. |
| `--report-dir <dir>` | | `runtime/` where ship runs | Where the run reports go. Ship runs in the current directory, or in the contract's own directory when the contract is outside it. A relative path is taken from the current directory. |
| `--skip-bundle` | | | Accepted and ignored: ship always bundles, so no stage runs a stale bundle. |
| `--skip-plan` | | | Removed: exits 2. Use `--stage` or `--until`. |

The options for single stages (`--strict`, `--emit`, `--exit-on-drift`, `--last-applied`, `--plan-html`, `--policy-mode`, `--verify-strict`) and the `RUN_STAGE_<N>_<NAME>` switches are in [Stage switches and knobs](#stage-switches-and-knobs).

### Reference-only contracts

*(since 0.33.0, [forge-cli #971](https://github.com/Agenticstiger/forge-cli/pull/971))*

Through 0.32.0, stage 3 skipped every contract with a `hybrid-reference`, `reference` or `external-reference` build, even with `--emit`. Stage 4 skipped too, and the run exited 0 with no `MANIFEST.json`. But `fluid generate artifacts` has written ODCS, ODPS and policy artifacts for such contracts for a long time: they do not depend on where the transformation runs. Stage 3 now runs for them as well.

Stage 4 now fails, where it used to skip, when stage 3 was to write `dist/artifacts/` and did not. It still skips under `--no-generate-artifacts`. A CI file from `fluid generate ci` still switches stage 3 off by default for a reference-only contract. *(since 0.33.0, [forge-cli #1000](https://github.com/Agenticstiger/forge-cli/pull/1000))* It does not: only `fluid generate ci --no-generate-artifacts` turns stage 3 off.

### Requiring artifacts

*(since 0.33.0, [forge-cli #971](https://github.com/Agenticstiger/forge-cli/pull/971))*

`--require-artifacts KEYS` fails the run unless stage 3 writes what it promised. A key is one of `generate artifacts`' emit keys:

| Key | Stage 3 must write |
|---|---|
| `odcs` | One ODCS file for each `exposes[]` port of the bundled contract |
| `odps-bitol` | The ODPS product |
| `opds` | The OPDS document |
| `policies` | `policy/bindings.json` |
| `schedule` | At least one schedule file |

```bash
fluid ship --require-artifacts odcs,policies
```

Ship removes the earlier `dist/artifacts/MANIFEST.json` before stage 3 runs. A file counts only when the new MANIFEST lists it and its digest on disk matches, so output left by an earlier run never passes. When a file is missing, stage 3 fails with exit `1` and names every missing file (the port, for ODCS), in the log, in `ship-report.json` and in the JUnit report:

```text
stage 3 generate-artifacts: required artifact missing: schedule: stage 3 wrote no schedule file (orchestration.engine is none, or it is unset and no build has a schedule trigger)
ERROR: stage 3 generate-artifacts failed (exit 1)
Ship aborted at stage 3 generate-artifacts (it exited 0, but --require-artifacts was not met). After the fix, run the same command again; to go on from that stage with this bundle, use --stage 3-9.
```

A run that cannot meet the requirement is refused with exit `2` before stage 1, and `--explain` shows why:

- Stage 3 does not run in this invocation (`--stage`, `--until`, `--skip-stage`, `--no-generate-artifacts`, or `RUN_STAGE_3_GENERATE_ARTIFACTS=false`).
- `--emit` or `GENERATE_EMIT` leaves a required key out.

```text
warning: a real run would stop: --require-artifacts odcs needs stage 3 generate-artifacts in this invocation, and it does not run (--no-generate-artifacts)
```

An unknown key exits `2` and lists the keys: `fluid ship: --require-artifacts: unknown key(s) bogus: use odps-bitol, odcs, opds, schedule, policies`.

### Publishing a release

*(since 0.33.0, [forge-cli #980](https://github.com/Agenticstiger/forge-cli/pull/980))*

`--release-dir DIR` publishes a run as a release, once every stage it ran passed. Use it when a later job, an auditor or a promotion step needs one directory that holds what this run produced.

```bash
fluid ship --release-dir releases/orders-1 --yes
```

The run stages into a new `DIR.partial-<run-id>-*` beside `DIR`. It copies the bundle, the artifacts the artifacts MANIFEST lists (each checked against its digest), the plan when stage 6 ran, and the reports there. It writes `release.json` last, and renames the directory to `DIR`. This is what a run of a one-expose local contract published:

```text
releases/orders-1/
├── artifacts/        the files artifacts/MANIFEST.json lists, with the MANIFEST
├── bundle.tgz
├── bundle.tgz.provenance.json   (since 0.35.0, when the bundle names a source contract)
├── plan.json
├── release.json
└── reports/          ship-report.json, ship-junit.xml, and each stage's report
```

A run that fails, or is interrupted, publishes nothing. Its reports stay in `runtime/` and in the staging directory, and `ship-report.json` names the stage that stopped it. `DIR` does not exist after a failed run. A release run first removes the stage reports in `runtime/`, so only this run's are published. Through 0.34.0 the release directory held the bundle but not its `.provenance.json` file, so a plan made from the release's bundle recorded no source contract and `fluid apply` refused a contract with a dbt build. *(since 0.35.0, [forge-cli #1022](https://github.com/Agenticstiger/forge-cli/pull/1022))* The release holds `bundle.tgz.provenance.json`, written for the release's own place: the same source contract, relative to the release directory (see [The provenance file](./bundle.md#the-provenance-file)). `release.json` lists it in `files` with its sha256, and it stays out of `identity`. A bundle that names no source contract gets no file, and neither does a release on another drive. `fluid ship` then warns `release_provenance_missing`. The file names the contract relative to where the release was published, so keep the release at the same place in the checkout, as CI artifacts restored into the same layout are. A release run reads only local files: it opens no network connection of its own.

**Rules.** `DIR` must not exist, and stages 1 to 4 must run in the invocation. Otherwise ship refuses with exit `2`, and `--explain` says why:

```text
warning: a real run would stop: --release-dir needs stages 1-4 (bundle to validate-artifacts) in this invocation, and stage 3 generate-artifacts does not run (--no-generate-artifacts)
```

**Every port is verified.** *(since 0.33.0, [forge-cli #986](https://github.com/Agenticstiger/forge-cli/pull/986))* Under `--release-dir`, stage 9 passes `--require-every-port` to `fluid verify`, so a run that runs stage 9 publishes a release only when every expose was verified. An expose that was skipped (no verifier for its binding, or a reference-only table that is not built yet), an entry that verify cannot check (no id, or an id used twice) and a contract with no exposes fail stage 9, and nothing is published. `--explain` shows the argument:

```text
   9 verify              run      fluid verify runtime/bundle.tgz --strict --require-every-port --env dev --out runtime/verify-report.json
```

The flag is added whether or not `--no-verify-strict` drops `--strict`. A run that does not run stage 9, for example with `--skip-stage verify`, still publishes. See [Requiring every port](./verify.md#requiring-every-port).

**`release.json`** keeps what the release is apart from how it was made:

| Key | Holds |
|---|---|
| `schema` | `fluid-release/1` |
| `identity` | The product id, environment, `fluidVersion`, Forge version, the exact emit set and any `--require-artifacts` keys, the bundle's MANIFEST digest and archive sha256, the artifacts MANIFEST digest, the plan's digests, the apply mode when stage 7 ran (so a dry run never reads as an apply), and the external files a lock names (`external`, see [Sealing external files](#sealing-external-files)) |
| `identity_digest` | A digest of `identity`. Two clean runs of one checkout give the same `identity` and `identity_digest` |
| `provenance` | The run id, the stage times, the CI run and the report time |
| `gates` | Each stage's number, name, status and reason |
| `files` | The sha256 of every file in the release |

`identity` holds nothing that changes from run to run, so a downstream job compares `identity_digest` to tell whether two runs built the same release. The run id and the times are in `provenance`, outside it.

### Sealing external files

*On forge-cli `main`, not yet in a release ([forge-cli #1115](https://github.com/Agenticstiger/forge-cli/pull/1115)).*

A product can run code Forge does not build: a PySpark package that writes its own output, a hand-written Airflow DAG, a file another job reads. `--artifacts LOCK` seals those files into the release, next to what the run built, so the release names every piece of code that ran. `$RELEASE_ARTIFACTS` names the lock when the flag is absent.

```bash
fluid ship --release-dir releases/orders-1 --artifacts release-artifacts.yaml --yes
```

The lock lists each file, the sha256 of its bytes, and the repository and commit it was built from:

```yaml
artifacts:
  - name: orders-jobs
    kind: spark-package          # spark-package (.whl, .zip), airflow-dag (.py, .zip) or file
    path: dist/orders_jobs-1.4.0-py3-none-any.whl
    sha256: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
    source:
      repo: https://git.example.com/data/orders-jobs
      commit: 4b825dc642cb6eb9a060e54bf8d69288fbee4904
      ref: refs/tags/v1.4.0      # optional
  - name: orders-dag
    kind: airflow-dag
    path: dags/orders_daily.py
    sha256: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
    source:
      repo: git@git.example.com:data/orders-dags.git
      commit: 9fceb02d0ae598e95dc970b74767f19372d61af8
```

**Rules.** Ship reads the lock before stage 1 and refuses, with exit `2`, a lock it cannot seal:

- an unknown field, or a `kind` other than the three, or a file name its kind does not take;
- a `name` that is not letters, digits and `._-` (at most 100, starting with a letter or digit), or two names that differ only in case;
- a `path` that is absolute, names a hidden file or directory, or leads out of the lock's directory, by `..` or through a linked directory. A path is relative to the lock's directory, and each of its segments takes letters, digits and `._=+-` only;
- a link, or anything that is not a regular file;
- bytes whose sha256 is not the one the lock names. The message gives the lock's value and never the digest the file has: put the one `sha256sum` prints in the lock;
- a `repo` that is not an `https`, `http`, `ssh` or `git` URL or `user@host:org/repo`, a `commit` that is not 7 to 64 hex characters, or a `ref` with characters a branch or tag name does not take. A user and password in the URL are dropped, as they are from the CI's own source.

`--artifacts` without `--release-dir` is refused, and so is a blank value (`--artifacts "$LOCK"` with `LOCK` unset). `$RELEASE_ARTIFACTS` without `--release-dir` is not read at all, so one variable set for every job of a pipeline leaves the jobs that seal nothing, such as an apply step, alone.

**What the release holds.** When every stage passed, ship reads the lock again, copies each file to `external/<name>/<file>`, and hashes the copy again before `release.json` is written: a file that changed while the run ran publishes nothing. `files` lists each copy with its sha256, and `identity` gains `external`, the entries sorted by name:

```json
"external": [
  {
    "name": "orders-jobs",
    "kind": "spark-package",
    "path": "external/orders-jobs/orders_jobs-1.4.0-py3-none-any.whl",
    "digest": {"sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"},
    "source": {
      "uri": "git+https://git.example.com/data/orders-jobs@refs/tags/v1.4.0",
      "digest": {"gitCommit": "4b825dc642cb6eb9a060e54bf8d69288fbee4904"}
    }
  }
]
```

Each entry is shaped like a SLSA provenance `resolvedDependencies` entry, with its source the way `fluid bundle --attest` records the contract's own. No path on the machine that ran ship is recorded, so two clean runs with the same lock and bytes give one `identity_digest`, and a changed file gives a new one. [`fluid runs status --release-dir`](./runs.md#which-release-was-in-force) prints one `external` line for each file.

### The stage journal

*(since 0.33.0, [forge-cli #1003](https://github.com/Agenticstiger/forge-cli/pull/1003))*

`fluid ship` can keep a journal of what each stage did, so that a rerun after a crash does not apply, publish or schedule again against a target nobody has looked at. It is on with `--journal-dir DIR`, and with every `--release-dir` run, which keeps it in `.fluid/ship-journal` under the project. Without either flag no journal is kept and no stage is refused. The one change is that the run report records a stage that exits 129 to 159, or is killed by a signal, as `unknown` instead of `failed`.

```bash
fluid ship --journal-dir /var/lib/fluid/ship-journal --yes
fluid ship --journal-dir /var/lib/fluid/ship-journal --stage 6-7 --yes --acknowledge-inspected apply   # after an apply of unknown outcome
```

**What it writes.** One append-only JSON Lines file for each release, named by the bundle's digest, for each target, which is the product and the environment: `DIR/<product id>/<env>/<digest hex>.jsonl`, beside a `.lock` file. The product id and the environment are written as file names, and an id with upper-case letters gets a short hash added. A run holds the target through that lock, and a second run is refused before it rebundles. Each stage that runs leaves two events. `started` is written and fsynced before the stage runs (for `bundle`, once it has passed, because the bundle names the release). A stage that is skipped, or refused by the journal, leaves none. `finished` carries its status, its exit code and receipts: the report files the attempt wrote with their digests, the plan's digests, and the lineage and serial of local OpenTofu state. A file opens with an `opened` event, and an acknowledgement is an `acknowledged` event.

```text
{"argv": ["plan", "runtime/bundle.tgz", "--out", "runtime/plan.json", ...], "attempt": 1, "event": "started", "name": "plan", "run_id": "852290d84289", "side_effects": false, "stage": 6, ...}
{"attempt": 1, "event": "finished", "exit_code": 0, "name": "plan", "receipts": {"files": {"runtime/plan.json": "sha256:a47e..."}, "plan": {...}}, "stage": 6, "status": "passed", ...}
```

Nothing is rewritten: a rerun adds attempts. A last line cut off by a crash is ignored. The `argv` of a stage is recorded with credential-bearing values masked.

**What it refuses.** Before a stage that changes the target runs, ship reads what earlier attempts left. These stages change it: `apply`, unless it is a dry run, `policy-apply`, unless it only checks, `publish`, and `schedule-sync`, unless it is a dry run. The stages that only read always rerun.

| Left by an earlier attempt | The stage is refused until |
| --- | --- |
| An attempt of that stage that could change the target (a dry run or a check never counts), in any release of the target, that started and never finished, or finished `unknown`: ship was interrupted or killed, the stage was killed by a signal (exit 129 to 159, such as 130 for Ctrl-C), or a CI job timed out. An unknown `apply` also blocks `policy-apply`, `publish` and `schedule-sync`, which would act on a target nobody has looked at | You inspect the target and pass `--acknowledge-inspected STAGE`, which records it |
| An `apply` in this release that failed or whose outcome was unknown, so the plan it ran is stale | Stage 6 has planned again through ship, and `runtime/plan.json` is that plan: `--stage 6-7` |

```text
stage 7 apply: stage journal: stage 7 apply started in this release for env dev at 2026-11-19T06:20:00.000Z and has no known outcome (attempt 1), so what it changed in the target is unknown. Inspect the target, then run again with --acknowledge-inspected apply
```

```text
stage 7 apply: stage journal: stage 7 apply failed in attempt 2 for this release, so it may have changed part of the target and the plan it ran is stale. Plan again against the target as it is now, then apply (--stage plan-apply)
```

The refused stage is recorded with exit code `2` and ship stops, exiting `1` (`3` if an apply has already changed something). `--acknowledge-inspected` takes a stage name or number, repeated or comma-separated, and one acknowledgement of a stage clears its unresolved attempts in every release of the target. After an unknown `apply` that blocks `policy-apply`, `publish` or `schedule-sync`, name `apply`. It exits `2` for an unknown stage (the message lists them), for a stage that changes nothing, and when there is no journal to record it in (`--journal-dir` or `--release-dir`). Acknowledging an unknown `apply` does not make the old plan good: the next `apply` is still refused until the plan is made again. Nothing is rolled back. Recovery goes forward: inspect, plan again, apply again.

**Seeing it.** `--explain` prints the journal's path and marks each stage the journal would refuse, with its reason, and ends with the warning `a real run would stop`. The run report, `runtime/ship-report.json`, has a `journal` block when a journal is kept: the `dir` (`.fluid/ship-journal` for the default, a project-relative path, or the label `--journal-dir`, never an absolute path), the `path` of the release file below it, and the `digest` of that file when the report was written. A release published with `--release-dir` carries the same block under `provenance.journal` in `release.json`.

**Where to keep it.** The journal is evidence only where the checkout cannot write it. Keep `DIR` outside the checkout, and out of reach of runs at a lower trust level: a CI cache that a pull request can fill is such a reach. The default under `--release-dir` is in the checkout, where it guards a working copy against its own reruns. Ship follows no symbolic link below the journal directory, reads only regular files with one link, and refuses a journal file larger than 8 MiB, and more than 64 MiB for the release files of one target. A journal that cannot be opened or written refuses only the stages that change the target. A `--journal-dir` that cannot be created or opened is a usage error, exit `2`, before stage 1:

```text
fluid ship: stage journal: cannot create the stage journal directory /dev/null/x/gold.customer.analytics_360_v1/dev: Not a directory
```

### Stage switches and knobs

*(since 0.31.0, [forge-cli #929](https://github.com/Agenticstiger/forge-cli/pull/929))*

A generated pipeline exposes a switch per stage, `RUN_STAGE_<N>_<NAME>` (`RUN_STAGE_1_BUNDLE` to `RUN_STAGE_11_SCHEDULE_SYNC`), and `fluid ship` reads the same variables:

- `false` switches a stage off, under `--stage` too: a CI step names its stage, it does not decide whether it runs. A step whose stages are all switched off prints `fluid ship: stage 5 diff is switched off (RUN_STAGE_5_DIFF=false): nothing to run` and exits 0 without writing a report; the run's first step records the switch for that stage in the shared report. Flags that leave nothing to run on their own still exit 2.
- `true` switches on stage 10 or 11, only in a run that does not name its stages with `--stage`, so a CI step that runs `--stage 3` never publishes. `--publish` and `--schedule-sync` beat their own switch.
- Any other value leaves the default. With stage 3 switched off, stage 4 skips instead of asking for `dist/artifacts/`. With stage 7 switched off, a dry-run mode no longer skips stages 9 to 11, and stage 8 enforces the bindings.

Each stage option takes the flag, then the variable the Jenkins pipeline already read, then the default. A flag beats its variable both ways:

| Stage | Option | Variable | Default | Description |
|---|---|---|---|---|
| 2, 4 | `--strict`, `--no-strict` | `VALIDATE_STRICT` | on, unless the variable is `false` | `--strict` for `validate` and `validate-artifacts`. |
| 3 | `--emit <list>` | `GENERATE_EMIT` | every emitter | `generate artifacts --emit`, comma-separated: `odps-bitol`, `odcs`, `opds`, `schedule`, `policies`. *(since 0.33.0, [forge-cli #979](https://github.com/Agenticstiger/forge-cli/pull/979))* `spark` is a sixth key, and `GENERATE_EMIT` in a generated Jenkinsfile lists it. `--explain` assumes only the outputs it names, so stage 8 shows as skipped without `policies`. |
| 5 | `--exit-on-drift`, `--no-exit-on-drift` | `DIFF_EXIT_ON_DRIFT` | on, unless the variable is `false` | Whether drift fails stage 5 or is only reported. |
| 5 | `--last-applied <plan>` | `DIFF_LAST_APPLIED` | | `diff --last-applied`: compares with the plan the last apply ran, so a change the contract makes is pending, not drift. A missing file is a first run, compared with the contract alone. |
| 6 | `--plan-html`, `--no-plan-html` | `PLAN_HTML` | off, unless the variable is `true` | Also writes `runtime/plan.html`. |
| 8 | `--policy-mode <mode>` | `POLICY_APPLY_MODE` | `enforce` | `enforce` or `check`. After a dry-run apply in the same pipeline, `enforce` becomes `check`. Another value exits 2 before stage 1. |
| 9 | `--verify-strict`, `--no-verify-strict` | `VERIFY_STRICT` | on, unless the variable is `false` | `--strict` for `verify`. With `--release-dir`, `verify` also gets `--require-every-port`. |

Stages 2 and 4 also write `runtime/validate-report.json` and `runtime/validate-artifacts-report.json`. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* When stage 11 runs (a scheduler is set, stage 3 wrote DAGs, and apply was not a dry run), it passes `--report runtime/schedule-sync-report.json` to `fluid schedule-sync`.

### Required artifacts and change-request builds

*(since 0.37.0)* `--require-artifacts` also accepts `custom-scaffold` and `pyspark-schema`. On a build its CI marks as a change request, `fluid ship` leaves `custom-scaffold` out of stage 3 and says so in the stage's notes. A run that would seal a release (`--release-dir`) or publish while `--require-artifacts` names `custom-scaffold` is refused with exit 2. `--adopt-tables` is passed to the apply stage. See [Custom scaffold](./generate-artifacts.md) and [Adopting existing Glue tables](./apply.md).

*(since 0.37.0)* A release's `release.json` also records each expose's version (`identity.expose_versions`) and the CI's source revision, repository and ref (`provenance.source`). See [`fluid runs status`](./runs.md).

### A wrapped store token

*(since 0.37.0, [forge-cli #1042](https://github.com/Agenticstiger/forge-cli/pull/1042))* A runner such as Command Center can hand a run its OpenBao or Vault token response-wrapped, as `FLUID_VAULT_WRAPPED_TOKEN`, and a wrapper opens once. Ship runs each stage as its own process, so through 0.36.0 only the first stage that reached the store could use the wrapper. With OpenBao state encryption, `fluid diff` and `fluid apply` both reach it, so `diff` spent it and `apply` then failed. Now a ship of two or more stages opens the wrapper before the first stage and hands every stage the token it yields:

- **One unwrap, one revoke.** Ship opens the wrapper once, hands each stage the token through a pipe, and revokes that token when the run ends, also after a failed stage and after Ctrl-C. No stage revokes it. dbt, a project's build steps and the stage's other child processes never see the token. `tofu` gets it, as `BAO_TOKEN`, only for OpenBao state encryption, which needs it to reach the key. A stage reads the pipe, which `FLUID_VAULT_SHIP_TOKEN_FD` names, as it starts. Windows has no inherited pipes, so there the token travels in `FLUID_VAULT_SHIP_TOKEN`, which the stage takes out of its environment at once. Ship sets both names for its stages, an operator never does, and a project `.env` cannot set them.
- **A wrapper that cannot be opened stops the run before any stage.** Ship exits 2 with a message that starts `fluid ship: no stage ran:`. It happens when the wrapper is spent, when no store address is set, and when the store cannot be reached. For a spent wrapper the message says to treat the run's credentials as exposed, unless this run opened it.
- **A ship of one stage leaves the wrapper to that stage**, as before, so a pipeline that runs one stage per CI step works as it did. A single `fluid apply` uses the wrapper itself.
- **A wrapper serves one `fluid ship` invocation.** A run split over several invocations needs a wrapper for each.

The store resolver reads this token before any other, a project `.env` token included, and `fluid doctor` reports its auth method as `ship-token`. A ship that SIGTERM or SIGKILL ends does not revoke the token, which then lasts until its TTL. See [A response-wrapped token](./secrets.md#a-response-wrapped-token).

### Exit status

| Code | Meaning |
|---|---|
| `0` | Every selected stage passed or was skipped, or every stage the flags selected is [switched off](#stage-switches-and-knobs). |
| `1` | A stage failed. |
| `2` | Ship refused its arguments: an unknown stage or a reversed range, no stage left to run, an environment name a stage would refuse, a publish target with `:`, `--dry-run` with another `--apply-mode`, a missing input, no contract, a contract that is missing, symlinked or under a system path, or `--skip-plan`. *(since 0.37.0, [forge-cli #1042](https://github.com/Agenticstiger/forge-cli/pull/1042))* Also a wrapped store token that cannot be opened: see [A wrapped store token](#a-wrapped-store-token). |
| `3` | A stage failed after apply changed something, so those changes are live. A dry-run apply changes nothing. |
| `130` | Interrupted. |

The failing stage's own exit code is in the report and in the line ship prints when it stops, for example `Ship aborted at stage 5 diff (exit 2)`. The first Ctrl-C does not stop ship at once: it waits for the running stage to end, then stops the run (exit 130). From a terminal the stage gets the same Ctrl-C and may stop on its own. A second Ctrl-C stops the stage.

### Reports

Every run that starts a stage writes `runtime/ship-report.json` and `runtime/ship-junit.xml`. The JSON holds the run id, env, mode, contract and the run's exit status, and for each stage its status, the reason it was skipped or failed, its argv, exit code and duration. The JUnit file has one test case per stage.

*(since 0.33.0, [forge-cli #980](https://github.com/Agenticstiger/forge-cli/pull/980))* `ship-report.json` is versioned, `"schema": "fluid-ship-report/2"`. Every stage has one of six statuses:

| Status | Meaning |
|---|---|
| `passed` | The stage ran and passed. |
| `failed` | The stage ran and failed. |
| `skipped-by-policy` | A flag, a `RUN_STAGE_*` switch or a dry run turned it off. |
| `unsupported` | There is nothing to act on: no policy bindings, no DAGs, no scheduler. |
| `not-run` | It was not selected, or came after a failure. |
| `unknown` | It was interrupted or killed by a signal (exit 129 to 159): what it had done by then is not known. |

Each stage also has one `reason`, which replaces `skip_reason` and `failure_reason`, and `started_at` and `finished_at` in UTC. The report gains `written_at`, a `journal` block when a [stage journal](#the-stage-journal) is kept, and a `release` block under `--release-dir` with the directory, a `status` (`published` or `not-published`), the `identity_digest` and the `reason`. In one-step-per-stage CI, an earlier step's report that is the run's but cannot be read leaves the stages before this step `unknown`, and the run's `exit_code` is not 0. A version 1 record still merges, with `skipped` read as `skipped-by-policy`. JUnit counts `unknown` as a failure and both kinds of skip as skipped.

A CI job that calls `fluid ship --stage N` once per step gets one report: calls with the same run id, env, mode and contract merge, and each call keeps its own records for the stages it selected. The run id is `FLUID_RUN_ID`, else the one in `.fluid/run-id.txt`. A call that includes stage 1 starts a new report.

### Output in CI

`--ci-output auto` reads the CI system from the environment. On GitHub Actions each stage is a `::group::`, a failure is an error annotation and the stage table goes to the job summary; every stage runs between `::stop-commands::` markers, so nothing the checkout prints can issue a workflow command. GitLab gets collapsible sections and Azure Pipelines `##[group]` blocks. Anywhere else each stage gets a banner:

```text
── stage 1/11 · bundle ────────────────────────────────────────
$ fluid bundle contract.fluid.yaml --env dev --format tgz --out runtime/bundle.tgz
...
── stage 9/11 · verify ────────────────────────────────────────
$ fluid verify runtime/bundle.tgz --strict --env dev --out runtime/verify-report.json
...
Ship complete: 9 stage(s) passed, 0 skipped
```

### Where it runs

A contract outside the current directory (`fluid ship /tmp/x/contract.fluid.yaml`) runs in its own directory, so `runtime/` and `dist/` land beside it. A contract below the current directory keeps the current directory as the project root.

*(since 0.37.0, [forge-cli #1042](https://github.com/Agenticstiger/forge-cli/pull/1042))* A stage no longer imports modules from that directory. Through 0.36.0 a stage started as `python -m fluid_build.cli` in the contract's directory, so a `yaml.py` or a `fluid_build/` in the checkout ran inside every stage, before the CLI started, with your environment. A stage now starts the CLI as `-m` does, without the checkout on the import path.

### From the four-stage macro

- Apply runs the reviewed `runtime/plan.json` against `runtime/bundle.tgz`, so the plan digest binding holds. `--env` reaches bundle, validate and every other stage that reads the overlay, not only plan and apply.
- `diff`, `generate artifacts`, `validate artifacts`, `policy-apply` and `verify` now run, and `validate` is strict by default. `--no-strict` drops `--strict` from `validate` and `validate-artifacts`.
- `--skip-plan` exits 2, and `--skip-bundle` is ignored.
- The bundle is `runtime/bundle.tgz` and the plan `runtime/plan.json`, not `<contract id>.fluid.bundle.tgz` beside the contract and `plan.json` in the current directory.
- The exit status is ship's own. A script that read the failing stage's code from `$?` reads it from the report.

## The four-stage macro (0.30.1 and earlier)

Through 0.30.1, `fluid ship` chained `validate → bundle → plan → apply` and nothing else. The text below describes that macro. In 0.31.0 and later, `--skip-plan` exits 2 and `--skip-bundle` is ignored; see [From the four-stage macro](#from-the-four-stage-macro).

### Examples of the four-stage macro

These are the four-stage macro's examples (0.30.1 and earlier). The first exits 2 in 0.31.0, where `--skip-plan` is removed; see [The 11-stage runner in 0.31.0](#the-11-stage-runner-in-0-31-0).

```bash
# Local dev: validate + apply only (0.30.1 and earlier)
fluid ship --skip-bundle --skip-plan --yes

# Production-style: validate strictly, then deploy the prod overlay
fluid ship contract.fluid.yaml --strict --env prod --yes

# Render the apply without writing anything
fluid ship contract.fluid.yaml --env dev --dry-run
```

The last command runs all four stages. Each stage line shows the command `ship` ran:

```text
🚢 fluid ship — running 4 stage(s)
...
[ship validate] $ fluid validate /.../contract.fluid.yaml
[ship bundle] $ fluid bundle /.../contract.fluid.yaml --format tgz
[ship plan] $ fluid plan /.../contract.fluid.yaml --env dev
[ship apply] $ fluid apply /.../contract.fluid.yaml --env dev --dry-run
...
🎉 Ship complete — all 4 stage(s) passed
```

### How the four-stage macro behaves

`fluid ship` runs the four core stages in sequence, stopping at the first failure and relaying that stage's exit code:

```text
1. fluid validate <contract>                [--strict if --strict is set]
2. fluid bundle <contract> --format tgz     (skipped if --skip-bundle)
3. fluid plan <contract>                    [--env]  (skipped if --skip-plan)
4. fluid apply <contract>                   [--env] [--yes] [--dry-run]
```

Each stage runs as a separate process (`python -m fluid_build.cli <stage>`), so a stage's own flag handling and errors are unchanged.

Three things `ship` does not do, which differ from the [11-stage pipeline](../walkthrough/11-stage-pipeline.md):

- **`--env` reaches only `plan` and `apply`.** `validate` and `bundle` run against the base contract, so the bundle is not built for the environment you apply.
- **`apply` gets the contract path, not the bundle or `plan.json`.** `ship` therefore has no bundle or plan digest binding between the reviewed plan and the apply. For a chain that binds them, use [`fluid generate ci`](./generate.md#fluid-generate-ci) or run the stages yourself.
- **`--dry-run` does not stop before `apply`.** It passes `--dry-run` to `fluid apply`, which renders what it would do and writes nothing. The run still reports every stage as passed.

### Options of the four-stage macro

| Option | Description |
|---|---|
| `[contract-path]` | Path to the contract. Auto-discovered from the current directory if omitted. |
| `--env <env>` | Environment overlay, passed to `plan` and `apply` only. |
| `--strict` | Pass `--strict` to `fluid validate` (treat warnings as errors). |
| `--yes`, `-y` | Pass `--yes` to `fluid apply` (skip the interactive confirmation). Needed in CI. |
| `--skip-bundle` | Skip the bundle stage. |
| `--skip-plan` | Skip the plan stage. |
| `--dry-run` | Pass `--dry-run` to `fluid apply`. |

### Files the four-stage macro writes

The bundle stage runs `fluid bundle <contract> --format tgz` with no `--out`, so the bundle goes next to the contract as `<contract id>.fluid.bundle.tgz`. The plan stage writes `plan.json` in the current directory. Neither is read by `apply`. Add them to `.gitignore`, or pass `--skip-bundle` and `--skip-plan`.

A `fragments/` directory next to the contract does not change where the bundle goes since 0.26.0 ([forge-cli #763](https://github.com/Agenticstiger/forge-cli/pull/763)). In 0.25.0 and earlier, `fluid bundle` sent a no-`--out` run on a fragment layout to `<contract dir>/contract.bundled.fluid.yaml`, and for `--format tgz` wrote the gzip tarball under that `.yaml` name, which `fluid validate` and `fluid plan` could not read as a contract. If an earlier `fluid ship` left that file beside your contract, delete it.

### When to use the macro vs. the individual stages

| Use `fluid ship` when | Use individual stages when |
|---|---|
| You've already iterated and want a clean push | You're debugging a failing stage |
| For demo and quickstart speed | You need stage-specific flags `ship` doesn't expose (per-stage `--out` paths, `bundle --format`, `plan --html`) |
| | You want to inspect `plan.json` before apply, or bind the apply to the plan |

In 0.30.1 and earlier, for the production-grade 11-stage pipeline (cryptographic plan binding, drift gating, supply-chain signing), use [`fluid generate ci`](./generate.md#fluid-generate-ci) to emit the full pipeline for your CI system instead of `fluid ship`. *(since 0.31.0, [forge-cli #942](https://github.com/Agenticstiger/forge-cli/pull/942))* The pipeline `fluid generate ci` writes calls `fluid ship` for every stage, so the macro and the generated pipeline run the same code: see [What a generated pipeline runs](../advanced/operating-in-ci.md#what-a-generated-pipeline-runs).

### Exit codes of the four-stage macro

`fluid ship` relays the exit code of the **first failing stage**:

| Code | Meaning |
|---|---|
| `0` | All stages passed |
| Non-zero | Exit code of the failing stage (e.g. `1` from `validate` for a schema error) |

With no contract path and no `contract.fluid.yaml` in the current directory, `ship` exits `1` with `contract_required`. Stage logs are written to stdout and stderr unmodified: the macro doesn't buffer or reformat them. Pipe to `tee` or to your CI system's log capture as usual.

## See also

- [`fluid validate`](./validate.md), [`fluid bundle`](./bundle.md), [`fluid plan`](./plan.md), [`fluid apply`](./apply.md): the stages `ship` chains
- [`fluid generate ci`](./generate.md#fluid-generate-ci): production-grade 11-stage pipeline generator
- [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md): when you need more than the four core stages
