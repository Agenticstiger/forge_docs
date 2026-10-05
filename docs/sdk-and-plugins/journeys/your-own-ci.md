# You have your own CI/CD setup, no problem

Your platform team already maintains GitLab CI templates / GitHub Actions workflows / Jenkinsfiles that encode your org's conventions: how to authenticate to the cloud, what tests to run, when to require approvals, which secrets to inject. You don't want `data-product-forge` to overwrite any of that. You want it to **emit your existing templates**, with values pulled from each contract.

This guide walks through that pattern end to end. By the end you will have:

- A small **scaffold bundle** (YAML manifest + Jinja templates) that lives in a git repo your platform team controls.
- A fluid contract that **points at the bundle** and runs `fluid custom-scaffold` to render it.
- A CI definition emitted from your team's templates, driven by the contract's identity fields and a `targets` variable that lists the deploy targets.

Realistic time end to end: **15-25 minutes**.

::: tip Prerequisites
`pip install data-product-forge data-product-forge-custom-scaffold`. The `fluid custom-scaffold` command is registered by the second package; without it `fluid custom-scaffold` is an unknown command. The command is `custom-scaffold`, not `generate-custom-scaffold`: `generate-custom-scaffold` is the name of the package's entry point, and `fluid generate-custom-scaffold` fails with an invalid-choice error.
:::

## The mental model

```text
your platform team's repo                      any product team's repo
┌────────────────────────────────┐             ┌──────────────────────────────┐
│ ci-bundle/                     │             │ contract.fluid.yaml          │
│   ├── fluid-scaffold.yaml      │             │   extensions.customScaffold: │
│   ├── templates/               │  ──source── │     libraries:               │
│   │   ├── .gitlab-ci.yml.j2    │             │       - source:              │
│   │   ├── Dockerfile.j2        │             │         kind: git            │
│   │   └── README.md.j2         │             │         url: …               │
│   └── static/                  │             │         ref: v1.0.0          │
└────────────────────────────────┘             └──────────────────────────────┘
            │                                              │
            │             fluid custom-scaffold            │
            └────────────────┬─────────────────────────────┘
                             ▼
                  product team's repo:
                  ├── .gitlab-ci.yml          ← rendered from your template
                  ├── Dockerfile              ← rendered from your template
                  └── README.md               ← rendered from your template
```

Two ownership boundaries:

1. **The platform team owns the bundle.** They write the Jinja templates, tag versions, and review changes. Product teams do not edit these files.
2. **Product teams own the contract.** They declare the contract's identity (`id`, `name`, `metadata.owner`, `domain`) and the `targets` variable the bundle asks for. Re-running `fluid custom-scaffold` against a new bundle version pulls fresh templates.

## Step 0: see the result first

A product team's directory after `fluid custom-scaffold`:

```text
my-data-product/
├── contract.fluid.yaml     ← the product team wrote this
├── fluid-scaffold.lock     ← the engine wrote this; records the resolved bundle commit
├── .gitlab-ci.yml          ← rendered from the bundle's .gitlab-ci.yml.j2
├── Dockerfile              ← rendered from the bundle's Dockerfile.j2
├── README.md               ← rendered from the bundle's README.md.j2
└── docs/runbook.md         ← copied verbatim from the bundle's static/
```

The rendered files are deterministic, so the product team commits them, along with `fluid-scaffold.lock`. When the platform team cuts a new bundle version, the product team re-runs the command and the diff is the platform team's intentional change.

## Step 1: set up the bundle repo

Git is the usual bundle source. The other source kinds are `path` (local development) and `entrypoint` (Python plugins, covered in the [examples](../examples/)).

```bash
mkdir my-org-ci-bundle && cd my-org-ci-bundle
git init -q

mkdir -p templates static
```

You should have:

```text
my-org-ci-bundle/
├── templates/    (Jinja templates rendered against the contract)
└── static/       (files copied verbatim: runbooks, license, ...)
```

## Step 2: write the bundle manifest

The manifest tells the custom-scaffold engine what your bundle produces. Create `fluid-scaffold.yaml`:

