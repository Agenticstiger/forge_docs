# You have your own CI/CD setup, no problem

Your platform team already maintains GitLab CI templates / GitHub Actions workflows / Jenkinsfiles that encode your org's conventions: how to authenticate to the cloud, what tests to run, when to require approvals, which secrets to inject. You don't want `data-product-forge` to overwrite any of that — you want it to **emit your existing templates**, with values pulled from each contract.

This guide walks through that pattern end-to-end. By the end you'll have:

- A small **scaffold bundle** (YAML manifest + Jinja templates) that lives in a git repo your platform team controls.
- A fluid contract that **points at the bundle** and runs `fluid generate custom-scaffold` to render it.
- A CI definition emitted from your team's templates — not from forge's defaults — driven by the contract's `metadata` / `environments` / `domain`.

Realistic time end-to-end: **15–25 minutes**.

## The mental model

```text
your platform-team's git repo                  any product team's repo
┌────────────────────────────────┐             ┌──────────────────────────────┐
│ ci-bundle/                     │             │ contract.fluid.yaml          │
│   ├── fluid-scaffold.yaml      │             │   extensions.customScaffold: │
│   ├── templates/               │  ──source── │     libraries:               │
│   │   ├── .gitlab-ci.yml.j2    │             │       - source:              │
│   │   ├── Dockerfile.j2        │             │         kind: git            │
│   │   └── README.md.j2         │             │         url: …               │
│   └── static/                  │             │         ref: v1.2.0          │
└────────────────────────────────┘             └──────────────────────────────┘
            │                                              │
            │       fluid generate custom-scaffold         │
            └────────────────┬─────────────────────────────┘
                             ▼
                  product-team's repo:
                  ├── .gitlab-ci.yml          ← rendered from your template
                  ├── Dockerfile              ← rendered from your template
                  └── README.md               ← rendered from your template
```

Two clean ownership boundaries:

1. **Platform team owns the bundle.** They write the Jinja templates, they tag versions, they version-control changes. Product teams **never** edit these files.
2. **Product teams own the contract.** They declare `environments`, `metadata.domain`, `metadata.owner` — whatever the bundle's templates ask for. Re-running `fluid generate` against a new bundle version pulls fresh templates.

## Step 0 — see the result first

A product team's directory after `fluid generate custom-scaffold`:

```text
my-data-product/
├── contract.fluid.yaml                  ← they wrote this
├── fluid-custom-scaffold.lock.json      ← engine wrote this; pins the bundle sha
├── .gitlab-ci.yml                       ← rendered from your bundle's .gitlab-ci.yml.j2
├── Dockerfile                           ← rendered from your bundle's Dockerfile.j2
├── README.md                            ← rendered from your bundle's README.md.j2
└── docs/runbook.md                      ← copied verbatim from your bundle's static/
```

