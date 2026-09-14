# Fluid Forge Docs Baseline: CLI `0.15.0`

**Release Date:** September 14, 2026
**Status:** Current stable docs baseline (supersedes [`0.14.0`](./RELEASE_NOTES_0.14.0.md))

This baseline covers **two CLI releases**: `0.14.1` (August 3) and `0.15.0` (September 14). `0.14.1`
did not receive its own docs pass, so both change sets are documented here.

## Headline

`0.15.0` is the **sovereignty enforcement** release, and `0.14.1` beneath it is the
**authorisation-correctness patch** that preceded it.

The headline is uncomfortable and it is the point: a set of data-residency controls that reported
clean while checking nothing now actually block. `sovereignty.enforcementMode` had failed in *both*
directions at once — `strict` could not block, because the only check that reads `jurisdiction`
hardcoded warning severity, while `advisory` could, because the cross-border check hardcoded error
severity. Both are now one function of the declared mode (#569). The engine's own defaults were the
permissive inverse of the schema's and now match them (#510). The region→jurisdiction table is
derived from the vendors' own data instead of typed out by hand, which is how it came to place
**London in the EU** and to treat Singapore and Seoul as pass-anything wildcards (#514). And the AWS
provider read its region allow-list out of `sovereignty.dataResidency`, a boolean, so the strict
setting raised `TypeError` and the permissive one skipped the check in silence (#513).

**A contract that passed [`fluid validate`](./cli/validate.md) on `0.14.1` can fail here, with no
contract change of yours.** That is the whole upgrade risk, and the checklist below is how to find
out before CI does.

Alongside it, `sovereignty` stops binding only provisioning: the **MCP output port enforces caller
jurisdiction at query time**, on by default, fail-closed, verified-claims-only, and derived from the
contract's own `sovereignty` block (#574, #576, #581). A jurisdiction-pinned contract therefore
**refuses to start** on the two deployments that could never satisfy the rule — the default stdio
transport, and HTTP with no auth mode configured. The `agentPolicy` gate moves behind one decision
function with a closed reason vocabulary and a portable policy digest (#568, #574).

Three more upgrade risks sit outside sovereignty, and none of them announces itself. The **MCP SDK
ceiling widens from `<2.0` to `<3.0`** (#604), so a fresh `pip install` now resolves the 2.x
generation — where a client can no longer self-attest identity through `clientInfo` extras.
**Git-backed federation digests are computed differently** (#587), so a `consumes[].upstreamDigest`
pinned on `0.14.1` against a `git_registry` upstream reads as drift and aborts `fluid apply`. And
**DataHub `customProperties` keys lose their dots** (#596) — `fluid.layer` becomes `fluid_layer` —
so any saved search, dashboard or ingestion rule keyed on the old spelling must be updated.

`pip install --upgrade data-product-forge`.

::: tip Who should upgrade
Anyone whose contracts declare a **`sovereignty`** block — every control in it behaves differently,
and mostly more strictly. Anyone serving an **MCP output port** (`0.14.1` closes two HIGH
authorisation bypasses; `0.15.0` fixes claim-mapping semantics that could silently disable the
`agentPolicy` gate and every `${caller.*}` row filter). Anyone passing **`--provider`** to
[`fluid generate iac`](./cli/generate-iac.md) or [`fluid apply`](./cli/apply.md). Anyone running
[`fluid validate-artifacts`](./cli/validate-artifacts.md) over **hand-authored or third-party ODCS**.
Anyone applying to **Snowflake** with `SNOWFLAKE_ACCOUNT` set — `fluid apply` reaches Snowflake again.
And anyone on **Python 3.10**, where `pip install` produced a package that could not import.
Anyone pinning **`consumes[].upstreamDigest`** against a `git_registry` upstream — the digest value
changes. Anyone publishing to **DataHub**, where the `customProperties` keys change spelling. And
anyone who pins the **`mcp` SDK** themselves, or ships a client that self-attests identity through
`clientInfo` extras.
:::

## Upgrade checklist

Work through this before you upgrade a CI lane, not after.

1. **Re-run `fluid validate` over every contract that declares `sovereignty`.** `strict` is the
   schema default and now blocks; the engine no longer defaults to the permissive inverse. Declaring
   `enforcementMode`, `dataResidency` and `crossBorderTransfer` explicitly restores the old
   evaluation.
2. **`jurisdiction: Multi-Region` needs no action.** It is a catch-all alongside `Global`, and
   check 3 skips both: no region resolves to `Multi-Region`, because it is not a place. While check 3
   hardcoded warning severity that mismatch was only a spurious warning; making `enforcementMode`
   mean what the schema says would have turned it into an error no region could satisfy, so both
   unconstrained values are now skipped outright — at provision time and at query time alike.
3. **Re-check any contract bound to London (`eu-west-2`, `europe-west2`), Singapore
   (`ap-southeast-1`, `asia-southeast1`) or Seoul (`ap-northeast-2`).** The first was mapped to `EU`
   and the rest to `Global`, which check 3 skips outright. All three now resolve correctly and can
   newly fail.
4. **If you serve an MCP output port for a contract that pins `sovereignty.jurisdiction`, change how
   you serve it.** `fluid mcp output-port serve --transport stdio` (the default) and
   `--transport http` with `FLUID_MCP_AUTH_MODE` unset now write a refusal to stderr and **exit 2**
   before binding. Serve over HTTP with `FLUID_MCP_AUTH_MODE=jwt`, or set
   `sovereignty.crossBorderTransfer: true` if the data may leave. See [`fluid mcp`](./cli/mcp.md) and
   the [MCP deep dive](./advanced/mcp.md).
5. **If you set `FLUID_MCP_JWT_CLAIM_MAPPING`, revisit it.** It now **merges over** the defaults
   instead of replacing them, so you can drop any default you were re-listing defensively — and you
   should map your IdP's jurisdiction claim, because `jurisdiction` is the one default whose absence
   *closes* the gate rather than widening it.
6. **Audit your `--provider` flags.** A `--provider` that contradicts the contract's `binding` is now
   `generate_iac_provider_mismatch` on both `fluid generate iac` and `fluid apply`. It was never a
   retargeting switch; retarget by editing `binding`.
7. **Expect `--allow-empty` where you relied on an empty module.** A resource-free OpenTofu module is
   now an error in its own right.
8. **If a CI lane runs `fluid plan --check-sovereignty`, expect it to be able to fail.** It printed
   `PASS` for a check it never ran and exited 0; it now returns a real verdict and **exits 1** on
   findings.
9. **Re-run `fluid validate-artifacts` over hand-authored ODCS.** Schemas are now validated with the
   dialect they declare, so the nine `unevaluatedProperties` guards in the vendored ODCS schema
   actually fire.
10. **On Python 3.10, reinstall.** The litellm pin is fixed; installs that could not import now can.
11. **Re-pin every `consumes[].upstreamDigest` that points at a `git_registry` upstream.** The
    git-backed digest was the raw-text fallback on every call and is now computed over the *parsed*
    contract, so the value changes. Until you re-pin, `fluid apply` aborts with `apply_consumes_drift`
    and **exit 1**, before any DDL. Clear `.fluid/federation/<workspace>.digest-cache.json` as well —
    it has no expiry check, so a machine that already holds an entry keeps returning the `0.14.1`
    value. `--no-verify-federation` is the escape hatch while you work through them. `catalog` and
    `http_registry` upstreams are unaffected.
12. **Update anything keyed on DataHub's dotted `customProperties`.** `fluid.layer` → `fluid_layer`,
    `fluid.productType` → `fluid_product_type`, `fluid.version` → `fluid_version`, plus a new
    `fluid_domain`. Structured properties keep their dotted `qualifiedName` — a different namespace,
    unchanged.
13. **Expect a fresh install to resolve MCP SDK 2.x.** The pin is now `mcp>=1.20,<3.0`. An existing
    environment does not move until you upgrade it, and pinning `mcp>=1.20,<2.0` yourself still works.
    The one behaviour difference is on the client side, and it is a client change, not yours:
    see *Changed — the MCP SDK ceiling moves from `<2.0` to `<3.0`* below.

::: warning Eight behaviour changes that can newly fail
1. **`sovereignty.enforcementMode` is honoured.** `strict` → error, `advisory` → warning, `audit` →
   info, applied to checks 2, 3 and 4, and `is_valid` is simply `not has_errors` in every mode. A
   strict, EU-declared contract whose binding region resolves elsewhere now **exits 1** where it
   validated clean (#569).
2. **The sovereignty engine's defaults now mirror the schema's**: `enforcementMode: strict`,
   `dataResidency: true`, `crossBorderTransfer: false`. They were advisory / false / true (#510).
3. **The region→jurisdiction table is derived from botocore and vendored vendor CSVs**: 31
   hand-written regions became 121 resolved, none left as `Global` or `Unknown`. London leaves the
   EU; Singapore and Seoul stop being wildcards (#514).
4. **A jurisdiction-pinned contract refuses to serve** over stdio, or over HTTP with no auth mode,
   with **exit 2** (#581).
5. **`fluid generate iac` / `fluid apply --provider` reject a provider that contradicts the
   binding**, and a zero-resource module is an error unless you pass `--allow-empty` (#546).
6. **ODCS artifact validation is genuinely stricter** — 2019-09 dialect, so unrecognised keys in
   `servers[]` and a missing `required: ["name"]` beside a `$ref` both fail now (#582).
7. **Git-backed federation digests change value.** A `consumes[].upstreamDigest` pinned on `0.14.1`
   against a `git_registry` upstream now reads as drift, and `fluid apply` **exits 1** before any DDL
   (#587).
8. **DataHub `customProperties` keys lose their dots** — `fluid.layer` → `fluid_layer`, and three
   siblings with it (#596).
:::

## What changed in `v0.15.0`

### Fixed — `sovereignty.enforcementMode` means what the schema says

The schema defines the modes in one sentence: strict blocks deployment, advisory warns, audit logs
only. Neither end held. Check 3 — the **only** check that reads `jurisdiction`, the field whose
documented purpose is validating `binding.location` against sovereignty intent — hardcoded
`severity="warning"`, so it could not block in any mode. In the other direction the cross-border
mismatch in check 4 hardcoded `severity="error"`, and `cli/validate.py` routes messages by their
rendered ❌ / ⚠️ / ℹ️ prefix, which no returned boolean could override — so an `advisory` contract
failed the build on a mode documented as "warn" (#569).

Severity is now `severity_for(mode)` in one place, and `is_valid` is one rule in every mode. The
three modes and what each one now does are documented in
[Governance & Compliance](./advanced/governance.md). Concretely, this contract:

```yaml
sovereignty:
  jurisdiction: EU            # enforcementMode defaults to strict
exposes:
  - exposeId: customer_events
    binding:
      platform: aws
      location:
        region: us-east-1     # not in the declared jurisdiction
        bucket: acme-events
```

```text
# 0.14.1
$ fluid validate contract.fluid.yaml
⚠️  binding.location.region 'us-east-1' is outside declared jurisdiction 'EU'
✅ Contract is valid
$ echo $?
0

# 0.15.0
$ fluid validate contract.fluid.yaml
❌ binding.location.region 'us-east-1' is outside declared jurisdiction 'EU'
$ echo $?
1
```

Two carve-outs are deliberate, and are not bugs. **`deniedRegions` stays an error in every mode**,
because an explicit prohibition outranks a mode default and because
[`fluid plan`](./cli/plan.md) must block where `fluid validate` exits 1. And **an unmappable region
stays a warning under strict**, because "unknown" is an inability to evaluate rather than a
violation.

### Changed — the engine's defaults are the schema's defaults, which makes them stricter

Every bundled schema from `0.7.1` to `0.7.6` declares `enforcementMode: strict`,
`dataResidency: true` and `crossBorderTransfer: false` on `$defs.sovereignty`. The engine defaulted
to advisory / false / true — the permissive inverse of all three — so a contract that declared a
policy and relied on the documented defaults was evaluated under the weakest possible settings. A
strict GDPR contract with exposes in `eu-west-1` *and* `us-east-1` printed `PASS`, because
`dataResidency` silently became false and the cross-border check was never entered (#510).

The three values are now constants read by both the engine and the display, pinned against the
bundled schema. This is the entry most likely to be felt on upgrade, because `fluid validate` shares
this engine with `fluid plan`: measured, an `allowedRegions` mismatch that warned now errors, and
`dataResidency: true` with exposes in two jurisdictions now trips the cross-border check where
`0.14.1` said nothing at all. **Declaring the keys explicitly restores the old evaluation.**

### Fixed — the region→jurisdiction table is derived from the vendors' own data

31 regions typed out by hand mapped `eu-west-2` and `europe-west2` — both London — to `EU`. The UK
left the EU in 2020, so a product declaring EU-only residency and deploying to either reported clean.
`Global` was worse, because check 3 skips any region whose jurisdiction is `Global`:
`ap-southeast-1` (Singapore), `ap-northeast-2` (Seoul) and `asia-southeast1` were **pass-anything
wildcards against every declared jurisdiction** (#514).

AWS regions now resolve through botocore's shipped `endpoints.json` — the vendor's own table, all
eight partitions, GovCloud and the EU Sovereign Cloud included — and GCP and Azure through CSVs
vendored from `dgl/cloud-regions` (ODbL-1.0, recorded in `NOTICE`). 31 hand-written entries became
**121 resolved and 0 hand-written**, with nothing left resolving to `Global` or `Unknown`. New AWS
regions now arrive by upgrading `boto3`, not by waiting for a FLUID release. Resolution is lazy and
memoised, so `fluid --help` imports no botocore and the startup-budget gate still passes.

`providers/aws/util/sovereignty.py` kept a **second** table that had drifted from the first on 16
regions — `eu-west-2` was `EU` there and `UK` in the canonical engine, and every `ap-*` collapsed to
one `APAC` — so `fluid validate` and the AWS provider could reach opposite verdicts on the same
contract. It now delegates. This is identity, not adequacy: the UK and Switzerland hold GDPR adequacy
decisions, but a contract asking for `jurisdiction: EU` has not asked for the UK, and adequacy
belongs in `transferMechanisms`, which the schema already carries. Also folded in:
[`fluid import`](./cli/import.md)'s scan emitted a `sovereignty` block that failed its own schema, so
it handed you a contract `fluid validate` rejected on the very next step.

### Fixed — AWS reads its residency allow-list from `allowedRegions`

`sovereignty.dataResidency` is typed **boolean** in every bundled schema — "must this data stay
inside the declared jurisdiction?" — and the region list lives in the sibling `allowedRegions`. The
[AWS provider](./providers/aws.md) util read the allow-list *out of* `dataResidency`, so `true` (the
schema default, and the value the repo's own `eu-customer-data-gdpr` example writes) raised
`TypeError: argument of type 'bool' is not a container or iterable`, while `false` skipped the check
in silence. The strict setting was the one that broke and the permissive one was the one that worked
(#513).

`deniedRegions` is now honoured — it was never consulted at all — and `allowedRegions` is enforced
whatever the boolean says, deliberately, because gating it would make the provider quietly more
permissive than the `fluid validate` stage before it. **A contract declaring
`allowedRegions: [eu-west-1]` and binding to `eu-south-1` was previously written to disk with exit 0
and now exits 1.** The two non-schema shapes that exist in the wild are still read as a fallback when
`allowedRegions` is absent, with a warning naming the right key, but never merged into it.

The same confusion reached the cloud tags, where joining the dict emitted its **keys**, so one tag
read `fluid:allowed_regions = "allowedRegions"` — and detective controls downstream, an AWS Config
rule or a tag-based SCP, key on exactly those tags.

Relatedly (#513): `fluid generate iac` **stops writing a module after the provider refused the
contract on sovereignty grounds.** The native planner ran inside a best-effort `except Exception`
that logged at DEBUG and returned an empty action list, so a contract bound outside its declared
jurisdiction logged the violation and emitted `main.tf.json` anyway, exit 0. "Best-effort" now means
a planner that could not *run*, not one that ran and refused. `AwsProvider._validate_sovereignty`
also caught only `SovereigntyViolationError`, and `ResidencyViolationError` is a **sibling** of it
rather than a subclass, so every residency refusal bypassed the handler and never emitted the
`sovereignty_violation` audit event — the one refusal an operator most needs in the log.

### Added — caller-jurisdiction enforcement at query time in the MCP output port

`sovereignty` used to bind provisioning and nothing else: a contract declaring `jurisdiction: EU`
refused to provision into `us-east-1` and then answered a tool call from a caller sitting there.
`derive_caller_jurisdictions` reads the constraint the contract already makes — a pinned
`jurisdiction` with `crossBorderTransfer` unset or false, the schema's own default — so the gate is
live on every `fluid mcp output-port serve` with **no flag to switch it on and none to switch it
off** (#574, #576, #581).

Every escape hatch is in the contract: `crossBorderTransfer: true`, `jurisdiction: Global` or
`Multi-Region`, or **no `jurisdiction` at all**, which is every contract that has never pinned one.
Those are entirely unaffected, policy digest included, and all 25 pre-existing conformance vectors
keep their exact digest.

The claim is admissible **only when verified**: `_resolve_verified_jurisdiction` reads the attributes
the HTTP auth middleware writes after it validates a JWT or mTLS identity, and never the caller's
self-attested `clientInfo`. A client typing `jurisdiction: "EU"` satisfies nothing and collapses to
the same `missing-caller-jurisdiction` denial as no claim at all. There is no no-auth fallback on
purpose, and matching is exact and case-sensitive — a verified `"eu"` against a contract pinning
`"EU"` is refused.

**Newly blocking.** Rather than denying every call one at a time, the port refuses at startup with
**exit 2** on the two deployments that could never satisfy the rule:

```text
$ fluid mcp output-port serve contract.fluid.yaml --expose customer_events
fluid mcp output-port: refusing to serve over 'stdio'.
  This contract pins sovereignty.jurisdiction to EU, so every tool call needs a
  cryptographically verified caller jurisdiction.
  'stdio' carries no headers, so no credential can supply one and every call would be denied.
  Serve it over HTTP with auth instead:
    FLUID_MCP_AUTH_MODE=jwt fluid mcp output-port serve --transport http
  (plus FLUID_MCP_JWT_ISSUER / _AUDIENCE / _JWKS_URL)
  Or set sovereignty.crossBorderTransfer: true if the data may leave EU.
$ echo $?
2
```

The second refusal is `--transport http` with `FLUID_MCP_AUTH_MODE` unset, where the middleware
short-circuits before stamping anything. Both messages name the jurisdiction and give the command
that fixes it. `jurisdiction` also joins the default JWT claim mappings, and it is the one default
whose absence **closes** the gate rather than widening it: an operator whose IdP calls the claim
something else locks themselves out of a jurisdiction-pinned contract until they map it.

### Added — `agentPolicy` decisions come from one function, with a closed reason vocabulary

`fluid_build/policy/decision.py` owns `decide()`, a `ReasonCode` str-enum over all **eleven**
outcomes, and `CHECK_ORDER` — precedence as **data** rather than as an accident of statement order,
on two stated principles: bounded surfaces first, and explicit denial beats absence from an
allowlist. The order is:

1. `tool-not-allowed`
2. `missing-caller-jurisdiction`
3. `in-denied-jurisdiction`
4. `not-in-allowed-jurisdictions`
5. `missing-model-identity`
6. `in-deniedModels`
7. `in-deniedUseCases`
8. `not-in-allowedModels`
9. `missing-use-case-with-allowlist`
10. `not-in-allowedUseCases`

Jurisdiction sits above the identity gates on a third principle: a legal constraint outranks a usage
constraint as the *reported* reason. If a caller may not receive this data at all, saying "your model
is not on the allowlist" describes the least important thing wrong with the request.

The wire values stay the existing kebab-case strings, so a caller comparing against
`"tool-not-allowed"` keeps working; what is new is that `ReasonCode("invented")` raises instead of
quietly becoming a reason nobody enumerated. `policy_digest()` is a `"<scheme>:<sha256>"` over the
RFC 8785 (JCS) canonical form of the effective rule lists, sorted and de-duplicated so authoring
order cannot change it, with `None` and `()` digesting differently because "no allowlist" and "allow
nothing" are different policies. 35 portable vectors ship **inside the wheel** at
`policy/data/vectors/agent-policy-vectors.json`, so a consumer can check their own gate without
cloning the repo. `rfc8785` is a new runtime dependency. The digest is reachable via
`OutputPortPolicy.policy_digest()` and `Decision.to_record()`, and #591 writes it into every
`data_access` audit record in this same release — see the audit-provenance entry below.

**One reported reason changes, and no verdict does** (#568). `check_tool_call` documented its
precedence as tool denylist > tool allowlist > model denylist > use-case denylist > model allowlist >
use-case allowlist, then evaluated the whole model stage before the use-case stage. So a request
whose model was merely absent from an allowlist and whose use case was **explicitly denied** reported
`not-in-allowedModels` where the prose directly above promised `in-deniedUseCases`. Exercised across
1,728 policy and request combinations, every allow and every deny is identical to `0.14.1`, and 48
reported reason codes differ — all of them `not-in-allowedModels` becoming `in-deniedUseCases`.
**Operators routing alerts or dashboards on those two strings should re-check their rules.**

### Fixed — every schema is validated with the dialect it declares

`Draft7Validator` was pinned at three call sites, and Draft 7 does not reject keywords it does not
recognise — it **ignores** them. The vendored `odcs-schema-v3.1.0.json` declares 2019-09 and guards
nine objects with `unevaluatedProperties: false`, so
[`fluid validate-artifacts`](./cli/validate-artifacts.md) reported ODCS documents clean that the
published standard rejects (#582). `servers[]` is the sharp case, because unlike the document root it
carries no `additionalProperties` of its own:

```yaml
servers:
  - server: prod
    type: snowflake
    TOTALLY_BOGUS_KEY: oops      # 0.14.1: 0 errors.  0.15.0: 1 error.
```

```text
# 0.15.0
$ fluid validate-artifacts dist/
❌ servers[0]: Unevaluated properties are not allowed ('TOTALLY_BOGUS_KEY' was unexpected)
```

Because Draft 7 also ignores keywords sitting alongside `$ref`, `schema[].properties[]` had lost the
`required: ["name"]` check that `SchemaProperty` carries beside its `$ref`. That fails now too,
naming the offending key.

**The change only tightens, and it is ODCS-only in practice.** No shipped schema uses a keyword
2019-09 or 2020-12 drops, so nothing that failed before now passes. Every ODCS document fluid itself
emits is unaffected — 20 documents generated across ten example contracts validate identically under
both dialects — so only **hand-authored or third-party** artifacts can newly go red. The FLUID
schemas were the same bug not yet triggered: they declare 2020-12 but have so far used only `$defs`,
which Draft 7 resolves as an ordinary JSON pointer, and 52 example contracts validate identically
either way, so `fluid validate` on a contract is unchanged today.

### Fixed — the ODCS `description` block is emitted as ODCS declares it

ODCS models `description` as an object of string fields — `purpose`, `limitations`, `usage` — while
FLUID models it as a single string, so converting needs a type check in both directions and only the
importer had one. The exporter wrapped **unconditionally** (#585). Given a mapping, it emitted:

```yaml
# 0.14.1 — an object where the ODCS schema declares a string. Invalid ODCS, no error.
description:
  purpose:
    purpose: Customer events for EU analytics
    limitations: No PII beyond hashed identifiers
    usage: Read-only, batch
```

```yaml
# 0.15.0 — the three fields as siblings, as ODCS declares them
description:
  purpose: Customer events for EU analytics
  limitations: No PII beyond hashed identifiers
  usage: Read-only, batch
```

A plain string is still wrapped as `{purpose: <string>}`, and an **empty** mapping now emits no
`description` key at all rather than an empty object. Both the `odcs/` and the per-port
`odps-bitol/*.odcs.yaml` outputs are fixed at once — see [`fluid odcs`](./cli/odcs.md).

Round-trips never saw it, which is why it hid: the importer stashes the original object in metadata
passthrough and the exporter's first branch reads it back, so only a caller rendering a document it
had **not** imported reached the broken `else`. When it was reached, installs carrying the optional
`vowl` validator (`fluid-build[odcs-strict]`) aborted
[`fluid generate artifacts`](./cli/generate-artifacts.md) with a provider error and wrote no
artifacts at all; elsewhere the invalid document was written with only a warning. The old shape was
already schema-invalid, so only a consumer written against the bug breaks.

### Fixed — `fluid plan --check-sovereignty` no longer prints `PASS` for a check it never ran

`AwsProvider` has no public `validate_sovereignty` hook, so the hook helper returned an empty
violation list — and an empty list rendered as `PASS`, on a contract `fluid validate` rejects with
two residency errors. The flag was also skipped outright when the provider failed to build, and a
hook that *raised* was indistinguishable from one that found nothing, because `invoke_hook` swallows
the exception and hands back its first argument (#510).

The helper now returns `None` for "no usable verdict", so `[]` means only "the hook ran and found
nothing". A new reporter resolves the provider hook, then the **built-in policy engine** — the same
checker `fluid validate` runs — before reporting `NOT CHECKED`, always naming which one answered:

```text
# 0.14.1 — the hook does not exist, so nothing was checked
Sovereignty check: PASS

# 0.15.0 — a real verdict, and it says where it came from
Sovereignty check: PASS  — source: built-in policy engine, enforcementMode=strict;
                            the aws provider has no sovereignty hook
```

On findings it prints a numbered list followed by `❌ Sovereignty check FAILED` and **exits 1**,
where `0.14.1` exited 0 (the plan file is still written). A contract that declares no `sovereignty`
block at all now prints `Sovereignty check: NOT CHECKED` and still exits 0. The flag stays opt-in and
off by default, but the non-zero exit is what makes it usable as a CI gate. See
[`fluid plan`](./cli/plan.md).

Also in #510: **the cross-border transfer check is order-independent.** `None` meant two different
things — "no baseline jurisdiction yet" and "this region has no known jurisdiction" — so the verdict
depended on the order exposes happened to be declared in: `eu-west-1` plus `eu-south-1` (both EU, the
latter unmapped) was blocked, the same pair reversed passed, and two unmapped regions in genuinely
different jurisdictions passed as clean. An unknown jurisdiction is now its own warning-severity
finding that never seeds and never trips the baseline. The check also moved out of the per-expose
loop — it is a property of the contract as a whole, and running it per expose emitted one duplicate
error per expose.

### Fixed — `--provider` that contradicts the binding is rejected before anything is written

`fluid generate iac <contract> --provider gcp` on an AWS- or local-bound contract emitted a
resource-free `main.tf.json` and exited 0. Adding `--validate` made it worse: `tofu validate`
genuinely reports success for a configuration with no resources, so the operator generated,
validated, saw green and had provisioned nothing. Three example contracts were worse than empty — an
S3-bound expose is shape-compatible with the GCP emitter, which produced a `google_storage_bucket`
named after the S3 bucket and carrying `location: us-east-1`, an AWS region that is not a valid GCS
location. Which is why the gate sits on the provider/binding **pair**, not on the output (#546).

**`--provider` was never a retargeting switch.** It disambiguates a contract that spans clouds or
declares none; retargeting is done by editing `binding`, as the new
`examples/sovereignty-platform-swap` corpus does across three clouds without ever passing the flag.
The requested provider must now be among the clouds the contract declares; a contract that declares
no cloud still falls through, since that is the case the flag exists for.

The same hole was open on **`fluid apply --provider`**, the command that actually provisions, which
reported `tofu plan: +0 ~0 -0` with exit 0. Both commands resolve through one resolver, so one gate
covers both, and the engine's broad exception fallback now re-raises this specific error instead of
quietly routing the same wrong target to the native engine.

### Changed — a resource-free OpenTofu module is an error, and `--allow-empty` opts out

Nothing downstream can catch one, so `fluid generate iac` now fails with `generate_iac_empty_module`
instead of printing a warning and exiting 0:

```text
$ fluid generate iac contract.fluid.yaml --out infra/
❌ emitted no gcp resources — the module at infra/main.tf.json would provision nothing.
  Check that the contract's `exposes[].binding` carries the gcp location fields the emitter needs,
  then re-run.
  Pass --allow-empty to emit the empty module anyway.
```

It is the backstop for the emit-when-derivable emitters, which can legitimately skip a resource on a
*matching* provider when a required binding input is absent. Pass `--allow-empty` when a module that
provisions nothing is genuinely intended; the run then prints an explicit warning that it provisions
nothing.

### Fixed — a GCP expose resolves to its target from the whole binding, not from `binding.format`

The emitter dispatched on five `format` spellings, two of which (`bigquery_view`, `gcs_bucket`)
appear in no shipped `fluid-schema-*.json`, while the one schema-valid Cloud Storage spelling
(`gcs_file`) matched none of them. So this validated clean and emitted **nothing** (#580):

```yaml
binding:
  platform: gcp
  format: gcs_file
  location:
    bucket: acme-raw
```

A silent no-op on a correctly auto-detected provider — which the new provider/binding cross-check
cannot catch precisely *because* the provider is right, and which the empty-module gate now turns
into a hard failure. `resolve_gcp_target()` is now the single dispatch: an explicit GCP `format`
wins, otherwise the shape of `binding.location` decides (`dataset` → BigQuery, `bucket` → Cloud
Storage, `topic` → Pub/Sub), and `emit`, `emit_data`, `discover_imports` and the new validate-time
gate all route through it. That brings [GCP](./providers/gcp.md) in line with AWS and Snowflake,
which already dispatch on the location shape and let `format` merely refine.

`discover_imports` also filtered on a literal platform string and lacked the emitter's `exposeId`
table-name fallback, so a table the emitter declared had no import block and a brownfield apply would
try to create one that already exists. Separately, the AWS plugin filtered `exposes[]` by comparing
`binding.platform` to the literal `"aws"`, so `platform: glue`, `s3`, `athena` or `redshift` — all
aliases the cloud detector accepts — auto-detected as AWS and were then skipped by every AWS filter.

### Fixed — `fluid verify` checks what `fluid apply` provisioned for a GCP binding

Stage 9 dispatched on the single literal `binding.format == "bigquery_table"`, which was equivalent
to asking the emitter right up until the emitter stopped keying on `format` alone. After that the two
stages disagreed about what an expose *is*, and the disagreement was not silent but wrong:
`{platform: gcp, format: csv, location: {project, dataset}}` is provisioned as a BigQuery table, yet
verify fell through to the local-file branch and returned `status: error` with "no location.path
declared" — diagnosing a missing file for a table that exists. `error_count` fails the run with or
without `--strict`, so a correctly applied target broke the stage for a nonsense reason (#580).

[`fluid verify`](./cli/verify.md) now asks the emitter's own resolver. A BigQuery table or view goes
to the BigQuery verifier, addressed by the name the emitter actually used — an expose with no
`location.table` previously built `project.dataset.`, which passed the three-part shape check and
then looked for a table named `""`. A GCS bucket, Pub/Sub topic or Iceberg warehouse reports
`unsupported`, which is "not checked" rather than "check failed". Non-GCP bindings, local files,
Snowflake and the legacy `format`-plus-`properties` dialect take the format chain unchanged.

### Added — a validate-time gate for GCP bindings the IaC emitter cannot resolve

`fluid validate` now reports a GCP expose that would emit no resource, resolved through the emitter's
own dispatch so the gate can neither block a contract that would have emitted nor wave through one
that emits nothing (#580). The split is deliberate, because `fluid validate` runs for contracts that
never reach `fluid generate iac`: only a format that *names* a container while omitting the location
key that container needs is an **error** — in practice `format: gcs_file` with no `location.bucket` —
and everything else that resolves to nothing is a **warning**, including the `other` escape hatch.
Formats with no `hashicorp/google` resource by design stay silent (`http_api`, `grpc_api`,
`kafka_topic`, a store on another platform), and Iceberg exposes are left to the
[Iceberg gate](./cli/validate.md) that owns a more specific message for the same input.

### Fixed — `fluid apply` reaches Snowflake again when `SNOWFLAKE_ACCOUNT` is set

From `snowflakedb/snowflake` 2.x — the only major the generated module pins, `~> 2.0` — the bare
`account` field is gated behind the `PROVIDER_CONFIGURATION_ACCOUNT_FALLBACK` experiment, and the
provider errors the moment it sees the legacy `SNOWFLAKE_ACCOUNT` variable, **whether or not** the v2
`SNOWFLAKE_ORGANIZATION_NAME` plus `SNOWFLAKE_ACCOUNT_NAME` pair is also present. The credential
overlay split the legacy variable into that pair but *added* the pair alongside it, so every
`tofu plan` against Snowflake failed with "the account field requires the
PROVIDER_CONFIGURATION_ACCOUNT_FALLBACK experiment to be enabled" (#511).

Measured against a live account on provider 2.19.0 and OpenTofu 1.12.0: legacy variable only,
rejected; legacy plus both v2 vars, rejected; v2 vars with the legacy variable blanked, plan
succeeds. The overlay now **blanks** `SNOWFLAKE_ACCOUNT` in the environment handed to `tofu` once a
complete v2 identity is available, whether you supplied it directly or it was derived from the
`<org>-<account>` form — blanked rather than removed, because callers apply the overlay with
`env.update()`, which cannot delete, and an empty value reads as unset to the provider.

**No contract or configuration change is needed:** keep setting `SNOWFLAKE_ACCOUNT` in the standard
`<org>-<account>` form and you go from failing to working. The one shape that still cannot plan is a
bare account locator with no organisation (`xy12345`), which deliberately keeps its legacy value so
the provider's actionable error survives; set the two v2 variables, or opt into the experiment. This
is the IaC/apply path only — `SNOWFLAKE_ACCOUNT` remains valid for source credentials, see the
[credential resolver](./advanced/credential-resolver.md) and
[environment variables](./advanced/environment-variables.md).

### Fixed — `pip install` on Python 3.10 produces a package that can import again

litellm 1.98.0 added a module that imports `NotRequired` straight from `typing`, which landed there
only in 3.11 (PEP 655), so merely importing litellm raised `ImportError` on 3.10 — while litellm's own
metadata still declared `requires_python ">=3.10,<3.15"`. litellm is a **core** dependency, not an
extra, and 3.10 is advertised in both `requires-python` and the classifiers, so this broke installs
and not just the red 3.10 leg of the test matrix (#555).

The pin is now split on an environment marker: `litellm>=1.83.7,<2` on 3.11 and newer,
`litellm>=1.83.7,<1.98` below it — bisected against real wheels, with 1.97.0 the newest that imports
clean on CPython 3.10. The `>=1.83.7` floor is unchanged on both branches, so the CVSS 9.3
SQL-injection fix that floor exists for stays in force and the compromised 1.82.7 / 1.82.8 PyPI
artifacts stay excluded.

### Added — a runnable sovereignty and platform-swap example corpus

`examples/sovereignty-platform-swap/` carries one contract for `analytics.eu.customer_events_v1`
compiled against AWS, Google Cloud and Snowflake with the `binding` block as **the only difference
between the three files**, plus a README that walks `validate` → `policy-check` → three
`generate iac` runs → the ODPS/ODCS export, with a cleanup step (#556). Re-run from this checkout,
the AWS binding emits three resources (`aws_s3_bucket`, `aws_glue_catalog_database`,
`aws_glue_catalog_table`), GCP two (`google_bigquery_dataset`, `google_bigquery_table`) and Snowflake
three (`snowflake_database`, `snowflake_schema`, `snowflake_table`). The contracts declare
`fluidVersion 0.7.6`, a preview version: validatable because they name it explicitly, and still never
the default for an untagged contract. This is also the documented way to **retarget** a product across
clouds, which `--provider` never was.

### Changed — the MCP SDK ceiling moves from `<2.0` to `<3.0`

`mcp` is a core dependency, not an extra, so `pip install data-product-forge` resolves the **2.x**
generation from here on. An existing environment does not move until it is upgraded, and pinning
`mcp>=1.20,<2.0` yourself still works and is still supported.

The dual-support seam shipped in `0.14.1` (#492); what changed is the audit that lets the ceiling
follow it. `tests/test_mcp_sdk_rename_guard.py` parses every module that imports the SDK or lives in
forge's own MCP packages and asserts that none of the twelve renamed field names it tracks is read by
its camelCase spelling — a read that on 2.x returns the attribute default instead of raising, so an
error would read as success and a tool schema as empty. It also bans a `model_dump()` on an SDK model
without `by_alias=True`, which on 2.x emits snake_case keys a peer does not recognise. That is a
static scan rather than a behavioural proof, and the drift canary supplies the rest: its `range-max`
leg now installs `mcp>=1.20,<3.0`, resolves to 2.x, is no longer warn-wrapped, and asserts which SDK
major it actually got.

::: warning One behaviour difference survives the widening, and it is client-side
On SDK 1.x a client can self-attest identity — `model`, `useCase`, tenant attributes — as **extra
fields on `clientInfo`**, because v1's `Implementation` model is `extra="allow"`. **2.x drops unknown
fields at wire-parse.** Forge's own clients go through `_mcp_compat.self_attesting_client_kwargs` and
are unaffected, but a third-party client hard-coded to that shape stops being attested, with no error
raised. Move those fields to the client's declared capabilities under `experimental.fluid`, which
both generations parse. Self-attested identity does not bind at all when authentication is enforced
(#492), so this reaches only the stdio / no-auth path (#604).
:::

### Fixed — anticipated `forge_run` failures reached the IDE as a generic string on SDK 2.x

All six raise sites in the `forge_run` tool used a bare `RuntimeError`. SDK 1.x passed the message
through intact; 2.x treats anything that is not the SDK's own `ToolError` as a crash and substitutes
`Error executing tool forge_run`. The call still returned `isError: true`, so nothing looked broken —
the only thing lost was the part that helped. An operator on an IDE that does not advertise the
`sampling` capability got that generic sentence instead of the message naming the capability and its
two ways out, `mode='blank'` or shelling out to `fluid forge --agent --blank`.

All six now raise the SDK's `ToolError` through `_mcp_compat.get_tool_error()`, since the class moved
package between generations (`mcp.server.fastmcp.exceptions` on 1.x,
`mcp.server.mcpserver.exceptions` on 2.x). `forge_run` is the only tool on that server that raises,
so this is the whole surface, and SDK 1.x behaviour is unchanged (#602).

### Fixed — git-backed federation digests were the raw-text fallback, and the value changes

`_fetch_digest_via_git` imported `compute_contract_digest` inside a `try/except`, and that function
existed nowhere in `fluid_build` — not at `v0.14.1`, not at the `0.15.0` branch point. Every call
therefore took the except branch and hashed the raw contract bytes. A raw-text hash makes key order,
indentation, quoting style, comments and CRLF all look like upstream drift, which is precisely the
thing `upstreamDigest` pinning exists to tell apart from a real change.

`compute_contract_digest` now exists and is imported at module scope, hashing the **parsed** mapping
as NFC-normalised, sorted, compact JSON and sharing one canonical form with `compute_plan_digest`.
You can reproduce it outside fluid:

```bash
yq -o=json '.' contract.fluid.yaml | jq -cSj '.' | shasum -a 256
```

An unparseable upstream contract returns `None`, which the caller escalates to a violation — so
federation fails closed rather than degrading to a weaker digest.

::: warning Upgrade action, and a silent one
For a `git_registry` upstream, a `consumes[].upstreamDigest` pinned against the old value now reads
as drift: `fluid apply` aborts with `apply_consumes_drift` and **exit 1**, before any DDL. Re-pin
those rows, or pass `--no-verify-federation` while you do. Two caveats. The per-workspace cache at
`.fluid/federation/<workspace>.digest-cache.json` has no expiry check, so a machine already holding
an entry keeps returning the `0.14.1` value until it is cleared. And only `git_registry` is affected
— `catalog` and `http_registry` upstreams read a digest off the remote (#587).
:::

### Fixed — a contract published to a default DataHub install was readable nowhere

One commit shipped two contradictory specifications, name for name: the unit suite asserted that
`fluid_contract`, `odps_spec` and the ODCS blob were **forbidden** in `customProperties`, the
integration suite that they were **required**. The unit suite ran on every pull request and pinned
the implementation; the integration suite needed a live GMS and had never once run, so the
contradiction survived unnoticed.

Neither was right. The "link, don't inline" design rests on a spec URL that is `None` unless
`spec_source_base_url` is configured — a field set by no factory and documented nowhere — while
`DataContract.rawContract`, the other proposed home, is absent from the OSS GraphQL schema. So on a
default install the contract was neither inlined, nor linked, nor readable. `_specs_are_linkable` now
states the rule in one place: large YAML is **linked** when a base URL exists and **inlined** when it
does not. Verified against a real DataHub OSS GMS (Quickstart v1.5.0.6).

::: warning Key rename to know about
`fluid.layer` → `fluid_layer`, `fluid.productType` → `fluid_product_type`, `fluid.version` →
`fluid_version`, plus a new `fluid_domain`. This is the underscore spelling every other emitter
already uses — DataHub was the only one using dots — so an analyst now sees the same keys whichever
catalog they browse. Any saved search, dashboard or ingestion rule keyed on the dotted names must be
updated. **Structured properties keep their dotted `qualifiedName`**: a different namespace,
unchanged. Expect larger entity payloads too — with no `spec_source_base_url` set, the dataset aspect
carries `odcs_contract` and the DataProduct aspect carries `fluid_contract` and `odps_spec` inline
(#596).
:::

### Added — the MCP gateway's audit record names which rules produced a decision

`policySource: contract` cannot distinguish the contract before an `allowedModels` edit from the
contract after it, so once the contract moved on, a denial was no longer reconstructable from its own
record. Every `data_access` event, allow and deny alike, now carries `policyDigest` — a
`jcs-sha256:<hex>` over the RFC 8785 canonical form of the effective rule lists, which hashes
identically however the YAML was written, and is the same digest the conformance vectors publish.

**Additive:** one new key, nothing renamed, retyped or removed, so only a reader validating against a
closed key set notices. It completes the digest #568 introduced, which until now was written into no
record (#591).

### Added — an ODCS contract can be read back out of the OpenMetadata catalog

The registrar could publish an ODCS document and not retrieve one, so a contract held in the catalog
could not drive `plan` / `apply`. `fetch_odcs_contract(fqn)` closes the read half. It prefers the
table's `extension.odcs_contract`, preserved verbatim, over OpenMetadata's native ODCS export, whose
converter drops `servers` and six other top-level blocks
([open-metadata/OpenMetadata#30493](https://github.com/open-metadata/OpenMetadata/issues/30493)), and
keeps that route as the fallback for a contract fluid did not publish.

**No command calls it yet.** This is the library half, and nothing in the CLI behaves differently
(#588).

### Also in `0.15.0`

- **Release image:** two CPython `tarfile` CVEs are suppressed in `.grype.yaml` with their
  reachability argument recorded — the single `extractall` call is guarded by `_safe_tar_members`,
  which raises on symlink and hardlink members, and no streaming (`"r|"`) mode is used anywhere. Both
  are fixed only in a CPython pre-release, so no stable base image clears them, and `0.14.1`
  published to PyPI while its GHCR job failed the gate on them (#501).
- **The wrong legal entity no longer ships in the container image or on the docs site.** `0.14.1`
  renamed the maintainer to **Agentics Transformation Limited** across `LICENSE`, `NOTICE`,
  `pyproject.toml` and the markdown docs, but two published surfaces were missed because neither is a
  file a docs linter would open: `Dockerfile`'s `org.opencontainers.image.vendor` label, so every
  image pushed to `ghcr.io` since carried "Pty Ltd" as vendor metadata, and the footer of this docs
  site. PyPI package metadata was already correct (#561).
- **The Apache-2.0 notice is complete in every source file that carries one.** 346 tracked files held
  a header truncated mid-boilerplate, dropping the warranty and liability disclaimer Apache-2.0's
  appendix asks to be attached. **No licence terms changed** — the licence is still Apache-2.0, the
  copyright line is untouched, and across all 358 files touched the diff contains zero non-comment,
  non-blank lines (#493).
- **CI and internal:** seventeen pinned-action bumps, a terminology gate in the lint job, a BigQuery
  emulator that seeds its full project set, first live-cloud GCP coverage for `fluid verify`, and the
  multi-language MCP conformance nightly passing for the first time since it was added — every defect
  in that last one was in the harness rather than the gateway. The Go and Rust clients attest no
  caller identity at all, so their deny scenarios passed vacuously; both are gated off behind
  `RUN_MULTILANG_GO_RUST` rather than deleted (#502–#508, #512, #521–#525, #547, #549, #550, #552,
  #561–#567, #584, #600, #603).
- **Internal, no runtime change — the weekly model-catalog refresh fetches from OpenRouter and needs
  no API key.** `scripts/update_model_catalog.py` is maintainer tooling: pruned from the sdist and
  imported by nothing in `fluid_build`, so no credential is ever asked of a user and the CLI makes no
  such call. The old host is undeployed, so the job could not have worked with or without the key it
  asked for. A promoted model with no catalog entry is now marked **incapable rather than unknown** —
  capabilities come from `litellm.model_cost` read in-process, falling back to a per-provider
  defaults table wherever litellm omits a flag, because an omitted flag means "no data" and not
  "cannot". `fluid_build/cli/llm_models.json` is byte-identical to `0.14.1`: this lets a refresh be
  *proposed*, it is not one (#593, #594).
- **Test and CI evidence that had been reporting green while proving very little.** The emulated
  integration lane started LocalStack but never the GCP emulator stack it is named for — measured on
  one commit, 3 passed / 53 skipped became **17 passed / 38 skipped**, keyless — and it had not run at
  all since 2026-07-13; it now runs nightly, with `scripts/ci/assert_lane_coverage.py` failing it
  unless every provisioned area contributed a passing test. The fourteen AWS `tofu apply` round-trips
  in `tests/iac/test_iac_aws_localstack_e2e.py` had never executed in CI anywhere, because the only
  workflow referencing them declares no `environment:` and so could never read the token; running
  them for the first time turned up a missing `/var/run/docker.sock` bind-mount and one Lake
  Formation round-trip that has never passed under LocalStack, now `xfail(strict=False)` with the
  upstream issue written down rather than skipped quietly. Snowflake is exercised over the **real
  wire protocol** for the first time, keyless, against fakesnow's server — the in-process
  `fakesnow.patch()` test could cover none of that, because it replaces the connector rather than
  talking to it. Two suites flaky under `-n auto` were fixed by patterns already in the repo, and
  `iac-tests.yml`'s two Stage 3 jobs are gated on a repository variable instead of failing nightly
  for credentials nobody has set (#590, #595, #597, #598, #601, #605).

## What changed in `v0.14.1`

`0.14.1` was a correctness and security patch: the MCP output port works against both generations of
the MCP SDK, two authorisation bypasses in that port are closed, and the project's legal entity is
named correctly across the distributed files. It shipped to PyPI on August 3 without a docs pass.

### Changed — the MCP output port supports MCP SDK 1.x and 2.x

`mcp` 2.0.0 renamed `FastMCP` to `MCPServer`, inverted the lowlevel `Server` registration API from
decorators to `on_*` constructor handlers, removed `create_connected_server_and_client_session`, and
renamed model fields from camelCase to snake_case at the attribute level. All generation branching is
confined to one new tier-0 leaf, `fluid_build/_mcp_compat.py`, which probes with `find_spec` rather
than importing `mcp` at module scope, so the `fluid --help` startup budget is preserved (#492).

Twelve `getattr`-with-default camelCase reads were failing **silently** under 2.x — errors reading as
success, tool schemas as empty — and now route through a dual-name accessor. Verified green against
both `mcp` 1.29.0 and 2.0.0, including a live end-to-end run of `fluid mcp output-port serve` over
HTTP/SSE under 2.0.0. The dependency pin stays `mcp>=1.20,<2.0` in `0.14.1` and the drift canary
stays warn-only until the 2.x leg has a track record — `0.15.0` widens the ceiling to `<3.0` and
makes that leg blocking (#604, above).

### Fixed — the legal entity name

Corrected across `NOTICE`, `LICENSE`, `pyproject.toml` and repository docs: the project is maintained
by **Agentics Transformation Limited** (Ireland); earlier files misnamed the entity as "Pty Ltd". The
trademark notice now correctly asserts an unregistered mark rather than claiming a registration. Two
surfaces were missed and are fixed in `0.15.0` — see above.

## Security — across both releases

- **Two HIGH authorisation bypasses closed in the MCP output port** (`0.14.1`, #492). Verified caller
  attributes (JWT/mTLS) and self-attested ones were flattened into a single dictionary, so the
  "cryptographic identity wins" rule held only for the keys a claim mapping happened to emit. A
  caller could therefore **(a)** self-attest any `rowFilter` the mapping did not cover — including
  another tenant's value, turning a fail-closed denial into an attacker-chosen row-level-security
  predicate — and **(b)** self-attest `model` and `useCase` past the `agentPolicy` gate whenever the
  mapping omitted them, which any custom `FLUID_MCP_JWT_CLAIM_MAPPING` did, since it *replaced* the
  defaults rather than extending them. The flattening predated the SDK port and was reachable on SDK
  1.x through `clientInfo` extras. Fixed by reading the `fluid_auth_kind` stamped by the transport
  middleware but never consulted: when authentication is enforced, only verified claims bind, and
  dropped self-attestations are logged at WARNING naming each one. The no-authentication path is
  unchanged. Five regression tests pin all four exploit shapes plus a no-auth control.
- **`FLUID_MCP_JWT_CLAIM_MAPPING` merges over the default claim mappings instead of replacing them**
  (`0.15.0`, #574). `AuthValidator.from_env` assigned the parsed value wholesale, so an operator who
  mapped one extra claim silently dropped `sub`, `model`, `use_case` and `tenant_id`. That is not
  cosmetic: `model` and `use_case` are the inputs to the `agentPolicy` gate, so losing them **turned
  that gate off**, and `sub` / `tenant_id` are what `${caller.*}` row filters interpolate, so losing
  them **emptied every row-level predicate** — with no error, and a server still reporting healthy.
  `0.14.1` named this replacement semantics as the reason a custom mapping could be self-attested
  past; it is now fixed at the source. The defaults are `sub`, `model`, `use_case`, `tenant_id` and —
  new in `0.15.0` — `jurisdiction`, exported as `DEFAULT_JWT_CLAIM_MAPPINGS`. Mapping a default away
  explicitly still works; what no longer happens is losing one by accident while adding something
  unrelated.
- **Integration CI jobs no longer inherit a token that mints cloud credentials** (`0.15.0`, #586).
  `integration.yml` declared `id-token: write` and `issues: write` at the workflow level, and a job
  with no `permissions:` block of its own inherits the whole workflow grant — so all eight jobs held
  both, while only three need either. `id-token: write` is not a convenience flag: it federates into
  GCP via Workload Identity and assumes an AWS IAM role. It mattered most for
  `multi-lang-mcp-conformance`, which fetches and executes third-party code at build time. The
  workflow level is now the floor (`contents: read`), and the three jobs that need more each declare
  the one extra capability their own steps call. Five jobs drop to the floor, none gains anything, and
  the release workflow was not affected.

## Compatibility

- **No breaking changes to the contract schema.** `0.7.5` remains the stable default; `0.7.6` stays
  **preview**, opt-in via `fluidVersion: "0.7.6"`, and `fluid version` now prints it as
  `0.7.6 (preview)`.
- **`sovereignty` behaviour changes in both directions.** `strict` now blocks where it could not, and
  `advisory` now warns where it wrongly failed the build. `deniedRegions` remains an error in every
  mode, by design.
- **Contracts that declare `sovereignty` but omit its keys are judged under the schema's stricter
  defaults.** Declare `enforcementMode`, `dataResidency` and `crossBorderTransfer` explicitly to
  restore the previous evaluation.
- **`jurisdiction: Multi-Region` is a catch-all and needs no action.** Both unconstrained values,
  `Global` and `Multi-Region`, are skipped by check 3 at provision time and by the caller gate at
  query time. No region resolves to either.
- **Contracts that never pin `jurisdiction` are entirely unaffected** by the MCP caller-jurisdiction
  gate, policy digest included.
- **`fluid mcp output-port serve` exits 2 at startup** for a jurisdiction-pinned contract on
  `--transport stdio`, or on `--transport http` with `FLUID_MCP_AUTH_MODE` unset.
- **The MCP SDK pin is now `mcp>=1.20,<3.0`.** A fresh install resolves 2.x; an existing environment
  does not move until it is upgraded, and pinning `mcp>=1.20,<2.0` yourself still works. A
  third-party client that self-attests identity through `clientInfo` extras stops being attested on
  2.x — declare those fields under `experimental.fluid` in the client's capabilities instead.
- **Git-backed federation digests change value.** Re-pin `consumes[].upstreamDigest` for every
  `git_registry` upstream and clear `.fluid/federation/<workspace>.digest-cache.json`. `catalog` and
  `http_registry` upstreams are unaffected.
- **DataHub `customProperties` keys lose their dots**: `fluid.layer` → `fluid_layer`,
  `fluid.productType` → `fluid_product_type`, `fluid.version` → `fluid_version`, plus a new
  `fluid_domain`. Structured properties keep their dotted `qualifiedName`.
- **The MCP gateway's `data_access` audit record gains a `policyDigest` key.** Additive — nothing is
  renamed, retyped or removed, so only a reader validating against a closed key set is affected.
- **`agentPolicy` verdicts are unchanged; 48 of 1,728 reported reason codes are not.**
  `not-in-allowedModels` becomes `in-deniedUseCases` when both apply. Re-check alert routing that
  keys on those strings.
- **`fluid generate iac` and `fluid apply` reject a `--provider` that contradicts the binding**, and
  a zero-resource module is an error unless `--allow-empty` is passed.
- **`fluid validate-artifacts` is stricter on ODCS.** Documents fluid emits are unaffected;
  hand-authored and third-party artifacts can newly fail, each error naming the unexpected key.
- **ODCS `description` output shape changed** for callers rendering a document they did not import.
  The old shape was already schema-invalid, so only a consumer written against the bug breaks.
- **`fluid verify` reports `unsupported` rather than `error`** for a GCS bucket, Pub/Sub topic or
  Iceberg warehouse on a GCP binding. That is "not checked", and it no longer fails the stage.
- **Python 3.10 installs are fixed** by an environment-marked litellm pin. No action beyond
  reinstalling.
- **New runtime dependency:** `rfc8785`, for the canonical JSON the policy digest is computed over.
- **SDK / custom-scaffold:** `data-product-forge-sdk 0.10.0` (unchanged),
  `data-product-forge-custom-scaffold 0.4.1`.
- **Install:** `pip install --upgrade data-product-forge` → `0.15.0`.