```yaml
# fluid-scaffold.yaml
apiVersion: fluid.dev/custom-scaffold.v1

bundle:
  name: my-org-ci
  version: 1.0.0
  description: My Org's standard CI/CD scaffold
  author: platform-team@my-org.example.com

patterns:
  - name: main
    description: Render the full project skeleton (CI + Dockerfile + README)
    supportedProductTypes: [SDP, ADP, CDP]
    requiredContractFields:
      - id
      - metadata.owner.email
    variables:                       # JSON Schema (draft-07) for patterns[].variables
      $schema: http://json-schema.org/draft-07/schema#
      type: object
      required: [targets]
      properties:
        targets:
          type: object
          minProperties: 1
          additionalProperties:
            type: object
            required: [provider, region]
            properties:
              provider: { enum: [aws, gcp, snowflake] }
              region: { type: string }
    templates:
      - from: templates/.gitlab-ci.yml.j2
        to: .gitlab-ci.yml
      - from: templates/Dockerfile.j2
        to: Dockerfile
      - from: templates/README.md.j2
        to: README.md
```

Two guards run before any template renders:

- `requiredContractFields` is a presence check on the contract. A contract without `metadata.owner.email` fails with `Pattern 'main' requires contract field 'metadata.owner.email', which is missing or empty.`
- The `variables` schema is checked against what the product team passes under `patterns[].variables`. A missing `targets` fails with `invalid variables — variables.(root): 'targets' is a required property`; a provider outside the enum fails with `variables.targets.dev.provider: 'azure' is not one of ['aws', 'gcp', 'snowflake']`.

### Where per-environment data lives

The contract schema validates an `environments:` map, but `fluid plan` and `fluid apply` apply nothing from it, and each environment entry is closed to `metadata`, `exposes`, `tags` and `labels`: `environments.prod.cloud` fails `fluid validate` with `Additional properties are not allowed ('cloud' was unexpected)`. Values that only your bundle reads belong in the pattern's `variables`, as above. Values that `fluid apply --env prod` must act on belong in an overlay file, `overlays/prod.yaml`; see [per-environment overlays](../../recipes/per-environment-overlays.md).

## Step 3: pick your CI system

The templates below are complete. Drop them into your bundle's `templates/` directory. Each one is a Jinja template: variables in `{{ ... }}`, loops in `{% for ... %}{% endfor %}`. Pick the one matching your org's CI:

| CI system | What you get | Approval gate |
|---|---|---|
| **[GitLab CI →](./your-own-ci-gitlab.md)** | `.gitlab-ci.yml.j2`: three stages (validate, build, deploy), one deploy job per target, switch on the target's `provider` | `when: manual` on prod |
| **[GitHub Actions →](./your-own-ci-github.md)** | `.github/workflows/ci.yml.j2`: one validate job + one `deploy-<env>` job per target, OIDC auth to AWS/GCP | GitHub Environments for prod |
| **[Jenkins →](./your-own-ci-jenkins.md)** | `Jenkinsfile.j2`: declarative pipeline, per-target stages, `withCredentials` for cloud auth | `input { ... }` block for prod |
| **[CircleCI →](./your-own-ci-circleci.md)** | `.circleci/config.yml.j2`: validate + per-target deploy jobs, workflow ordering | `type: approval` job for prod |

The GitLab template is part of the `main` pattern above. The GitHub, Jenkins and CircleCI pages each add their template as its own pattern in the same manifest (`github`, `jenkins`, `circleci`), selected with `use: my-ci:<pattern>`. A pattern can also list several `templates:` entries.

The templates read these names from the render context, which is built from the contract plus your `variables`:

| Name | What it is |
|---|---|
| `product_id`, `product_name`, `description`, `domain` | The contract's root `id`, `name`, `description`, `domain` |
| `metadata`, `owner`, `labels`, `tags` | The contract's `metadata` block, `metadata.owner`, and the root `labels` and `tags` |
| `product_type` | `metadata.productType` |
| `exposes`, `consumes`, `builds`, `environments` | The contract's blocks of the same name |
| `bundle` | `name`, `version`, `description`, `author`, `license`, `url`, `pattern_name` from the manifest's `bundle:` block |
| `fluid` | The whole contract dict |
| anything under `patterns[].variables` | For example `targets`, or an optional `fluid_cli_version` to pin the CLI the pipeline installs |

There is no `contract` name in the context: `{{ contract.metadata.id }}` fails with `RenderError`, and a root field such as the id is `{{ product_id }}`. Rendering uses Jinja's `StrictUndefined`, so a name that does not exist fails the run instead of rendering an empty string.

## Step 4: add the supporting templates

`Dockerfile.j2` and `README.md.j2` work the same way:

