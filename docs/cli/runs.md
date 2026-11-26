# `fluid runs`

Day-2 introspection for acquisition runs. `fluid runs` reads the run records and logs that source-aligned builds leave in the state directory (`.fluid/` by default) and answers three questions: what ran lately and how did it end, what did a component log, and what changed between two runs.

It is separate from [`fluid status`](./status.md) (a summary of one product's files), [`fluid doctor`](./doctor.md) (health of the CLI and its machine) and [`fluid auth`](./auth.md) (cloud credentials).

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the panic — Fluid Forge day-2 ops">
</iframe>

The reel above walks `runs status`, `runs logs --component dlq`, `runs diff`, a policy fix and `fluid ship`. It pairs with [`fluid retention`](./retention.md), [`fluid secrets`](./secrets.md) and [`fluid stats`](./stats.md).

::: tip Available in 0.8.3
`fluid runs` ships with the source-aligned acquisition stack in `0.8.3` (schema `0.7.3`). Earlier releases do not include it.
:::

## Syntax

```bash
fluid runs status <product-id> [--build BUILD] [--last N] [--state-root PATH] [--json]
fluid runs status <product-id> --release-dir DIR [--release-dir DIR ...] [--on YYYY-MM-DD] [--env NAME] [--json]
fluid runs verify-release SRC [--json]
fluid runs logs   <product-id> [--component C] [--run-id ID] [--grep TEXT] [--limit N] [--state-root PATH] [--json]
fluid runs diff   <product-id> --build BUILD --run-a ID --run-b ID [--state-root PATH] [--json]
```

All three read the state directory, `./.fluid` unless you pass `--state-root`. Run them from the directory that holds the product's `.fluid/`, which for acquisition builds is the directory of the contract.

Without `--json`, the output is an indented `key: value` listing, not a table. With `--json`, it is a JSON document with sorted keys.

## Where the data comes from

```text
.fluid/
├── runs/<product-id>/<build-id>/runs/<run-id>.json    # one record per run
├── logs/<product-id>/<build-id>/<component>.log        # component logs
└── dlq/<run-id>/<stream>.ndjson                        # records routed to the dead-letter queue
```

Acquisition builds write the run records and the dead-letter files. A run record is a JSON file. These are the keys the `runs` commands read:

```json
{
  "run_id": "0101M3W8N4EGS716V5",
  "state": "partial",
  "started_at": "2026-10-01T17:37:06Z",
  "finished_at": "2026-10-01T17:37:09Z",
  "records_total": 11,
  "facets": { "duration_seconds": 3.1 },
  "error": "stream refunds: 1 record routed to the DLQ",
  "streams": [
    { "name": "orders", "records": 10, "state": "succeeded" },
    { "name": "refunds", "records": 1, "state": "failed" }
  ]
}
```

`state` is one of `queued`, `running`, `succeeded`, `partial`, `failed`, `cancelled` or `archived`. The examples below read two records of this shape. The run IDs are the file names, and `runs status` orders runs by them, newest first.

## `fluid runs status`

Show the most recent runs of a product, with freshness, the error rate over the last 24 hours, and per-stream record counts.

```bash
fluid runs status bronze.crm_orders
fluid runs status bronze.crm_orders --build ingest_orders --last 10
fluid runs status bronze.crm_orders --json
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--build ID` | The build to inspect. Without it, the command takes the first build directory it finds under `runs/<product-id>/`, in name order. Pass `--build` when a product has more than one. |
| `--last N` | How many recent runs to list. Default `5`. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit JSON instead of the listing. |

```bash
fluid runs status bronze.crm_orders --json
```

```json
{
  "build_id": "ingest_orders",
  "error_rate_24h": 0.0,
  "facets": {
    "total_runs_seen": 2
  },
  "freshness_seconds": 304123.563919,
  "last_state": "partial",
  "product_id": "bronze.crm_orders",
  "runs": [
    {
      "duration_seconds": 3.1,
      "error": "stream refunds: 1 record routed to the DLQ",
      "finished_at": "2026-10-01T17:37:09Z",
      "records_total": 11,
      "run_id": "0101M3W8N4EGS716V5",
      "started_at": "2026-10-01T17:37:06Z",
      "state": "partial",
      "streams": [
        {
          "name": "orders",
          "records": 10,
          "state": "succeeded"
        },
        {
          "name": "refunds",
          "records": 1,
          "state": "failed"
        }
      ]
    },
    {
      "duration_seconds": 2.3,
      "error": null,
      "finished_at": "2026-10-01T11:41:08Z",
      "records_total": 8,
      "run_id": "0101M3VM992GJ62H1F",
      "started_at": "2026-10-01T11:41:06Z",
      "state": "succeeded",
      "streams": [
        {
          "name": "orders",
          "records": 8,
          "state": "succeeded"
        }
      ]
    }
  ]
}
```

What the top-level fields mean:

| Field | Meaning |
| --- | --- |
| `runs` | The most recent `--last` runs, newest first. `duration_seconds` comes from the record's `facets.duration_seconds`, or from `finished_at - started_at` when that is missing. |
| `freshness_seconds` | Seconds since the newest `succeeded` run finished. `null` when no run succeeded. |
| `error_rate_24h` | The fraction (`0` to `1`) of runs from the last 24 hours that ended `failed` or `partial`. `0.0` when no run falls in that window, as in the example, whose runs are days old. |
| `last_state` | The `state` of the newest run. |
| `facets.total_runs_seen` | How many records the command read: up to 100, or `--last` when that is larger. |

`freshness_seconds` depends on when you run the command.

With a product that has no runs, the command prints a one-line message and exits `1`:

```text
no builds found for product nothing.here under .../.fluid/runs/nothing.here/
```

## `fluid runs verify-release`

*On forge-cli `main`, not yet in a release ([forge-cli #1116](https://github.com/Agenticstiger/forge-cli/pull/1116)).*

Checks a sealed release without changing it. `SRC` is a release directory that `fluid ship --release-dir` wrote, or the `s3://bucket/prefix/<product>/<code hex>/<env>/` that [`fluid ship --release-to`](./ship.md#publishing-to-s3) wrote.

```bash
fluid runs verify-release releases/orders-1
fluid runs verify-release s3://acme-releases/orders/acme.orders/6369...9999/prod/ --json
```

It checks that:

- `release.json` is a `fluid-release/1` record, at most 1 MB;
- its `identity_digest` is the digest of its `identity`;
- `code_digest` is the digest of the code `identity` names, recomputed (see [The code digest](./ship.md#the-code-digest)), and is absent only when `identity` names no source commit;
- for an S3 key laid out as `<code hex>/<env>/`, the code hex is this release's and the environment is its own;
- every file the index lists is there, with the sha256 it names. A path in the index that is absolute, has `..`, or names `release.json` is not intact;
- the identity pins a bundle and an artifacts MANIFEST, as every sealed release does, and a `plan.json` only when it pins a plan;
- the files `identity` pins are listed with the digests `identity` names: `bundle.tgz`, each external file, `artifacts/MANIFEST.json` (its Merkle root) and each artifact it lists, and `plan.json` (its `bundleDigest` and `planDigest`). The `files` list sits outside `identity_digest`, so a file swapped with its entry rewritten, or dropped from the list, is not intact.

A directory is read without following a link: a file reached through one is not intact. An S3 release is read with `GetObject` only. A file the index does not list is not part of the release and is not read.

```text
s3://acme-releases/orders/acme.orders/6369...9999/dev/: NOT INTACT
  release  sha256:cce7...89bd
  code     sha256:6369...9999
  product  acme.orders
  env      dev
  files    14 checked
  - bundle.tgz: the index does not list it with the sha256 the identity's bundle names
```

With `--json` it prints `source`, `status` (`intact`, `not-intact` or `undecided`), `identity_digest`, `code_digest`, `product_id`, `environment`, `files_checked`, `problems` and `objects`. `objects` lists each object read, `release.json` first, with its `path`, `sha256` and `version_id`: the S3 VersionId on a versioned bucket, `null` for a directory. Record those to name exactly which object versions were checked.

| Code | Meaning |
| --- | --- |
| `0` | Intact. |
| `1` | Not intact: no `release.json` there, a record that does not parse or is not `fluid-release/1`, an identity digest that does not match, a file that is missing, changed, reached through a link or listed under a path a release never writes, or a file `identity` pins that is not listed with its digest. |
| `2` | Cannot decide: the release cannot be read (access denied, a network error, a bucket that does not exist), or boto3 is missing for an `s3://` source (install the `aws` extra). A local directory needs no extra. |

Like [Intact and not intact](#intact-and-not-intact), this proves the bytes match the index, not who wrote the index. The same check is public in Python as `fluid_build.api.verify_release`, and `runs status --release-dir` uses its identity check.

## `fluid runs receipt`

*On forge-cli `main`, not yet in a release ([forge-cli #1122](https://github.com/Agenticstiger/forge-cli/pull/1122)).*

A receipt records what one environment's check of a sealed release found. A later environment's deploy passes `receipt check` only when an earlier environment checked the same code and the check passed. The model is [Kargo](https://docs.kargo.io/user-guide/how-to-guides/working-with-freight)'s: Freight, named by a digest of what it carries, goes downstream only after an upstream Stage verified it. Here the [code digest](./ship.md#the-code-digest) plays the Freight's part: one commit and one lock, sealed once per environment.

```bash
# nonprod: check the deployed product against the release, then record the result
fluid verify contract.fluid.yaml --release s3://acme-releases/orders/acme.orders/6369...9999/nonprod/ --out verify.json
fluid runs receipt record s3://acme-releases/orders/acme.orders/6369...9999/nonprod/ --report verify.json \
  --target "s3://acme-dags/dags/orders.py#3HL4kqtJlcpXroDTDmJ.rmSpXd3dIbrHY" \
  --target "git+https://git.example.com/ops/dags@<full commit>" --check-targets

# prod: deploy only if nonprod passed for the same code
fluid runs receipt check s3://acme-releases/orders/acme.orders/6369...9999/prod/ --env nonprod --require-locked
```

### `fluid runs receipt record`

`record SRC --report R` verifies SRC first, as [`verify-release`](#fluid-runs-verify-release) does, then writes a `fluid-receipt/1` record write-once to `<code hex>/receipts/<env>/<utc>-<identity16>.json` beside it. For a release directory, the record goes to `receipts/<env>/` beside that directory. The report is stored next to the receipt and written first. The receipt is written last, and a reader takes a receipt only together with its report. On disk, `receipts/` and `receipts/<env>/` are created one level at a time and never through a link.

`R` is the report of [`fluid verify --release SRC --out R`](./verify.md#key-options), whose `release` block names the release. A report that names another release, or none, is refused, and nothing is written.

The receipt holds:

- `code_digest` and `identity_digest`;
- each object verified, with its sha256 and S3 VersionId;
- the report's sha256 and counts;
- the CI run, with any credentials cut out of its URLs;
- the targets.

Its fields follow SLSA's [verification summary attestation](https://slsa.dev/spec/v1.1/verification_summary): `verifier`, `time_verified`, `resource_uri` and the result.

The result is `PASSED` when the report's verdict passes, the report checked the whole release (not one `--expose`), and every checked target reads back. Otherwise the result is `FAILED`, and a failed receipt is written too. The verdict is `fluid_build.api.report_verdict`, the rule [`datamesh-manager promote --verify-report`](./datamesh-manager.md) uses.

| Option | Meaning |
| --- | --- |
| `--report R` | The `fluid verify --release SRC --out R` report. Required. |
| `--env NAME` | Must be the environment the release was sealed for; that environment is the default. |
| `--target T` | Where the release went, repeatable. `s3://bucket/key#versionId` names an object version, since a key alone can change. `git+<repo>@<commit>` takes a full commit and is recorded, never checked. The repository URL is kept without user, password, query or fragment. |
| `--check-targets` | Reads each S3 target version back and records the checksums S3 holds for it (its sha256 when it has one), its ETag and its size. A version that is not there fails the receipt. One that cannot be read writes nothing, with exit `2`. |
| `--sign` | Also stores an in-toto Statement of the SLSA verification-summary type over the release's `release.json`, signed with cosign (keyless) into one bundle beside it (`<stem>.intoto.jsonl.sigstore.json`). It is signed before anything is written. Needs cosign 2.0 or later; sign and verify with the same major version, since 2.x and 3.x write different bundle formats. |
| `--sign-key REF` | With `--sign`: a cosign key, either a path or a KMS URI. |
| `--json` | Prints the receipt and the files written. |

Exit `0` `PASSED`, `1` `FAILED` or refused (nothing written), `2` cannot decide or a usage error (nothing written).

### `fluid runs receipt check`

`check SRC --env nonprod` verifies SRC, then reads the newest `nonprod` receipt for SRC's code digest. It passes when all of these hold:

- the receipt is `PASSED`;
- the report stored beside it is the one it names, and still passes;
- the `nonprod` release it names is there, intact, of that environment and of the same code.

It fails closed:

- a newest file there that is not a receipt fails the check, rather than letting it fall back to an older receipt;
- a receipt overwritten or deleted after it was written fails the check. The listing reads every version and delete marker, because Object Lock keeps versions, not keys. Reading receipts in S3 therefore needs `s3:ListBucketVersions` and `s3:GetObjectVersion`, and `--require-signed` also `s3:GetBucketObjectLockConfiguration`;
- in S3, a receipt of other code under this code's folder fails the check;
- a receipt of this code named later than now decides nothing (exit `2`): a recorder's clock is ahead, or the name is not its own;
- a listing past 50,000 entries decides nothing. A new commit, whose code digest starts a new folder, is the way on.

Whoever can write under `receipts/<env>/` can therefore also make the folder decide nothing, by adding a second version of an entry. That fails closed; a new commit gives a new code digest and a new folder.

The check never reads a release's `gates` or `provenance`.

It reports whether each object of both releases and of the receipt carries an Object Lock in force, read at the version it checked. `--require-locked` fails the check when one does not. A receipt whose lock has run out gates nothing, so the retention must cover the time from the earlier environment's check to the later deploy; the way on is a fresh check of the earlier environment. Never shorten the bucket's default retention while releases are gated on its receipts: a newer receipt would then lose its lock before an older one, and `s3:DeleteObjectVersion` alone could remove it and let the older receipt decide. Lengthening it is safe. Never move or expire receipts (a lifecycle rule included): in a versioned bucket that leaves a delete marker, and the check then fails for that code for good.

::: warning Who may write receipts
A receipt is only as trusted as whoever can write `receipts/<env>/`. Keep that prefix writable by the verifier's own identity only, never by a role that runs build code. Or sign receipts with `--sign` and pass `--require-signed` to `check` with the signer: `--verify-key REF`, or `--certificate-identity` and `--certificate-oidc-issuer` for keyless. A signature cannot show that a newer receipt was never there, so `--require-signed` implies `--require-locked` over the receipt, its report and its Statement, needs a bucket with Object Lock and a default retention, and decides nothing (exit `2`) for a release on disk. No writer of `receipts/<env>/` may hold `s3:DeleteObjectVersion`, `s3:BypassGovernanceRetention` or `s3:PutObjectRetention` there: with any of them a newer receipt could be removed while the older one is still locked. The signer must be one the build code cannot reach. Keyless, the certificate identity is the workflow, and any step in a job that can mint its OIDC token can sign as it, so record receipts in a separate job, or use a key only the verifier can use. The Statement beside the newest receipt must then verify with `cosign verify-blob` for exactly that signer. It must also name the receipt's own sha256, environment, code and identity digests, `PASSED`, and the `release.json` of the release it vouches for.
:::

Exit `0` passes, `1` does not, `2` cannot decide (a read failed, cosign is missing, or the release has no code digest). With `--json` it prints `status`, `reason`, `code_digest`, `receipt`, `receipt_release`, `locks` (each with `uri`, `version_id`, `lock`) and `ignored`.

`fluid runs status --release-dir` lists, under each release, the newest receipt of each environment for its code, picked as the check picks it.

## `fluid runs logs`

Read the logs a product left, filtered by component.

```bash
fluid runs logs bronze.crm_orders --component dlq --run-id 0101M3W8N4EGS716V5
fluid runs logs bronze.crm_orders --grep schema_drift
fluid runs logs bronze.crm_orders --component dlq --run-id 0101M3W8N4EGS716V5 --json
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--component {build\|infra\|server\|worker\|dlq}` | Which component's logs to read. Default `build`. |
| `--run-id ID` | The run whose dead-letter files to read. **Required for `dlq`**: without it the result is empty. Ignored for the other components. |
| `--grep TEXT` | Keep only lines that contain `TEXT`. A case-sensitive substring match, not a regular expression. |
| `--limit N` | Keep the last `N` lines of each log file. Default `1000`. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit a JSON array of `{timestamp, level, component, message}` objects. |

Where each component reads from:

| Component | Reads |
| --- | --- |
| `build`, `infra`, `server`, `worker` | `logs/<product-id>/<build>/<component>.log` for each build under the product. JSON lines with `timestamp`, `level` and `message` keys are parsed; any other line is returned as plain text. |
| `dlq` | Every `dlq/<run-id>/*.ndjson` file for the `--run-id` you give. Each line is returned as the message, unparsed. |

```text
2026-10-01T17:37:06Z  INFO   stream orders: 10 records
2026-10-01T17:37:08Z  WARN   stream refunds: schema_drift on amount
-  -      plain text line
```

That is `fluid runs logs bronze.crm_orders` over a `build.log` holding two JSON lines and one plain line. A line with no timestamp or level prints `-` in both columns.

As of 0.18.1, the CLI itself does not write the `.log` files; the `build`, `infra`, `server` and `worker` components show what is already in `.fluid/logs/`. The `dlq` component reads files the acquisition runners do write. When nothing matches, the output is `(no <component> logs for <product-id>)` and the exit code is `0`.

`--limit` and `--grep` act per file. `--grep 'schema_.*drift'` matches the literal text `schema_.*drift`, so it finds nothing here.

## `fluid runs diff`

Compare two runs of the same build: record counts, duration and state, overall and per stream.

```bash
fluid runs diff bronze.crm_orders \
  --build ingest_orders \
  --run-a 0101M3VM992GJ62H1F \
  --run-b 0101M3W8N4EGS716V5
```

```text
run_a: 0101M3VM992GJ62H1F
run_b: 0101M3W8N4EGS716V5
state_a: succeeded
state_b: partial
records_total_a: 8
records_total_b: 11
records_delta: 3
duration_a: 2.3
duration_b: 3.1
duration_delta: 0.8000000000000003
streams:
  -
    name: orders
    records_a: 8
    records_b: 10
    delta: 2
  -
    name: refunds
    records_a: 0
    records_b: 1
    delta: 1
error_a: None
error_b: stream refunds: 1 record routed to the DLQ
```

| Option | Description |
| --- | --- |
| `<product-id>` | The data product ID. Required. |
| `--build ID` | The build to diff within. Required. |
| `--run-a ID` | The baseline run. Required. |
| `--run-b ID` | The run to compare against it. Required. |
| `--state-root PATH` | The state directory. Default `./.fluid`. |
| `--json` | Emit the diff as JSON. |

With `--json`, the document has `run_a`, `run_b`, `state_a`, `state_b`, `records_total_a`, `records_total_b`, `records_delta`, `duration_a`, `duration_b`, `duration_delta`, `error_a`, `error_b` and `streams`, a list of `{name, records_a, records_b, delta}`. Every delta is `b` minus `a`, and a stream present in only one run counts as `0` in the other.

`runs diff` compares counts. It does not compare columns or schemas, so it cannot tell you that a column was added or removed.

Run IDs that do not exist are not an error. The diff comes back with zero counts, `null` states and an empty `streams` list, and the exit code is `0`. Check `state_a` and `state_b` before you read the deltas in a script.

## Which release was in force

*(since 0.37.0, [forge-cli #1035](https://github.com/Agenticstiger/forge-cli/pull/1035))* A job that forge does not run, such as an existing job on its own runner that Airflow schedules, leaves no run record. What it does leave is the sealed release that [`fluid ship --release-dir`](./ship.md#publishing-a-release) publishes at each deploy. `fluid runs status --release-dir` reads those releases and says which one was in force, and so which version of the code ran.

```bash
fluid runs status commerce.orders --release-dir releases
fluid runs status commerce.orders --release-dir releases --on 2026-10-14
fluid runs status commerce.orders --release-dir releases/prod-0412 --release-dir releases/prod-0413 --env prod --json
```

| Option | Description |
| --- | --- |
| `--release-dir DIR` | One release, or a directory of releases, read one level deep. Repeat the flag to read several. Giving it replaces the run-record view: `--build`, `--last` and `--state-root` are not used. |
| `--on YYYY-MM-DD` | The UTC day to answer for. Default: now. Only valid with `--release-dir`. |
| `--env NAME` | Answer only for the releases of this environment. Default: one answer per environment the releases name. An empty name is a usage error. Only valid with `--release-dir`. |
| `--json` | Emit JSON. |

Each environment is answered on its own: a `dev` release sealed between two `prod` ones is not what was in force in `prod`.

### What you see

For each environment, the command prints:

- the release **in force**: now, or at the start of the `--on` day. This is the latest intact release sealed before that moment.
- the releases **sealed during** the `--on` day, if any.
- for each release, its expose versions, its release id, when it was sealed, the run that sealed it, the environment, the forge version, the `code` line (revision, repository and ref) and its `bundle` digest.
- *On forge-cli `main`, not yet in a release ([forge-cli #1115](https://github.com/Agenticstiger/forge-cli/pull/1115)).* one `external` line for each file the release sealed with [`fluid ship --artifacts`](./ship.md#sealing-external-files): its name, kind and sha256, and the repository, ref and commit it was built from. With `--json`, each release has an `external` list with `name`, `kind`, `sha256`, `source` and `commit`.
- a "Not in force" block for later records that are not intact (see below).
- a `not read` line for each kind of entry that was skipped, with a count.

```text
commerce.orders: 2 sealed release(s) read
In force at the start of 2026-10-14:
  orders 1.4.0
  release  rel-0412
  sealed   2026-10-12T08:31:02Z   run 8841   env prod   forge 0.37.0
  code     3f9c1d2e... https://github.com/example/orders-jobs refs/heads/main
  bundle   sha256:...
Sealed during 2026-10-14:
  orders 1.5.0
  release  rel-0413
  sealed   2026-10-14T09:02:44Z   run 8870   env prod   forge 0.37.0
  code     a77b0c19... https://github.com/example/orders-jobs refs/heads/main
Records are read as written. 'intact' means a record's identity_digest matches its identity; it does not say who wrote the record, and its sealed time and source are outside that digest.
```

With `--json` the document has `product_id`, `on`, `releases_read`, `not_read` and `answers`. Each entry of `answers` is:

| Field | Meaning |
| --- | --- |
| `environment` | The environment name, or `null` for releases that record none. |
| `in_force` | The release in force, or `null`. |
| `during` | The releases sealed during the `--on` day (empty without `--on`). |
| `not_intact` | Later records whose identity digest no longer matches. |

A release object carries `path`, `product_id`, `sealed_at`, `release_id`, `expose_versions`, `environment`, `forge_version`, `run_id`, `source`, `bundle_digest` and `intact`; fields a record does not hold are left out.

### Intact and not intact

A release record carries an `identity_digest`. A record is **intact** when that digest matches the record's `identity`. The release in force is the latest intact one. A later record whose digest no longer matches is listed under "Not in force" (`not_intact` in `--json`) and is never in force. When no intact release was sealed by then, nothing is in force and the exit code is `1`.

`intact` is a consistency check, not authentication. Whoever can write a record can also compute its digest, and the sealed time and the source are outside the digest. Read the records from a place only your pipeline can write to.

### Exit codes with `--release-dir`

| Code | Meaning |
| --- | --- |
| `0` | At least one environment has a release in force or sealed during the day. |
| `1` | No release of the product was sealed by then, or none that is intact. |
| `2` | A bad `--on` day, a `--release-dir` that is not a directory or cannot be read, an empty `--env`, or `--on` or `--env` without `--release-dir`. |

### Limits

| Limit | Value |
| --- | --- |
| Entries read in one directory | 2,000. The "not read" line counts every entry past that. |
| Size of one `release.json` | 1 MB. A larger record is skipped and counted. |
| Links | Never followed. |
| Other products, or files that are not a release | Skipped and counted under `not read`. |

Text taken from a record is cleaned of control characters and cut, so a record cannot rewrite your terminal.

### What `release.json` holds

`fluid ship --release-dir` writes `release.json` (schema `fluid-release/1`) last into a directory that is then renamed into place and never changed. These parts of it are what `runs status` reads. *(since 0.37.0)*

| Field | Holds |
| --- | --- |
| `identity.expose_versions` | The version of each expose, by expose id. |
| `provenance.source` | `revision`, `repository` and `ref`, read from the CI system's own variables. |
| `identity.source` | *On forge-cli `main`, not yet in a release ([forge-cli #1116](https://github.com/Agenticstiger/forge-cli/pull/1116)).* The commit the CI built, as `uri` (`git+<repo>`) and `digest.gitCommit`. See [The code digest](./ship.md#the-code-digest). |
| `code_digest` | *On forge-cli `main`, not yet in a release ([forge-cli #1116](https://github.com/Agenticstiger/forge-cli/pull/1116)).* The digest of the code, the same for every environment of one commit and one lock. |
| `identity.external` | *On forge-cli `main`, not yet in a release ([forge-cli #1115](https://github.com/Agenticstiger/forge-cli/pull/1115)).* The external files the release sealed (`fluid ship --artifacts`): each one's `name`, `kind`, `digest.sha256`, and its `source` as `uri` (`git+<repo>@<ref>`) and `digest.gitCommit`. See [Sealing external files](./ship.md#sealing-external-files). |

`provenance.source` is filled from the first CI system whose run variable is set:

| CI system | Revision | Repository | Ref |
| --- | --- | --- | --- |
| GitHub Actions | `GITHUB_SHA` | `GITHUB_REPOSITORY`, as a URL on `GITHUB_SERVER_URL` | `GITHUB_REF` |
| GitLab CI | `CI_COMMIT_SHA` | `CI_PROJECT_URL` | `CI_COMMIT_REF_NAME` |
| CircleCI | `CIRCLE_SHA1` | `CIRCLE_REPOSITORY_URL` | `CIRCLE_BRANCH` |
| Azure Pipelines | `BUILD_SOURCEVERSION` | `BUILD_REPOSITORY_URI` | `BUILD_SOURCEBRANCH` |
| Bitbucket Pipelines | `BITBUCKET_COMMIT` | `BITBUCKET_GIT_HTTP_ORIGIN` | `BITBUCKET_BRANCH` |
| Jenkins | `GIT_COMMIT` | `GIT_URL` | `GIT_BRANCH` |

What is left out: a clone URL loses its user, password, query and fragment. Anything that is not a hex commit, a URL or `user@host:org/repo`, or a ref name is dropped. A credential, or a path on the runner, is never part of a release record. An scp-style address such as `host:org/repo` with no `user@` is dropped.

`provenance.run_id` is the pipeline's run id. The Spark runner stamps the same id and the release's bundle digest on every Iceberg commit: see [Commit stamps](../advanced/spark-iceberg-aws.md#commit-stamps).

### Guide: which version ran on that date

Use this for a job forge does not run. Keep one sealed release per deploy, then ask.

1. Seal a release at each deploy, into a directory you keep:

   ```bash
   fluid ship contract.fluid.yaml --release-dir releases/run-8870
   ```

2. Later, ask which release was in force on the day:

   ```bash
   fluid runs status commerce.orders --release-dir releases --on 2026-10-14
   ```

3. Read the `In force` block for the version and the `code` line for the revision. If the job writes Iceberg tables through forge's Spark runner, match a commit to its release with the `bundle` digest and `fluid.bundle-digest` in the table's snapshot summary: see [Commit stamps](../advanced/spark-iceberg-aws.md#commit-stamps).

See [`fluid ship`](./ship.md#publishing-a-release) for how a release is sealed.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The command ran, including a diff of run IDs that do not exist and logs with no matches. |
| `1` | `runs status` found no builds for the product. |
| `2` | A usage error: a missing required argument, an unknown subcommand, an invalid `--component`. |

With `--release-dir`, the codes are those of [Exit codes with `--release-dir`](#exit-codes-with-release-dir).

## See also

- [Source-aligned acquisition](../advanced/source-aligned-acquisition.md): what produces these run records
- [`fluid retention`](./retention.md): sweep run records past their horizon
- [`fluid stats`](./stats.md): aggregate cost across forge runs
- [`fluid ship`](./ship.md#publishing-a-release): seal the releases that `--release-dir` reads, and [publish them to S3](./ship.md#publishing-to-s3)
- [Spark to Iceberg on AWS](../advanced/spark-iceberg-aws.md#commit-stamps): the stamps on each Iceberg commit
- [Typed CLI errors](../advanced/typed-cli-errors.md): the error catalog
