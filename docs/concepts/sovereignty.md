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

- **`jurisdiction`** is a *legal* claim — `EU`, `US`, `UK`, `CA`, `AU`, `JP`, `CN`, `IN`, `BR`, or the two catch-alls below. Forge resolves each expose's `binding.location.region` to a jurisdiction and compares. The region table is derived rather than hand-maintained (botocore's own endpoint data for AWS, a vendored open dataset for GCP and Azure), because a table edited by hand goes stale silently and a stale sovereignty table is a governance bug, not a missing feature.
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
| **Runs on** | `fluid validate` (always); `fluid plan --check-sovereignty` (opt-in) | every `tools/call` at `fluid mcp output-port serve` |
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

## `apply` has no sovereignty gate — it has a digest

`fluid apply` performs **no sovereignty check of its own**. Hand it a plan built from a contract that `fluid validate` rejects with exit 1 and it will execute the actions without printing a single sovereignty finding.

That is deliberate, and it is the reason the plan is bound cryptographically. `apply` is not the place to re-litigate policy; it is the place to guarantee that what runs is what was reviewed. Before any DDL executes it recomputes the plan's `planDigest` (and re-verifies `bundleDigest` when the plan carries one) and fails closed on a mismatch:

```bash
fluid apply plan.json --yes        # after editing plan.json by hand
#   kind: plan-tamper
#   error: plan.json has been modified since it was generated:
#          stored planDigest='sha256:…', recomputed='sha256:…'
# exit 1
```

The two digests it prints are yours, not ours — a `planDigest` is a function of your plan, so the property to rely on is *stable across re-runs, different after an edit*, never a particular hex string.

So the division of labour is: `validate` decides whether the contract's residency claim is consistent, and `apply` guarantees that the artifact reaching your cloud is byte-for-byte the one that decision was made about. Put `fluid validate` in CI — or `fluid plan --check-sovereignty`, which shares the same checker and the same exit-1 behaviour under `strict` — and a jurisdiction violation is caught in review. An `apply` that runs against an unvalidated contract is a broken pipeline, not a gap in the policy engine.

## Where to go next

- [Governance & Policy](./governance-policy.md) — `sovereignty` alongside `accessPolicy`, and how both compile to native cloud IAM
- [Agent Policy](./agent-policy.md) — the other half of what the MCP output port enforces on every agent call
- [`fluid validate`](/forge_docs/cli/validate.html) — flags, exit codes and the rest of the validation surface
- [Advanced → MCP output port](/forge_docs/advanced/mcp.html#caller-jurisdiction-enforcement-since-0-15-0) — the output-port mechanism: verified claims, reason codes, auth modes and JWT claim mapping
