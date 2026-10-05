---
title: Sovereignty
description: Where a data product's data may live, who may read it, and why those two rules are enforced at different moments by different gates.
---

# Sovereignty — residency the engine enforces

Most stacks treat data residency as documentation: a paragraph in a DPIA, a naming convention for buckets, a reviewer who is expected to notice that a Terraform module points at `us-east-1`. Nothing mechanical connects the intent to the infrastructure, so the control holds exactly as long as everyone remembers it.

A Fluid Forge contract declares residency as a field, and the CLI refuses to pass a contract that contradicts it. `sovereignty` is a top-level block in `contract.fluid.yaml`, versioned and reviewed with everything else, and **as of `0.15.0` it blocks by default** — no flag to remember, no opt-in.

This page explains what the block means and why it is enforced the way it is. For the field-by-field reference see [Governance & Policy](./governance-policy.md) and [`fluid validate`](/forge_docs/cli/validate.html).

## What the block declares

```yaml
sovereignty:
  jurisdiction: EU            # where the data must reside
  allowedRegions: [eu-west-1, eu-central-1]
  deniedRegions: [us-east-1]
  dataResidency: true         # default: true
  crossBorderTransfer: false  # default: false
  regulatoryFramework: [GDPR]
  enforcementMode: strict     # default: strict
```

Three different kinds of statement live in that block, and it is worth keeping them apart:

