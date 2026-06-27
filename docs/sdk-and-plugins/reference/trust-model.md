# Trust model

Plugins are **uncontained Python** loaded into the CLI process. Once a plugin is loaded there is no sandboxing, no per-plugin timeout, no resource limit. Trust in a plugin equals trust in whatever `pip` resolved when you installed it.

The one operator control that runs **before** load is the allow/block gate (CLI 0.10.0): `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST` decide whether a plugin's code is even imported — a blocked plugin never executes. That is a real trust boundary, not just a display filter. Everything below the gate (the "no sandbox once loaded" caveat) still holds.

If you treat plugins as adversarial, you'd never install community plugins. Most users — correctly — treat their `pip install` source list as a small attack surface they've already chosen to trust (same as their `requirements.txt` for an application). This page describes:

1. The operator governance gate that decides which plugins load at all.
2. What the CLI guarantees plugins **can't** do once loaded, regardless of intent or bug.
3. What the CLI deliberately does **not** defend against.
4. How to think about plugin trust in your org.

## Operator governance — allowlist and blocklist

CLI **0.10.0** adds two environment variables that gate **every code-executing entry-point group BEFORE the plugin is loaded**:

| Env var | Effect |
|---|---|
| `FLUID_PLUGINS_ALLOWLIST` | Comma-separated entry-point names. If set, **only** these plugins load; everything else is skipped. |
| `FLUID_PLUGINS_BLOCKLIST` | Comma-separated entry-point names. These plugins **never** load. |

The gate runs at discovery time, for every governed group — `providers`, `validators`, `catalog adapters`, `commands`, `apply_hooks`, `extension_schemas`, `extension_validators`, `modeling_techniques`, `source_adapters`, `iac_providers`. A blocked plugin's `load()` is never called, so its **code never executes** — not in a `try/except`, not behind a flag, not at all. This is the in-process complement to pip-level allowlisting (Policy 1/2 below): pip controls what is *installed*; these vars control what is *loaded* from whatever happens to be installed.

```bash
# Only the in-house validators load; nothing else, no matter what's pip-installed.
export FLUID_PLUGINS_ALLOWLIST="steward-required,cost-center-required"

# Everything loads except one suspect plugin.
export FLUID_PLUGINS_BLOCKLIST="some-third-party-scaffold"
```

`fluid plugins` surfaces each plugin's **allow/block status** so an operator can see exactly what would (and wouldn't) load — see [`fluid plugins`](/forge_docs/cli/plugins.html).

## SDK to CLI version-compat gate

