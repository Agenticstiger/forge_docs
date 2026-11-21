# Test kit

*(since 0.32.0, [forge-cli #957](https://github.com/Agenticstiger/forge-cli/pull/957))* A package that plugs into `fluid` through an entry point (an apply hook, a provider, an IaC emitter) has to be tested against the real CLI. It cannot reuse forge-cli's own test helpers, because that `tests/` tree is not in the wheel. `fluid_build.testing` is the part of it a plugin author needs, and it ships inside `data-product-forge`. Installing the CLI is all it takes.

It has four modules:

| Module | Helper | What it does |
|---|---|---|
| `fluid_build.testing.cli` | [`run_fluid`](#run-fluid) | Runs the real CLI in your test process and returns its exit code, stdout and stderr. |
| `fluid_build.testing.env` | [`isolated_env`](#isolated-env) | Gives a test its own `HOME`, working directory and plugin policy, and puts everything back afterwards. |
| `fluid_build.testing.entry_points` | [`installed_plugin`](#installed-plugin) | Installs a real `.dist-info` with entry points for the length of a test, so `fluid` finds the plugin the way it finds an installed package. |
| `fluid_build.testing.http_fake` | [`FakeHttpServer`](#fakehttpserver) | A loopback HTTP server with a route table, a request log and failure injection, over TLS when you give it a context. |

The kit keeps three rules:

- **No third-party imports, and no `pytest` import.** The kit uses the standard library and the CLI itself. Each helper is a context manager or a plain function, so it works with any test runner. Wrap one in a fixture if you want one.
- **Nothing in the CLI imports it.** `fluid --help` and `fluid providers` never load it.
- **Import each module by its own name.** `fluid_build.testing` itself imports nothing.

It is not the SDK's [conformance harness](./packaging.md#conformance-harness). `fluid_sdk.testing` checks that a plugin class keeps the contract of its role. This kit runs a plugin inside the real `fluid apply`, `fluid providers` or `fluid generate iac`, so it also catches a wrong entry point or a hook that never fires.

## An example: testing an apply hook

The hook below asks an approval service before `fluid apply` changes anything. It passes on a machine where `ACME_GATE_URL` is not set.

```python
# src/acme_gate/hook.py
"""Apply hook: ask the approval service before `fluid apply` changes anything."""

import json
import os
import urllib.error
import urllib.request


def check_approval(contract_dir, contract, errors):
    base = os.environ.get("ACME_GATE_URL")
    if not base:
        return  # not configured on this machine: the hook passes
    product = contract["id"]
    request = urllib.request.Request(
        f"{base}/v1/products/{product}/approval",
        headers={"Authorization": f"Bearer {os.environ['ACME_GATE_TOKEN']}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as exc:
        errors.append(f"acme-gate: the approval service answered {exc.code}")
    except OSError as exc:
        errors.append(f"acme-gate: the approval service is unreachable ({exc})")
    else:
        if not answer.get("approved"):
            reason = answer.get("reason", "no reason given")
            errors.append(f"acme-gate: {product} is not approved: {reason}")
```

The package registers it under the `fluid_build.apply_hooks` group, as [Entry points](./entry-points.md) describes:

```toml
# pyproject.toml
[project]
name = "acme-gate"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["data-product-forge>=0.32.0"]

[project.entry-points."fluid_build.apply_hooks"]
acme-gate = "acme_gate.hook:check_approval"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

The tests start the fake approval service, install the hook as an entry point and run `fluid apply --dry-run` through the real CLI:

```python
# tests/test_hook.py
"""Test the acme-gate apply hook through the real `fluid apply`."""

import pytest

from fluid_build.testing.cli import run_fluid
from fluid_build.testing.entry_points import installed_plugin
from fluid_build.testing.env import isolated_env
from fluid_build.testing.http_fake import FakeHttpServer

CONTRACT = """\
fluidVersion: "0.7.5"
kind: DataProduct
id: orders
name: Orders
metadata:
  owner:
    team: data-platform
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: out/events.parquet
    contract:
      schema:
        - name: id
          type: VARCHAR
builds:
  - id: load_events
    pattern: embedded-logic
    engine: sql
    properties:
      sql: "SELECT 'a' AS id"
    execution:
      trigger:
        type: manual
      runtime:
        platform: local
"""

# The same line your pyproject.toml carries under [project.entry-points."fluid_build.apply_hooks"].
HOOKS = {"fluid_build.apply_hooks": {"acme-gate": "acme_gate.hook:check_approval"}}


@pytest.fixture
def gate():
    """The approval service, on a free loopback port."""
    with FakeHttpServer() as fake:
        yield fake


@pytest.fixture
def fluid(tmp_path, capfd, gate):
    """`fluid <args>` with the hook installed, in its own HOME and working directory."""
    (tmp_path / "contract.fluid.yaml").write_text(CONTRACT)
    env = {"ACME_GATE_URL": gate.endpoint, "ACME_GATE_TOKEN": "s3cret"}
    with isolated_env(tmp_path, set_vars=env):
        with installed_plugin(tmp_path / "site", "acme-gate", HOOKS, {}):
            yield lambda *argv: run_fluid(capfd, *argv)


def approve(request, match):
    return 200, {"approved": True}


def test_an_approved_product_applies(fluid, gate):
    gate.add_route("GET", "/v1/products/orders/approval", approve)
    code, out, err = fluid("apply", "contract.fluid.yaml", "--dry-run", "--yes")
    assert code == 0
    assert [r.headers["authorization"] for r in gate.requests] == ["Bearer s3cret"]
    assert gate.unknown == []


def test_a_denied_product_stops_the_apply(fluid, gate):
    gate.add_route(
        "GET",
        "/v1/products/orders/approval",
        lambda request, match: (200, {"approved": False, "reason": "release window closed"}),
    )
    code, out, err = fluid("apply", "contract.fluid.yaml", "--dry-run", "--yes")
    assert code == 1
    assert "orders is not approved: release window closed" in err


def test_a_failing_service_stops_the_apply(fluid, gate):
    gate.fail_route("GET", "/approval", status=503)
    code, out, err = fluid("apply", "contract.fluid.yaml", "--dry-run", "--yes")
    assert code == 1
    assert "the approval service answered 503" in err
```

```bash
pip install "data-product-forge>=0.32.0" pytest
pytest -q
```

```text
...                                                                      [100%]
3 passed in 3.47s
```

The plugin does not need to be installed for this: `pythonpath = ["src"]` makes `acme_gate` importable, and `installed_plugin` registers the entry point. On Python 3.11, pytest also prints one `DeprecationWarning` (`SelectableGroups dict interface is deprecated`). It comes from the CLI's own provider discovery, not from your plugin or the kit.

What each piece does here:

- `isolated_env(tmp_path, set_vars=env)` makes `tmp_path` the working directory, so `contract.fluid.yaml` resolves, gives the test its own `HOME`, and sets the hook's two variables. Everything is put back when the block ends.
- `installed_plugin(tmp_path / "site", "acme-gate", HOOKS, {})` registers the hook the way `pip install` would. `modules` is empty because `acme_gate` is already importable.
- `run_fluid(capfd, "apply", ...)` runs the real `fluid apply`, hook included, and returns `(code, out, err)`.
- `FakeHttpServer` is the approval service. `gate.endpoint` is its base URL, `gate.requests` is what the hook sent, and `gate.unknown` is empty when every request hit a route.

A hook that refuses stops the apply with exit code 1 and writes its message to stderr. This is the `err` the second test reads, with the path shortened:

```text
Loading FLUID contract: <tmp>/contract.fluid.yaml
apply hook: acme-gate: orders is not approved: release window closed
apply aborted by an apply-time plugin hook. Pass --force-pattern-drift to override.
```

The third test reads the same text with `the approval service answered 503` as the message.

Use a contract with a `builds[]` entry, as `CONTRACT` does. A minimal contract without one still exits 0 under `--dry-run`, but the planner prints a plan validation error on stderr.

## `run_fluid`

`run_fluid(capture, *argv)` runs `fluid <argv...>` in the test process and returns `(exit code, stdout, stderr)`. In process is faster than a subprocess, and a test can patch what the command calls. Nothing is spawned, so the environment and working directory the test has at that moment, [`isolated_env`](#isolated-env) included, are the command's.

```python
from fluid_build.testing.cli import run_fluid


def test_version(capfd):
    code, out, err = run_fluid(capfd, "--version")
    assert code == 0
    assert out.startswith("FLUID Forge CLI v")
```

- **`capture`** is anything with a `readouterr()` that returns `(out, err)`: pytest's `capfd` or `capsys`. `run_fluid` captures nothing itself. The examples use `capfd`, which also sees what a subprocess started by the command writes.
- **The exit code** is what a shell would see for `sys.exit(main(argv))`. A command that returns `None`, or exits with `None`, gives `0`. An integer gives itself. Anything else is written to stderr and gives `1`.
- **A crash fails the test.** A `KeyboardInterrupt` or any other exception is not caught, so the test fails with its own traceback.

## `isolated_env`

`fluid` reads the process environment (state backend, provider and plugin policy, telemetry, colour) and the user's home directory. A test that runs it should not inherit those from your shell, and should not leak what it sets.

```python
from fluid_build.testing.env import isolated_env

with isolated_env(tmp_path, drop_prefixes=("ACME_",), set_vars={"ACME_HOST": url}) as home:
    code, out, err = run_fluid(capfd, "plan", "contract.fluid.yaml")
```

`isolated_env(root, *, drop_prefixes=(), set_vars=None)` makes these changes, in this order:

1. It starts from `os.environ` and drops every variable whose name starts with `FLUID_STATE`, `FLUID_PROVIDER`, `FLUID_PLUGIN` or `OTEL_`, and with any prefix in `drop_prefixes`, which is a sequence of strings or one string. That removes the state backend, the provider selection, `FLUID_PLUGINS_ALLOWLIST`, `FLUID_PLUGINS_BLOCKLIST` and `FLUID_PLUGIN_STRICT_COMPAT`, so a policy set in your shell cannot block the plugin the test installs, and the OpenTelemetry settings, so an exporter endpoint in your shell does not receive the test's spans.
2. It points `HOME` and `USERPROFILE` at `<root>/home`, which it creates, and drops `HOMEDRIVE` and `HOMEPATH`.
3. It sets `FLUID_NO_TELEMETRY=1` and `NO_COLOR=1`.
4. It adds `set_vars`, which wins over any drop. Every value has to be a `str`.

It then makes `root` the working directory and yields the new `HOME` as a `Path`. When the block ends, also when the body raises, the working directory and the whole environment, including variables the body set, changed or removed, are put back as they were.

Every other variable stays, your cloud credentials included. Name a prefix to drop more: `AWS_` drops an AWS credential, and `FLUID_` drops every variable of the CLI. An empty prefix is refused, because it would drop every variable.

`isolated_environ(root, *, base=None, drop_prefixes=(), set_vars=None)` returns the same environment as a new dict, starting from `base` (default `os.environ`), and does not apply it. It still creates `<root>/home`. Use it as the `env=` of a subprocess, or to see what `isolated_env` would do. The module also exports `DROPPED_PREFIXES` and `QUIET_VARS`.

## `installed_plugin`

`fluid` finds plugins through `importlib.metadata` entry points. `installed_plugin` writes what `pip install` would leave behind, puts it on `sys.path` and makes the CLI's registries look again. Nothing is mocked.

```python
from fluid_build.testing.entry_points import installed_plugin

groups = {"fluid_build.apply_hooks": {"acme-gate": "acme_gate.hook:check_approval"}}
with installed_plugin(tmp_path / "site", "acme-gate", groups, {}) as dist_info:
    code, out, err = run_fluid(capfd, "apply", "contract.fluid.yaml", "--dry-run", "--yes")
```

`installed_plugin(root, dist, groups, modules)` takes:

| Argument | Meaning |
|---|---|
| `root` | A directory to write into. It is created when missing, and is yours to clean up (`tmp_path` is). |
| `dist` | The distribution name, as `pip` shows it. |
| `groups` | `{entry-point group: {entry-point name: "module:attr"}}`, the same lines as `[project.entry-points."<group>"]` in your `pyproject.toml`. |
| `modules` | `{top-level module name: source text}`, each written as `<name>.py` in `root`. Pass `{}` when your plugin's module is already importable, as in the example above. |

It writes `<dist>-1.0.dist-info` (`METADATA` and `entry_points.txt`) and the modules into `root`, puts `root` first on `sys.path`, invalidates the import caches and yields the `.dist-info` path. For a group in `groups` that has a registry, it resets that registry so it reads the entry points again: `IAC_GROUP` (`fluid_build.iac_providers`) and `PROVIDER_GROUP` (`fluid_build.providers`) are the two constants the module exports. A group that `fluid` reads from `importlib.metadata` every time it uses it, such as `fluid_build.apply_hooks`, needs no reset. A group with a cache of its own is yours to reset.

When the block ends, also when the body raises, `sys.path`, the plugin's modules in `sys.modules` and what the two registries hold are put back as they were at entry. The IaC registry's lookup caches are cleared, not restored. The files stay in `root`.

A module name has to be a top-level identifier that does not shadow a standard-library module. A distribution name cannot be empty or hold a path separator or a line break, and an entry-point group, name or target cannot hold a line break. Any of these raises `ValueError` before anything is written. `write_dist(root, dist, groups, modules)` does the writing alone, returns the `.dist-info` and changes nothing else.

### Providers and IaC emitters

A provider or an IaC plugin is found through a registry that caches what it read, which is why `installed_plugin` resets them. Both tests below use a plugin module that lives in the package under test:

```python
import json

from fluid_build.testing.cli import run_fluid
from fluid_build.testing.entry_points import IAC_GROUP, PROVIDER_GROUP, installed_plugin
from fluid_build.testing.env import isolated_env

CONTRACT = """\
fluidVersion: "0.7.5"
kind: DataProduct
id: orders
name: Orders
metadata:
  owner:
    team: data-platform
exposes:
  - exposeId: events
    kind: table
    binding:
      platform: kubernetes
      format: table
      location:
        name: events
    contract:
      schema:
        - name: id
          type: string
"""


def test_the_provider_is_listed_inside_the_block_only(tmp_path, capfd):
    groups = {PROVIDER_GROUP: {"acme": "acme_cloud.provider:AcmeProvider"}}
    with isolated_env(tmp_path):
        with installed_plugin(tmp_path / "site", "acme-cloud", groups, {}):
            code, out, err = run_fluid(capfd, "providers")
            inside = json.loads(out)["providers"]
        code, out, err = run_fluid(capfd, "providers")
        after = json.loads(out)["providers"]
    assert "acme" in inside
    assert "acme" not in after


def test_generate_iac_runs_through_the_plugin(tmp_path, capfd):
    (tmp_path / "contract.fluid.yaml").write_text(CONTRACT)
    groups = {IAC_GROUP: {"kubernetes": "acme_kube.plugin:KubePlugin"}}
    with isolated_env(tmp_path):
        with installed_plugin(tmp_path / "site", "acme-kube", groups, {}):
            code, out, err = run_fluid(
                capfd, "generate", "iac", "contract.fluid.yaml", "--out", "infra"
            )
    assert code == 0
    assert (tmp_path / "infra" / "main.tf.json").is_file()
```

`fluid providers` prints `{"providers": [...]}`. With the plugin installed it lists `acme` beside the built-ins, and after the block it does not. The IaC test needs a contract whose `binding.platform` is one the schema lists and no built-in emitter serves: `kubernetes`, `postgres` or `kafka`. Without the plugin, `fluid generate iac` stops with `generate_iac_no_provider`. With it, it writes the module, and after the block the same command fails again:

```text
Wrote OpenTofu module: infra/main.tf.json  (provider: kubernetes, 1 resources)

Review and apply with OpenTofu:
  tofu -chdir=infra init
  tofu -chdir=infra plan
```

See [Shipping an IaC plugin](./entry-points.md#shipping-an-iac-plugin) for what the plugin has to implement, and the [trust model](./trust-model.md) for the allow and block lists that `isolated_env` clears.

## `FakeHttpServer`

`FakeHttpServer` stands in for a remote service. It listens on `127.0.0.1` on a free port, answers from a table of routes and keeps what it saw. It knows nothing about one service, so your tests register the routes of yours, or subclass it and register them in `__init__`.

```python
import json
import urllib.request

from fluid_build.testing.http_fake import FakeHttpServer


def test_the_fake():
    with FakeHttpServer() as fake:
        fake.add_route(
            "GET", r"/v1/items/(?P<item>\d+)", lambda request, match: (200, {"id": match["item"]})
        )
        with urllib.request.urlopen(fake.endpoint + "/v1/items/7") as response:
            assert json.load(response) == {"id": "7"}
        assert [request.path for request in fake.requests] == ["/v1/items/7"]
    assert fake.unknown == []
```

Use it as a context manager, or call `start()` and `stop()`. `stop()` twice is harmless. `endpoint` is `http://127.0.0.1:<port>` (`https://` with a TLS context) and raises `RuntimeError` when the server is not running.

**Routes.** `add_route(method, pattern, handler)` answers requests of that method whose whole path matches the regular expression `pattern`. Use named groups for path parameters. Routes are tried in the order you added them, and the first match wins. The server answers `DELETE`, `GET`, `HEAD`, `OPTIONS`, `PATCH`, `POST` and `PUT`, and refuses a route for another method with a `ValueError`. A `HEAD` answer has its headers and no body. It reads a request body by its `Content-Length` or as chunked, and answers a malformed one with `400`.

**Handlers.** `handler(request, match)` gets a `Request` and the `re.Match`, and returns `(status, payload)` or `(status, payload, headers)`:

| Payload | Body | `Content-Type` added |
|---|---|---|
| `None` | empty | none |
| `bytes` | the bytes | `application/octet-stream` |
| `str` | UTF-8 text | `text/plain; charset=utf-8` |
| anything else | `json.dumps` of it | `application/json` |

A `Content-Type` you give in `headers` wins. `headers` holds one value per name, in Latin-1 and without line breaks. The `Content-Length` is always the body's, so one you give is ignored. A 1xx, 204 or 304 answer has no body.

**Failure injection.** `fail_route(method, path_part, status=400, body=...)` answers every later request of that method whose path contains `path_part` with that status. `path_part` is a regular expression searched in the path, so `re.escape` it for a literal. The rule is checked before the routes and holds until you remove it with `fake.failing_routes.clear()`. The body defaults to `INJECTED_FAILURE`, `{"message": "injected failure"}`. The status defaults to 400, because a client that retries on 5xx does not retry a 4xx: pass `503` to exercise the retry.

**What it kept.** All of these are safe to read once the client call has returned:

| Attribute | Holds |
|---|---|
| `requests` | Every request, in order, as `Request(method, path, query, headers, body)`. `path` is percent-decoded and has no query string, `query` is `parse_qs` of it (blank values kept), `headers` has lower-case names and a repeated header keeps its last value, and `request.json()` parses the body, or gives `None` when there is none. |
| `unknown` | The requests no route matched. Each got a 404 with `{"message": "no route for GET /x"}`. Assert that it is empty. |
| `errors` | The exceptions a handler raised. Each got a 500 whose body is `{"message": "<ExceptionName>: <text>"}`. |
| `routes`, `failing_routes` | The route table and the failure rules, in match order. |

Handlers run one at a time, under `fake.lock` (an `RLock`), so they may change shared state freely. Take the lock yourself when a test changes state that a handler reads.

### HTTPS

Give `FakeHttpServer(ssl_context=...)` a server-side `ssl.SSLContext` that already holds a certificate chain, and it answers over TLS. A client context is refused with a `ValueError`. The kit makes no certificates: a test makes its own and trusts it in the client under test. `cryptography` is one of the CLI's dependencies, so it is installed with it and can make a self-signed certificate for `127.0.0.1`:

::: details A self-signed certificate for 127.0.0.1

```python
import datetime
import ipaddress

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def self_signed(directory):
    """Write loopback.pem and loopback.key into `directory`; return their paths."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "loopback.pem", directory / "loopback.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path
```

:::

```python
import ssl
import urllib.request

from fluid_build.testing.http_fake import FakeHttpServer


def test_the_client_trusts_the_fake(tmp_path):
    cert_path, key_path = self_signed(tmp_path)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    client_context = ssl.create_default_context(cafile=str(cert_path))
    with FakeHttpServer(ssl_context=server_context) as fake:
        assert fake.endpoint.startswith("https://127.0.0.1:")
        fake.add_route("GET", "/ping", lambda request, match: (200, {"ok": True}))
        with urllib.request.urlopen(fake.endpoint + "/ping", context=client_context) as response:
            assert response.status == 200
```

Without `client_context`, the client rejects the certificate, as it should. If the client under test takes its CA bundle from the environment, pass the certificate file in `isolated_env(set_vars={"SSL_CERT_FILE": str(cert_path)})`, and check when the client reads it. On Python 3.12 and newer, `urllib.request.urlopen` builds its TLS context on the first call in the process and keeps it, so a test that runs after any earlier `urlopen` call in the same process does not see the variable, and fails with `CERTIFICATE_VERIFY_FAILED`. On Python 3.11 each connection reads it. Give the client the bundle explicitly where you can.

## See also

- [Apply hook journey](../journeys/apply-hook.md): writing the hook, step by step
- [Entry points](./entry-points.md): the groups and their signatures
- [Packaging](./packaging.md): the `pyproject.toml` template and the SDK's conformance harness
- [Trust model](./trust-model.md): what the CLI guarantees about plugin execution