- **`jurisdiction`** is a *legal* claim — `EU`, `US`, `UK`, `CA`, `AU`, `JP`, `CN`, `IN`, `BR`, or the two catch-alls below. Forge resolves each expose's `binding.location.region` to a jurisdiction and compares (on GCP, `binding.location.location` is read the same way). The region table is derived from botocore's endpoint data for AWS and a vendored open dataset for GCP and Azure, plus a short hand-kept GCP supplement for the regions and dual-regions that dataset lacks. A region the table cannot place resolves to `Unknown`, which the strict mode refuses on a cloud binding (see [below](#a-cloud-binding-must-name-a-region-it-can-place)).
- **`allowedRegions` / `deniedRegions`** are *operational* lists, named region strings, evaluated without any jurisdiction lookup.
- **`dataResidency` and `crossBorderTransfer`** describe *movement* — whether the product's exposes may straddle more than one jurisdiction at all.

Jurisdiction here is **identity, not adequacy**. The UK and Switzerland hold GDPR adequacy decisions, so an EU→UK transfer is usually lawful; it is still a transfer to a third country, and a contract asking for `jurisdiction: EU` has not asked for the UK. London resolves to `UK`, and an EU-only contract bound there fails:

```bash
# jurisdiction: EU, binding region eu-west-2
fluid validate contract.fluid.yaml
# ❌  Region 'eu-west-2' (jurisdiction: UK) does not match required jurisdiction: EU
# exit 1
```

Adequacy is a different question and belongs in `transferMechanisms`.

### A block with no `jurisdiction` still constrains

`dataResidency` defaults to `true` and `crossBorderTransfer` to `false`, so a `sovereignty` block that names no jurisdiction at all is still saying something: *this product's exposes must all sit in one jurisdiction*. Two exposes, one in `eu-central-1` and one in `us-east-1`, fail on those defaults alone:

```bash
fluid validate contract.fluid.yaml
# ❌  Cross-border data transfer prohibited but multiple jurisdictions detected (EU and US)
# exit 1
```

Which is why the defaults matter more than they look. Declaring the block is the decision; the defaults then assume the strict reading of it rather than the permissive one.

## A cloud binding must name a region it can place

Since 0.17.0 the checker fails closed on AWS, GCP and Azure bindings. A binding with no region used to pass and land wherever the platform chose; a BigQuery dataset with no location lands in the `US` multi-region. Now, with a `sovereignty` block:

```bash
# jurisdiction: EU, allowedRegions: [europe-west1], gcp binding with no region
fluid validate contract.fluid.yaml
# ❌ Invalid FLUID contract (1 error(s)) (schema v0.7.5)
#  1. ❌  Binding declares no region, so where its data lives cannot be checked
# against the sovereignty policy (the platform would choose)
#    💡 Set binding.location.region to one of: europe-west1
# exit 1
```

The mode decides the outcome, as for any other finding: `strict` refuses, `advisory` warns and exits 0, `audit` logs.

A region the table cannot resolve to a jurisdiction is refused the same way under `strict` on a cloud binding, unless you vouch for it by naming it in `allowedRegions`:

```bash
# jurisdiction: EU, allowedRegions: [europe-west1], region: xx-unknown1
fluid validate contract.fluid.yaml
#  2. ❌  Region 'xx-unknown1' (jurisdiction: Unknown) does not match required
# jurisdiction: EU
#    💡 Use a region in the EU jurisdiction; if 'xx-unknown1' is one, name it in
# sovereignty.allowedRegions
# exit 1
```

Under `advisory` and `audit`, and on other platforms, an unresolvable region stays a warning.

How GCP locations resolve on 0.18.1:

| Location | Jurisdiction |
|---|---|
| `US`, `EU` (BigQuery and Cloud Storage multi-regions) | `US`, `EU` |
| `EUR4` | `EU` |
| `NAM4` | `US` |
| `ASIA1` | `JP` |
| `EUR5`, `EUR7`, `EUR8` (dual-regions that straddle jurisdictions) | `Unknown` |
| `ASIA` (multi-region) | `Unknown` |

A Pub/Sub topic's region becomes its `message_storage_policy.allowed_persistence_regions` and is checked like any other placement.

## `enforcementMode` decides severity, and `strict` is the default

The schema has always declared `enforcementMode` with `default: strict`. Since `0.15.0` the validator reads that default, and the mode is what decides the severity a violation carries — which in turn decides the exit code.

Given a contract pinning `jurisdiction: EU` with one expose bound to `us-east-1`:

```bash
fluid validate contract.fluid.yaml
# ❌  Region 'us-east-1' (jurisdiction: US) does not match required jurisdiction: EU
#    💡 Consider using regions in EU jurisdiction
# exit 1
```

| `enforcementMode` | Result on that contract |
|---|---|
| *(omitted)* — the schema default, `strict` | `❌` error, **exit 1** |
| `strict` | `❌` error, **exit 1** |
| `advisory` | `⚠️` warning, exit 0 |
| `audit` | informational, exit 0, nothing in the default output |

Silence is the thing to notice. `advisory` and `audit` both exit 0, so a contract that declares a policy and sets one of them reports clean while the binding sits outside its declared jurisdiction. That is the intended behaviour of those modes and the reason `strict` is the default: the fail-open setting has to be the one you typed on purpose.

One rule ignores the mode entirely. A region in **`deniedRegions` is an error in every mode**, including `advisory`:

```bash
# enforcementMode: advisory, deniedRegions: [us-east-1], binding region us-east-1
fluid validate contract.fluid.yaml
# ❌  Region 'us-east-1' is explicitly denied by sovereignty policy
# ⚠️  Region 'us-east-1' (jurisdiction: US) does not match required jurisdiction: EU
# exit 1
```

Both findings are reported, at different severities, from the same run. An operator naming a specific prohibition outranks a mode default, the same way an explicit denylist outranks absence from an allowlist.

## Two gates, at two different moments

This is the part most worth getting straight, because the two gates share a block and share nothing else. They answer different questions, run at different times, and are relaxed by different things.

| | Provision-time gate | Query-time gate |
|---|---|---|
| **Question** | May the data *sit* here? | May this *caller* read it? |
| **Compares** | each expose's `binding.location.region` → jurisdiction, against `sovereignty.jurisdiction` | the caller's **verified** jurisdiction claim, against `sovereignty.jurisdiction` |
| **Runs on** | `fluid validate` (always); `fluid plan --check-sovereignty` (run by stage 6 of a generated pipeline); `fluid generate iac` and `fluid apply` on AWS and GCP | every `tools/call` at `fluid mcp output-port serve` |
| **Since** | `0.7.1`, blocking by default since `0.15.0` | `0.15.0` |
| **Relaxed by** | `enforcementMode: advisory` / `audit` | `crossBorderTransfer: true` |

The query-time gate exists because the provision-time one is only half the promise. Before `0.15.0`, a contract declaring `jurisdiction: EU` refused to provision into `us-east-1` and then cheerfully answered a tool call from an agent sitting there. Nothing new is invented to close that: a contract saying `jurisdiction: EU` with cross-border transfer forbidden already *means* the data does not leave the EU, and serving it to a caller elsewhere is the border crossing it forbids.

The claim is admissible only if the HTTP transport's auth middleware verified it. A client that types `jurisdiction: "EU"` into its own MCP handshake satisfies nothing — self-attested identity is not evidence. The mechanism, the reason codes and the JWT claim mapping are in [Advanced → MCP output port](/forge_docs/advanced/mcp.html#caller-jurisdiction-enforcement-since-0-15-0).

One consequence surprises people, so it is worth stating plainly: a jurisdiction-pinned contract **cannot be served over stdio at all**. A pipe carries no headers, so no credential can supply a verified claim and every call would be denied. Rather than emit a denial per call, the server refuses once at startup and exits 2:

```bash
fluid mcp output-port serve contract.fluid.yaml --transport stdio
# fluid mcp output-port: refusing to serve over 'stdio'.
#   This contract pins sovereignty.jurisdiction to EU, so every tool call needs a
#   cryptographically verified caller jurisdiction.
# exit 2
```

The most common desktop-client setup is therefore the one configuration such a contract will not serve. That is the control working, not a bug.

## The escape hatches are not interchangeable

Because the two gates look like one feature, the natural assumption is that either relaxation loosens both. Neither does. `crossBorderTransfer: true` relaxes the query-time gate and **does not clear a provision-time jurisdiction mismatch**.

Take one contract — `jurisdiction: EU`, an expose bound to `us-east-1`, `crossBorderTransfer: true` — and run both:

```bash
fluid validate contract.fluid.yaml
# ❌  Region 'us-east-1' (jurisdiction: US) does not match required jurisdiction: EU
# exit 1

fluid mcp output-port serve contract.fluid.yaml --transport stdio
# output_port_serve_start        ← serves; no refusal
```

Remove `crossBorderTransfer: true` and the same server refuses with the exit-2 message above, while `fluid validate` fails identically either way.

It runs the other way too. `enforcementMode: advisory` downgrades the provision-time finding to a warning and leaves the caller gate **fully armed**:

```bash
# jurisdiction: EU, enforcementMode: advisory
fluid validate contract.fluid.yaml                                  # ⚠️ warning, exit 0
fluid mcp output-port serve contract.fluid.yaml --transport stdio    # refuses, exit 2
```

The asymmetry follows from what each field actually says. `crossBorderTransfer` is a statement about *readers*: this data is permitted to leave its jurisdiction. It says nothing about where the data is provisioned, so it cannot excuse a binding that contradicts the declared jurisdiction. `enforcementMode` is a statement about *how loudly the validator complains*, not about who may read — so it never reaches the caller gate.

If you want both relaxed, you have to say both things.

## `Global` and `Multi-Region` opt out of both

Two of the `jurisdiction` values are catch-alls, and both gates skip them:

```bash
# jurisdiction: Global (or Multi-Region), expose bound to us-east-1
fluid validate contract.fluid.yaml           # exit 0, no finding
fluid mcp output-port serve contract.fluid.yaml --transport stdio   # serves
```

For `Global` this is straightforward: the contract asserts no constraint. `Multi-Region` needs the special case for a mechanical reason — the caller gate is an equality test, and no caller's verified jurisdiction can ever equal the literal string `Multi-Region`, so without the carve-out a `Multi-Region` contract would refuse 100% of callers forever. The value means "several jurisdictions", not a jurisdiction by that name.

If you need a genuinely multi-jurisdiction product with real limits, name them in `allowedRegions` rather than reaching for `Multi-Region`.

## `apply` re-checks placements on AWS and GCP, and binds the plan by digest

`fluid generate iac` and `fluid apply` refuse an out-of-policy placement on AWS and GCP before any module is written or any resource is created:

- **GCP** (since 0.17.0) checks every location its OpenTofu plugin emits and every action its planner produces, including regions a resource inherits by default: the planner's `US` dataset default, a provider region a Cloud Scheduler job or staging bucket picks up. A KMS key ring or Data Catalog taxonomy is placed at its dataset's location and checked there.
- **AWS** checks the region its planner is configured with against the policy.
- **Local and Snowflake** have no such gate; `fluid validate` is the check.

The same contract with no region on its gcp binding, run through `generate iac`:

```bash
fluid generate iac contract.fluid.yaml --out infra/
# ❌ generate_iac_failed  [ERR_GENERATE_IAC_FAILED]
#   error: GCP placement refused by the sovereignty policy: customers: Binding
# declares no region, so where its data lives cannot be checked against the
# sovereignty policy (the platform would choose); dataset_crm: Region 'US' not in
# allowed regions list; dataset_crm: Region 'US' (jurisdiction: US) does not match
# required jurisdiction: EU; ...
# exit 1
```

No module is written. Under `advisory` the same run writes the module and logs each finding as a warning. An embedded-SQL build that reads from or loads into BigQuery checks those placements too, and fails with `EmbeddedSqlSovereigntyError`.

Separately, `fluid apply` guarantees that what runs is what was reviewed. Before any DDL executes it recomputes the plan's `planDigest` (and re-verifies `bundleDigest` when the plan carries one) and fails closed on a mismatch:

```bash
fluid apply plan.json --yes        # after editing plan.json by hand
#   kind: plan-tamper
#   error: plan.json has been modified since it was generated:
#          stored planDigest='sha256:…', recomputed='sha256:…'
# exit 1
```

The two digests it prints are yours, not ours. A `planDigest` is a function of your plan, so the property to rely on is *stable across re-runs, different after an edit*, never a particular hex string.

So the division of labour is: `validate` (and `plan --check-sovereignty` in CI) decides whether the contract's residency claim is consistent; on AWS and GCP the provider refuses to create a resource outside the policy, including where it fills in a default; and the digest guarantees the artifact reaching your cloud is the one that decision was made about.

## When `policy-compile` or `policy-apply` fails

The CLI links two policy errors to this page, although neither is a sovereignty finding. Both wrap whatever stopped the command. As of 0.18.1, `policy-compile` also prints a Python traceback above its error:

```bash
fluid policy-compile missing.fluid.yaml
# Outer exception: Contract/overlay not found: missing.fluid.yaml
# Traceback (most recent call last):
# ...
# ❌ policy_compile_failed  [ERR_POLICY_COMPILE_FAILED]
#   error: Contract/overlay not found: missing.fluid.yaml
# ...
# exit 1

fluid policy-apply bindings.json
# ❌ policy_apply_failed  [ERR_POLICY_APPLY_FAILED]
#   error: Expecting property name enclosed in double quotes: line 1 column 2
# (char 1)
# ...
# exit 1
```

| Error | Usual cause | Fix |
|---|---|---|
| `policy_compile_failed` | The contract or overlay path does not exist, or the contract does not load | Run `fluid validate <contract>` and fix what it reports. `policy-compile` reads `accessPolicy.grants`, not `agentPolicy`, whatever the suggestion line says |
| `policy_apply_failed` | The bindings file is missing or is not valid JSON, or the provider could not be built | Regenerate it with `fluid policy-compile <contract> --out <path>` |

`fluid policy-apply` provisions nothing on any provider as of 0.18.1; see [Governance & Policy](./governance-policy.md#fluid-policy-apply-enforces-nothing).

## Where to go next

- [Governance & Policy](./governance-policy.md) — `sovereignty` alongside `accessPolicy`, and how both compile to native cloud IAM
- [Agent Policy](./agent-policy.md) — the other half of what the MCP output port enforces on every agent call
- [`fluid validate`](/forge_docs/cli/validate.html) — flags, exit codes and the rest of the validation surface
- [Advanced → MCP output port](/forge_docs/advanced/mcp.html#caller-jurisdiction-enforcement-since-0-15-0) — the output-port mechanism: verified claims, reason codes, auth modes and JWT claim mapping