::: details templates/Dockerfile.j2 - opinionated app image
```jinja
# Auto-generated Dockerfile for {{ product_id }}
# Rendered from {{ bundle.name }}@{{ bundle.version }} - do not edit by hand.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="{{ product_id }}"
LABEL org.opencontainers.image.description="{{ description }}"
LABEL my-org.owner="{{ owner.email }}"
LABEL my-org.domain="{{ domain | default('unknown') }}"

WORKDIR /app
COPY . .
USER 1000:1000

ENTRYPOINT ["python", "-m", "{{ product_id | replace('-', '_') | replace('.', '_') }}"]
```
:::

::: details templates/README.md.j2 - opinionated project README
````jinja
# {{ product_name }}

> {{ description }}

**Owner:** {{ owner.email }}{% if domain %} · **Domain:** {{ domain }}{% endif %}

## What this is

Data product `{{ product_id }}`, classified as `{{ metadata.layer | default('Bronze') }}` ({{ product_type | default('SDP') }}). Generated from `{{ bundle.name }}@{{ bundle.version }}`.

## Environments

{% for env_name, t in targets.items() -%}
- **{{ env_name }}**: {{ t.provider }} ({{ t.region }})
{% endfor %}
## Local development

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --env dev
```
````
:::

## Step 5: add static files

Anything that is not a template lives in `static/`. The engine copies that directory byte for byte to the output root. It refuses symlinks (see the [trust model](../reference/trust-model.md)). A pattern copies the whole `static/` tree, so a bundle with several patterns writes the same static files for each.

```bash
mkdir -p static/docs
cat > static/docs/runbook.md <<'EOF'
# On-call runbook

For incidents, page the team via PagerDuty service "data-platform".
EOF
```

## Step 6: tag a bundle version

```bash
git add fluid-scaffold.yaml templates/ static/
git commit -m "v1.0.0: initial bundle"
git tag v1.0.0
git remote add origin https://github.com/my-org/ci-bundle.git
git push --tags origin main
```

The tag is what product-team contracts pin against. Pin to a tag: a contract that follows a moving `main` changes underneath the team.

## Step 7: consume from a product team's repo

Now you are a product-team engineer. In your product's repo:

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: bronze.commerce.order_events_v1
name: Order Events
description: Real-time order event stream.
domain: commerce

metadata:
  layer: Bronze
  productType: SDP
  owner: { team: commerce, email: orders-team@my-org.example.com }

exposes:
  - exposeId: order_events
    kind: table
    binding:
      platform: local
      format: parquet
      location: { path: out/order_events.parquet }
    contract:
      schema:
        - { name: order_id, type: STRING, required: true }

extensions:
  customScaffold:
    libraries:
      - id: my-ci
        source:
          kind: git
          url: "https://github.com/my-org/ci-bundle"
          ref: "v1.0.0"                      # pin the tag
          auth: { secret_ref: GITHUB_TOKEN } # only needed for private bundles
    patterns:
      - use: my-ci:main
        variables:
          targets:
            dev:     { provider: gcp, project: order-events-dev,     region: us-central1 }
            staging: { provider: gcp, project: order-events-staging, region: us-central1 }
            prod:    { provider: gcp, project: order-events-prod,    region: us-east1 }
```

```bash
pip install data-product-forge data-product-forge-custom-scaffold

# Only for private bundles:
export GITHUB_TOKEN=<token>

fluid validate contract.fluid.yaml
fluid custom-scaffold
```

You should see (output trimmed; the engine prints absolute paths):

```text
Resolved libraries:
  my-ci  ...

✓ 4 files written, 0 failed (0.0168s)
  .../.gitlab-ci.yml
  .../Dockerfile
  .../README.md
  .../docs/runbook.md
```

The engine also writes `fluid-scaffold.lock` to the output root. Commit it with the generated files. It records the pattern `variables` verbatim, so keep secrets out of `variables`.

::: details Verified on 0.18.1
The steps above were run on CLI 0.18.1 with `data-product-forge-custom-scaffold` 0.4.1, with the bundle bound as `source: { kind: path, path: ../my-org-ci-bundle }` instead of `kind: git`, because the engine refuses `file://` git URLs (`git source url has disallowed scheme ... (allowed: https/ssh/git+https/git+ssh)`). The rendered output is the same for both source kinds. The git clone path itself was not exercised.
:::

## When the platform team ships a new bundle version

```bash
# In the product-team repo:
# bump ref in contract.fluid.yaml:  ref: v1.0.0  →  ref: v1.1.0
fluid custom-scaffold
git diff
```