The product team can commit all the rendered files (they're deterministic). When you cut a new bundle version, they re-run `fluid generate`, and the diff is the platform-team intentional changes.

## Step 1 — set up the bundle repo

We'll use git as the bundle source (the other options are `path` for local development and `entrypoint` for Python plugins — see the [example walkthroughs](../examples/) for those).

```bash
mkdir my-org-ci-bundle && cd my-org-ci-bundle
git init -q

mkdir -p templates static
```

You should have:

```text
my-org-ci-bundle/
├── templates/    (Jinja templates rendered against the contract)
└── static/       (files copied verbatim — runbooks, license, etc.)
```

## Step 2 — write the bundle manifest

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
      - metadata.owner.email
      - environments
    templates:
      - from: templates/.gitlab-ci.yml.j2
        to: .gitlab-ci.yml
      - from: templates/Dockerfile.j2
        to: Dockerfile
      - from: templates/README.md.j2
        to: README.md
```

The `requiredContractFields` list is a cheap presence guard — if a contract is missing `metadata.owner.email` or `environments`, `fluid generate` fails with a clear message before any template rendering.

## Step 3 — pick your CI system

The templates below are full and runnable. Drop them into your bundle's `templates/` directory. Each one is a Jinja template — variables in `{{ … }}`, loops in `{% for … %}{% endfor %}`. Pick the one matching your org's CI:

| CI system | What you get | Approval gate |
|---|---|---|
| **[GitLab CI →](./your-own-ci-gitlab.md)** | `.gitlab-ci.yml.j2` — three stages (validate, build, deploy), one deploy job per env, switch on `env.cloud.provider` | `when: manual` on prod |
| **[GitHub Actions →](./your-own-ci-github.md)** | `.github/workflows/ci.yml.j2` — one validate + one `deploy-<env>` job per env, OIDC auth to AWS/GCP | GitHub Environments for prod |
| **[Jenkins →](./your-own-ci-jenkins.md)** | `Jenkinsfile.j2` — declarative pipeline, per-env stages, `withCredentials` for cloud auth | `input { … }` block for prod |
| **[CircleCI →](./your-own-ci-circleci.md)** | `.circleci/config.yml.j2` — validate + per-env deploy jobs, workflow ordering | `type: approval` job for prod |

Pick one (or copy several into the same bundle — the manifest can list multiple `templates:` paths) and continue with Step 4.


## Step 4 — add the supporting templates

`Dockerfile.j2` and `README.md.j2` work the same way. Examples:


::: details templates/Dockerfile.j2 — opinionated app image
```jinja
# Auto-generated Dockerfile for {{ contract.metadata.id }}
# Rendered from my-org-ci-bundle@{{ bundle.version }} — do not edit by hand.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="{{ contract.metadata.id }}"
LABEL org.opencontainers.image.description="{{ contract.metadata.description }}"
LABEL org.opencontainers.image.source="{{ contract.metadata.id }}"
LABEL my-org.owner="{{ contract.metadata.owner.email }}"
LABEL my-org.domain="{{ contract.metadata.domain | default('unknown') }}"

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
USER 1000:1000

ENTRYPOINT ["python", "-m", "{{ contract.metadata.id | replace('-', '_') }}"]
```
:::



::: details templates/README.md.j2 — opinionated project README
```jinja
# {{ contract.metadata.name }}

> {{ contract.metadata.description }}

**Owner:** {{ contract.metadata.owner.email }}{% if contract.metadata.domain %} · **Domain:** {{ contract.metadata.domain }}{% endif %}

## What this is

Data product `{{ contract.metadata.id }}` — classified as `{{ contract.metadata.layer | default('Bronze') }}` ({{ contract.metadata.productType | default('SDP') }}). Generated from [`my-org-ci-bundle@{{ bundle.version }}`](https://github.com/my-org/ci-bundle/releases/tag/v{{ bundle.version }}).

## Environments

{% for env_name, env in contract.environments.items() %}
- **{{ env_name }}** — {{ env.cloud.provider }} ({{ env.cloud.region | default('—') }})
{% endfor %}

## Local development

```bash
fluid validate contract.fluid.yaml
fluid apply contract.fluid.yaml --env dev --dry-run
```

## CI/CD

This project ships a CI definition generated from `my-org-ci-bundle`. The bundle is the source of truth — edit your contract and re-run `fluid generate custom-scaffold` to pick up changes.
```
:::


## Step 5 — add static files (runbooks, license, anything verbatim)

Anything that isn't a template just lives in `static/`. The custom-scaffold engine copies that directory byte-for-byte. Symlinks are refused (security feature — see [trust model](../reference/trust-model.md)).

```bash
mkdir -p static/docs
cat > static/docs/runbook.md <<'EOF'
# On-call runbook

For incidents, page the team via PagerDuty service "data-platform".

Common runbooks live at https://runbooks.my-org.example.com/data-products.
EOF
```

## Step 6 — tag a bundle version

```bash
git add fluid-scaffold.yaml templates/ static/
git commit -m "v1.0.0: initial bundle"
git tag v1.0.0
git remote add origin https://github.com/my-org/ci-bundle.git
git push --tags origin main
```

The tag is what product-team contracts will pin against. Always tag — never have product teams pull from a moving `main`.

## Step 7 — consume from a product team's repo

Now you're a product-team engineer. In your product's repo:

```yaml
# contract.fluid.yaml
fluidVersion: "0.7.3"

metadata:
  id: order-events
  name: Order Events
  description: Real-time order event stream.
  owner: { email: orders-team@my-org.example.com }
  domain: commerce
  layer: Bronze
  productType: SDP

environments:
  dev:
    cloud: { provider: aws, account: "111111111111", region: us-east-1 }
  staging:
    cloud: { provider: aws, account: "222222222222", region: us-east-1 }
  prod:
    cloud: { provider: aws, account: "333333333333", region: us-west-2 }

extensions:
  customScaffold:
    libraries:
      - id: my-ci
        source:
          kind: git
          url:  "https://github.com/my-org/ci-bundle"
          ref:  "v1.0.0"               # pin the tag
          auth: { secret_ref: GITHUB_TOKEN }   # only needed for private bundles
    patterns:
      - use: my-ci:main
```

```bash
pip install data-product-forge data-product-forge-custom-scaffold

# Optionally for private bundles:
export GITHUB_TOKEN=ghp_…

fluid generate custom-scaffold
```

You should see:

```text
✓ 5 files written, 0 failed
  .gitlab-ci.yml
  Dockerfile
  README.md
  docs/runbook.md
  fluid-custom-scaffold.lock.json
```

Commit those files. The bundle's templates rendered against your contract are now your CI definition.

## When the platform team ships a new bundle version

```bash
# In the product-team repo:
# bump ref in contract.fluid.yaml:  ref: v1.0.0  →  ref: v1.1.0
fluid generate custom-scaffold
git diff
```

`git diff` shows exactly what the platform team changed. Review, commit, deploy.

## You'll know it worked when

- `fluid generate custom-scaffold` writes `.gitlab-ci.yml` / `.github/workflows/ci.yml` / `Jenkinsfile` / `.circleci/config.yml` rendered with your contract's `environments` and `cloud` values.
- The rendered CI definition has one deploy job per environment in the contract.
- Adding a fourth environment to the contract → re-running `fluid generate` → produces a fourth deploy job, **without touching the bundle**.
- Bumping the bundle `ref:` in the contract → re-running `fluid generate` → produces the new bundle's templates rendered against the current contract.
- `fluid-custom-scaffold.lock.json` captures the bundle's resolved sha256 so apply hooks can verify drift later.

## When **not** to use this pattern

- **If each product needs wildly different CI** — like, the CI for product A has nothing in common with product B's. Bundles are for shared conventions; if there are none, the bundle pattern adds overhead without saving anything.
- **If you'd rather write Python** — the `gitlab-ci-scaffold` [example](../examples/gitlab-ci-scaffold.md) does the same thing as a `CustomScaffold` Python class. Pick based on who's authoring: bundle for non-Python platform engineers; Python plugin for full programmatic control.
- **If the output isn't deterministic** — anything that needs network access at render time, randomness, timestamps, etc. The custom-scaffold engine assumes deterministic templates. For non-deterministic logic, build a Python plugin (`entrypoint` resolver kind) and own the randomness yourself.

## Common gotchas

::: details `fluid generate` fails with "git source missing required 'ref'"
The contract's `source.ref` is required — you must pin to a specific git tag, branch, or commit SHA. Leaving it out is a deliberate failure (so you can never have "the latest" semantics that silently changes underneath you).
:::

::: details The bundle is private, what auth do I use?
`source.auth.secret_ref` is the env-var name carrying a token (e.g. `GITHUB_TOKEN`). The engine injects it into the clone URL as `https://x-access-token:<TOKEN>@github.com/…`. The token is never written to disk and is stripped from error messages.

```yaml
source:
  kind: git
  url:  "https://github.com/my-org/ci-bundle"
  ref:  "v1.0.0"
  auth: { secret_ref: GITHUB_TOKEN }
```

Then `export GITHUB_TOKEN=…` before running `fluid generate`.
:::

::: details The bundle moved, my CI doesn't reflect it
Bundles are cached at `~/.cache/fluid/custom-scaffold/git/<urlhash>/<ref>/`. If you re-tag the same ref (`v1.0.0` → new content), the cache won't pick it up. Either bump the ref number (recommended — tags should be immutable), or set `FLUID_CUSTOM_SCAFFOLD_NOCACHE=1` to force a fresh clone.
:::

::: details Some `Jinja` template path uses unfamiliar syntax
The render context is the **entire contract dict**, plus `bundle.version` and a few helpers. So `{{ contract.metadata.id }}` works, `{% for env_name, env in contract.environments.items() %}` works, `{{ env.cloud.provider | default('aws') }}` works. Jinja's full filter set is available.

If a template field is required and missing, `StrictUndefined` makes the render fail loudly rather than emit an empty string. Add `requiredContractFields:` to the manifest so the failure is even earlier and with a clearer message.
:::

## Next

- [Your own scaffolding](./your-own-scaffolding.md) — same pattern, but for the full project skeleton (not just CI)
- [Custom validator](./custom-validator.md) — for governance rules, not file generation
- [Apply hook](./apply-hook.md) — for runtime invariants right before deploy
- [Reference → Roles](../reference/roles.md), [Entry points](../reference/entry-points.md), [Trust model](../reference/trust-model.md)