CLI **0.10.0** also adds an opt-in compatibility gate, `FLUID_PLUGIN_STRICT_COMPAT=1`. When set, the CLI reads a plugin's declared `requires_cli` (a PEP 440 specifier carried on the SDK's [`PluginMetadata`](./roles.md#sdk-to-cli-compat-declaration)) and **refuses to load** any plugin whose requirement the running CLI version does not satisfy. Default (unset) is **warn-only** — the plugin still loads, but a mismatch is logged.

This is the dbt `require-dbt-version` model: the **SDK declares** compatibility, the **CLI gates** on it. A plugin pinned to `requires_cli=">=0.11"` running on CLI 0.10.0 loads with a warning by default, and is refused outright under strict compat.

## What the CLI defends against

### 1. Crashes

Every plugin's `load()` and invocation is wrapped in `try/except`. A plugin that raises `RuntimeError` or `ImportError` is logged at WARNING and the CLI continues with the next plugin. No exception escapes the CLI.

```python
# CLI loop (simplified, from cli/bootstrap.py / validate.py / apply.py)
for ep in entry_points:
    try:
        plugin = ep.load()
        plugin(args)
    except Exception as e:
        LOG.warning("plugin %s failed: %s", ep.name, redact(str(e)))
        # CLI continues
```

The CLI never crashes because of a plugin. Worst case: a plugin's intended functionality silently doesn't happen, with the failure logged.

Pinned by `tests/test_cli_plugin_hooks.py::TestBootstrapCommands::test_plugin_load_failure_logged_not_raised` and siblings.

### 2. Contract mutation (apply hooks)

Apply hooks receive a `copy.deepcopy(contract)` — not the live reference. Whatever the hook does to its received contract — modify a field, replace a nested dict, drop a key — is **invisible** to the rest of `fluid apply` and to other hooks.

```python
# Simplified from cli/apply.py
import copy

for ep in apply_hook_entry_points:
    isolated = copy.deepcopy(contract)   # ← fresh copy per hook
    ep.load()(contract_dir, isolated, errors)
```

A buggy hook that "fixes" the contract by mutating it can't poison the rest of the apply. A malicious hook that tries to inject extra `consumes:` or alter `metadata.owner.email` mid-apply is silently neutralized.

Pinned by `test_apply_hook_receives_deep_copy_of_contract`.

> Validators and CustomScaffolds **do not** receive a deep copy — they're contract-read-only by convention, and the cost of deepcopy on every validate-time call was deemed not worth the negligible additional safety. If you want belt-and-braces, make a copy yourself.

### 3. Credential leak in error messages

The CLI has a `SecretRedactingFilter` that scrubs args bound to `password=%s`-style log patterns. That filter handles the common case but doesn't catch free-form text — a plugin's `RuntimeError("bad config: api_key=sk_live_AAAAA...")` would normally slip through.

The plugin code path **pre-redacts** all plugin-supplied exception text with `redact_secret_text()` before it reaches logs or error lists:

```python
# Simplified from cli/apply.py, cli/validate.py, cli/bootstrap.py
try:
    plugin(args)
except Exception as e:
    errors.append(
        redact_secret_text(f"plugin {ep.name!r} raised: {e}")  # ← scrubbed
    )
```

The redactor catches: `password=...` / `api_key=...` / `token=...` style assignments, `Bearer ...` tokens, `ghp_...` / `sk_live_...` / `sk_test_...` provider keys, JWT-shaped tokens.

It does **not** catch: URL-embedded credentials (`https://user:pass@host`), HTTP Basic Auth headers (`Authorization: Basic <base64>`), arbitrary org-specific secret shapes. If your plugin handles unusual credential shapes, redact them yourself before raising.

Pinned by `TestPluginErrorRedaction` (5 tests in `test_cli_plugin_hooks.py`).

### 4. Apply-hook override is explicit and audited

The single CLI flag that downgrades apply-hook errors to warnings is `--force-pattern-drift`. Using it:

- Does not silently bypass the hook — every error still appears, as a WARN.
- Logs `apply hook drift ignored (--force-pattern-drift): ...` to stdout / stderr / journald, whatever the deploy environment captures.
- Is audit-able after the fact.

There's no per-plugin override flag. If a hook needs a custom escape, the hook itself reads an env var:

```python
if errors and os.environ.get("MY_HOOK_OVERRIDE"):
    return   # hook-internal escape, separate from --force-pattern-drift
```

## What the CLI deliberately does **not** defend against

### Malicious plugin code

A plugin can `os.system("rm -rf $HOME")`, exfiltrate `~/.aws/credentials`, open a reverse shell, run a cryptominer, anything Python can do. The CLI doesn't sandbox plugin code because **sandboxing Python is a hard problem with no clean OSS solution**, and adding it would slow down development without buying real safety (a determined attacker fingers around any in-process sandbox).

**Mitigation in your hands:** vet packages before installing them. Pin to specific versions in your `requirements.txt`. Use a private PyPI mirror if your org doesn't want to allow arbitrary public PyPI installs.

### Hung plugins

A plugin that does `while True: pass` blocks the CLI indefinitely. There is no per-plugin timeout.

**Mitigation in your hands:** plugins that make network calls should set per-request timeouts:

```python
import requests
r = requests.get(url, timeout=5)  # bounded; won't hang forever
```

If you're authoring a plugin that *could* hang on a flaky external service, set a tight timeout and fall back to a pass result.

### Resource exhaustion

A plugin can allocate unbounded memory, fork subprocesses, hold file descriptors. The CLI has no `setrlimit` calls or cgroup integration.

**Mitigation in your hands:** if you're running plugins in a deploy environment with limits, set them at the OS level (Docker `--memory`, Kubernetes resource requests, systemd `MemoryMax`). The CLI doesn't do this for you.

### URL-embedded credential leaks

The redactor catches `key=value` assignments and provider-token shapes, but it doesn't currently match `https://user:password@host` URLs or HTTP Basic Auth headers in free-form exception text.

If your plugin handles HTTP responses with embedded creds, scrub them yourself before raising or logging.

## How to think about plugin trust in your org

Three policies most orgs converge to:

### Policy 1 — only allow plugins from your private index

```bash
# in ~/.pip/pip.conf or your org's standard pip config
[global]
index-url = https://pypi.internal.example.com/simple/
# Nothing comes from public PyPI; vetting happens at index admission.
```

Plugins are tested, scanned, and approved by your platform team before showing up in the internal index. Public PyPI is unreachable. Highest trust, highest friction.

### Policy 2 — allowlist specific public PyPI plugins

```toml
# In your deploy environment's pyproject.toml or requirements:
data-product-forge==0.10.0
data-product-forge-sdk==0.10.0
data-product-forge-custom-scaffold==0.4.0
my-org-validators==1.2.0
# That's it. No other forge plugins.
```

Public PyPI is reachable but every plugin is on a tracked list. Medium trust, medium friction. The new `FLUID_PLUGINS_ALLOWLIST` / `FLUID_PLUGINS_BLOCKLIST` vars give an in-process complement to this pip-level allowlist — even if something else lands in the environment, only the named entry-points load.

### Policy 3 — trust the team running the CLI

If `data-product-forge` is run by a small data platform team on a hardened CI runner, `pip install`-anything is fine — same security boundary as the rest of your CI environment. Lowest friction, highest trust on the runner image.

The CLI doesn't care which policy you pick. It defends against the three failure modes above regardless.

## What plugin authors should do

If you're publishing a plugin to public PyPI:

- **Pin your own dependencies** with upper bounds. `data-product-forge-sdk>=0.10,<1` not `>=0.10`.
- **Test on the supported Python matrix** (3.10–3.14).
- **Document any non-stdlib dependency** in your README — surprising network calls or filesystem access deserve a heads-up.
- **Scrub credentials** before logging or raising. The CLI's redactor is a safety net, not your first line of defense.
- **Don't `os.system`-out** unless it's literally what your plugin does. `subprocess.run([...], shell=False)` is safer than `os.system(...)`.
- **Sign your wheels.** PyPI Trusted Publishing + Sigstore make this free. Helps reviewers verify your package came from your CI, not from a typo-squatter.

If you're reviewing a plugin for org install:

- **Read the source.** It's Python; it's small. The `examples/` in the SDK repo are each <200 LOC.
- **Check the dependency graph.** `pip install --dry-run --no-deps <pkg>` shows the immediate deps; `pipdeptree` shows transitive.
- **Look for `os.system` / `subprocess` / `urllib` / `requests`.** Network calls and shell-outs are the highest-risk surfaces.
- **Run the plugin's tests.** Confidence that the author tested *their own claims*.
- **Pin the version.** Once vetted, write `==X.Y.Z` in your install spec — and re-vet when bumping.

## Reporting a plugin vulnerability

If a vulnerability lives in a *third-party* plugin (not in this CLI), file the report with that plugin's project.

If the issue is in how the CLI dispatches to plugins — the entry-point discovery, exception trapping, contract isolation, redaction logic — file it via the channel in [`SECURITY.md`](https://github.com/Agenticstiger/forge-cli/blob/main/SECURITY.md).

## Source

- Crash containment: [`fluid_build/cli/bootstrap.py`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/bootstrap.py), [`cli/validate.py`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/validate.py), [`cli/apply.py`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/cli/apply.py)
- Contract deep-copy: search for `copy.deepcopy` in `cli/apply.py::_run_apply_hooks`
- Redactor: [`fluid_build/observability/secret_redactor.py`](https://github.com/Agenticstiger/forge-cli/blob/main/fluid_build/observability/secret_redactor.py)
- Tests pinning all four guarantees: [`tests/test_cli_plugin_hooks.py`](https://github.com/Agenticstiger/forge-cli/blob/main/tests/test_cli_plugin_hooks.py)