`git diff` shows what the platform team changed. Review, commit, deploy.

::: tip Reproducible re-generation (engine 0.4.0)
`fluid custom-scaffold --pin` re-renders at the commit recorded in `fluid-scaffold.lock`, for reproducible CI. `fluid custom-scaffold --update [--target REF]` re-renders at the new ref and 3-way-merges the result onto the working tree. See [Reproducible re-generation](./your-own-scaffolding.md#reproducible-re-generation-engine-0-4-0).
:::

## You'll know it worked when

- `fluid custom-scaffold` writes `.gitlab-ci.yml` (or the file your template targets) rendered with your contract's identity and `targets`.
- The rendered CI definition has one deploy job per entry in `targets`.
- Adding a fourth entry to `targets` and re-running the command produces a fourth deploy job, without touching the bundle.
- Bumping the bundle `ref:` in the contract and re-running the command renders the new bundle's templates against the current contract.
- `fluid-scaffold.lock` records the resolved bundle commit, and carries the pattern variables but not the `auth` block or any token.

## When **not** to use this pattern

- **If each product needs a different CI definition.** Bundles are for shared conventions; without shared conventions the bundle adds overhead and saves nothing.
- **If you would rather write Python.** The [`gitlab-ci-scaffold` example](../examples/gitlab-ci-scaffold.md) does the same job as a `CustomScaffold` Python class. Pick based on who is authoring: a bundle for platform engineers who do not write Python, a plugin for programmatic control.
- **If the output is not deterministic.** Anything that needs network access at render time, randomness or timestamps breaks the engine's assumption that the same context renders the same bytes. Build a Python plugin (the `entrypoint` source kind) and own that logic yourself.

## Common gotchas

::: details `fluid generate-custom-scaffold` says invalid choice
The command is `fluid custom-scaffold`. `generate-custom-scaffold` is the entry-point name the companion package registers under `fluid_build.commands`; `fluid plugins` lists it that way, but the subcommand it adds is `custom-scaffold`.
:::

::: details `fluid custom-scaffold` fails with "git source missing required 'ref'"
The contract's `source.ref` is required. Leaving it out is a deliberate failure, so a bundle reference cannot silently float to the latest commit. The engine also only accepts `https`, `ssh`, `git+https` and `git+ssh` URLs.
:::

::: details The bundle is private, what auth do I use?
`source.auth.secret_ref` names the environment variable carrying a token (here `GITHUB_TOKEN`). The engine injects it into the clone URL as `https://x-access-token:<TOKEN>@github.com/...`. The lock file records the source URL, ref and resolved commit, not the `auth` block.

```yaml
source:
  kind: git
  url:  "https://github.com/my-org/ci-bundle"
  ref:  "v1.0.0"
  auth: { secret_ref: GITHUB_TOKEN }
```

Then `export GITHUB_TOKEN=...` before running `fluid custom-scaffold`.
:::

::: details The bundle moved, my CI doesn't reflect it
Git bundles are cached under `~/.cache/fluid/custom-scaffold/git/<urlhash>/<ref>/`. If you re-tag the same ref with new content, the cache does not pick it up. Bump the ref (recommended, tags should be immutable), or set `FLUID_CUSTOM_SCAFFOLD_NOCACHE=1` to force a fresh clone.
:::

::: details A template fails with `RenderError`
The render context has no `contract` name (see the table in Step 3), and `StrictUndefined` fails on any name it does not have. `{{ contract.metadata.id }}` becomes `{{ product_id }}`; `{{ contract.environments.items() }}` becomes `{{ environments.items() }}` or, for bundle-owned data, `{{ targets.items() }}`. Escape quotes in a Jinja default inside a quoted Groovy string with the other quote kind: `{{ fluid_cli_version | default("0.18.1") }}`, not `default(\'0.18.1\')`, which Jinja rejects.

Add `requiredContractFields:` and a `variables:` schema to the manifest so the failure comes earlier and names the missing field.
:::

## Next

- [Your own scaffolding](./your-own-scaffolding.md): the same pattern for the full project skeleton, not just CI
- [Custom validator](./custom-validator.md): for governance rules, not file generation
- [Apply hook](./apply-hook.md): for runtime invariants right before deploy
- [Reference → Roles](../reference/roles.md), [Entry points](../reference/entry-points.md), [Trust model](../reference/trust-model.md)
