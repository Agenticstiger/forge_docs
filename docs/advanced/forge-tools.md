# Authoring Forge Tools

Tools are what the multi-turn copilot agent calls during a `fluid forge --agent-loop` run — `discover_workspace`, `read_sample_schema`, `propose_contract`, `validate_contract`, `list_templates`, `list_schedulers`. They're how the LLM reaches out of its context to inspect the user's workspace, sample data, and generate scaffolding.

The `@forge_tool` decorator collapses tool registration to a single declaration where the Pydantic args-model is the source of truth. This page is the contributor guide for adding a new tool.

## Quick start: a tool in 20 lines

```python
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from fluid_build.cli.forge_tool import forge_tool


class FetchOrdersArgs(BaseModel):
    since: str = Field(description="ISO-8601 lower bound, e.g. 2024-01-01")
    limit: int = Field(default=100, ge=1, le=1000)


@forge_tool(
    name="fetch_orders",
    description="Page through the orders table since a given date.",
    args_schema=FetchOrdersArgs,
    workspace_root_aware=True,
)
def fetch_orders(args: FetchOrdersArgs, *, workspace_root: Optional[Path] = None):
    return _fetch_impl(workspace_root, args.since, args.limit)
```

That's the whole pattern. The decorator handles registration, JSON Schema generation from the Pydantic model, args-model validation, `workspace_root` injection, and the typed-error return shape that `dispatch_tool_call` consumes downstream.

## The `@forge_tool` decorator

### Required arguments

- **`args_schema`** — a Pydantic `BaseModel` subclass describing the tool's input. The decorator rejects non-Pydantic schemas at decoration time. JSON Schema for the LLM is derived from this model — you don't write it twice.

### Optional arguments

- **`name`** — the tool name as exposed to the LLM. Defaults to the function's `__name__`. Use snake_case. Must be unique across the merged `TOOL_REGISTRY` + `FORGE_TOOL_REGISTRY` surface; on collision the legacy registry wins (see [Migration](#migrating-from-the-legacy-_register-pattern)).
- **`description`** — the tool description shown to the LLM. Defaults to the first line of the function's docstring.
- **`workspace_root_aware`** — `True` if the tool reads from / writes to the user's workspace. The dispatcher will plumb a resolved `workspace_root: Path` kwarg into your function. The args-schema does **not** include `workspace_root` — the LLM cannot supply it, by construction. See [Security: workspace confinement](#security-workspace-confinement) below.
- **`tags`** — optional taxonomy labels. Reserved for future use by the capability matrix to scope tool subsets per provider.
- **`register`** — `True` (default) registers the tool in `FORGE_TOOL_REGISTRY` at decoration time. Set `False` for tools that should be built on demand by tests / fixtures.

### What the function receives

Your function takes the validated args-model instance as the first positional argument:

```python
@forge_tool(name="echo", description="...", args_schema=EchoArgs)
def echo(args: EchoArgs):
    return {"echoed": args.text}
```

If you set `workspace_root_aware=True`, you also receive `workspace_root` as a keyword argument:

```python
@forge_tool(
    name="read_file",
    description="...",
    args_schema=ReadFileArgs,
    workspace_root_aware=True,
)
def read_file(args: ReadFileArgs, *, workspace_root: Path):
    confined = workspace_root / args.relative_path
    confined.resolve().relative_to(workspace_root.resolve())  # confinement check
    return {"content": confined.read_text()}
```

### What the function returns

Anything JSON-serialisable. The dispatcher routes the return value back to the LLM as the tool result. Best practice: return a dict with a stable shape so the LLM's reasoning over multiple turns sees the same keys.

If your function raises, the error is caught, the class name is captured, and the dispatcher returns a typed `{"error": "<ClassName>", "message": "Tool '<name>' failed — see server logs"}` to the LLM. Never quote sensitive data (paths, env vars, internal config) in raised exception messages — see [Error handling inside a tool](#error-handling-inside-a-tool) below.

## Pydantic args model contract

Three rules for the args-model:

1. **Every arg the LLM should be able to set goes here.** Required fields use `Field(description="…")` without a default. Optional fields use `Field(default=…, description="…")`.
2. **Don't include injected fields.** `workspace_root`, sessions, db connections, etc. are dispatcher-injected and must NOT appear in the args-schema. The LLM can't see them and can't supply them.
3. **`additionalProperties: false` is automatic.** The decorator's `input_schema` property sets `additionalProperties: false` so the LLM can't sneak extra fields past validation.

Example with all three rules:

```python
class ReadSampleSchemaArgs(BaseModel):
    # Required field — no default, has description for the LLM
    path: str = Field(description="Absolute or relative path to the sample file.")

    # Optional field with default
    max_rows: int = Field(default=1000, ge=1, le=100_000,
                          description="Cap on rows read for inference.")

    # NO workspace_root field — that's dispatcher-injected
```

Free-form `Dict[str, Any]` fields are allowed when the inner shape is genuinely user-provided:

```python
class ProposeContractArgs(BaseModel):
    context: Dict[str, Any] = Field(
        description="User context with project_goal, data_sources, use_case, etc."
    )
    template: str = Field(default="starter")
    provider: str = Field(default="local")

    # Permit nested free-form objects in ``context`` — the LLM should not
    # be limited to a fixed schema for it.
    model_config = {"extra": "allow"}
```

## Security: workspace confinement

If your tool touches the filesystem, you **must** set `workspace_root_aware=True` and confine reads/writes to the resolved root. The pattern from `read_sample_schema`:

```python
@forge_tool(
    name="read_sample_schema",
    description="Infer the schema of a single data file.",
    args_schema=ReadSampleSchemaArgs,
    workspace_root_aware=True,
)
def _dispatch_read_sample_schema(args, *, workspace_root):
    effective_root = (workspace_root or Path.cwd()).resolve()

    # Resolve the LLM-supplied path; either absolute or relative to root.
    raw = Path(args.path)
    resolved = (raw if raw.is_absolute() else effective_root / raw).resolve()

    # SECURITY: confinement check — refuse paths outside the workspace.
    try:
        resolved.relative_to(effective_root)
    except ValueError:
        return {"error": "path_outside_workspace",
                "message": "Path is outside the workspace root."}

    # SECURITY: extension allow-list (fail closed).
    if resolved.suffix.lower() not in _ALLOWED_SAMPLE_SUFFIXES:
        return {"error": "unsupported_file_type", "message": "..."}

    # SECURITY: size cap before parsing.
    size = resolved.stat().st_size
    if size > _MAX_SAMPLE_FILE_SIZE_BYTES:
        return {"error": "file_too_large", "message": "..."}

    return _do_the_actual_work(resolved)
```

Three pillars of the confinement model:
- **Resolve before checking** — symlinks and `..` components are resolved first, so the `relative_to(effective_root)` check is on the canonical path.
- **Allow-list, not deny-list** — for file types, paths, and any other LLM-controlled input. Fail closed.
- **Size cap before parsing** — protects against a 50GB CSV the LLM didn't notice was huge.

## Error handling inside a tool

There are two error-shape conventions you can use.

### Return a typed-error dict

For "user-fixable" failures (path outside workspace, file too large, unsupported extension), **return** a dict with `error` + `message`:

```python
return {"error": "path_outside_workspace",
        "message": "Path is outside the workspace root."}
```

The dispatcher passes this dict through to the LLM as the tool result. The agent loop's [corrective-feedback layer](typed-errors.md#corrective-feedback-layer) recognises common error class names and appends a guidance message — keep your `error` strings consistent with the catalogued ones (`UnknownTool`, `ToolValidationError`, `PathTraversalError`, `ForbiddenPathError`, `FileNotFoundError`, etc.) for the best match.

### Raise an exception

For unexpected failures (the impl's own bugs, third-party library exceptions, etc.), just raise. The dispatcher catches all exceptions and returns the typed shape automatically:

```python
@forge_tool(name="boom", description="...", args_schema=...)
def boom(args):
    raise RuntimeError("internal-detail-do-not-leak")

# Dispatcher returns to the LLM:
#   {"error": "RuntimeError", "message": "Tool 'boom' failed — see server logs"}
```

### S-013 invariant: never echo raw exception text to the LLM

The dispatcher **scrubs** the original `str(exc)` from the dict that flows to the LLM and replaces it with a static `"see server logs"` message. The full detail is logged via `LOG.warning(...)` for operator debugging.

This is the SECURITY_REVIEW S-013 invariant. Without it, exceptions like `FileNotFoundError("/home/alice/.aws/credentials")` would leak filesystem paths or env-var values straight into the LLM context, where they could be echoed back into the user's reply or surface in third-party observability sinks.

The codified test at `tests/copilot/test_forge_tool_decorator.py::test_legacy_impl_does_not_leak_exception_text_to_llm` and the parallel `test_forge_tool_failure_does_not_leak_path_via_bridge` in `tests/test_slice_ux_k_agent_loop.py` pin this behaviour. Don't disable the scrubbing — log full detail server-side instead.

## Testing your tool

The standard test layout (mirrors what's in `tests/copilot/test_forge_tool_decorator.py`):

```python
import pytest
from pydantic import BaseModel, Field

from fluid_build.cli.forge_tool import (
    FORGE_TOOL_REGISTRY,
    dispatch_forge_tool,
    forge_tool,
)


class FetchOrdersArgs(BaseModel):
    since: str = Field(description="...")
    limit: int = Field(default=100)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Snapshot/restore so the production tools registered at module-import
    time aren't wiped between tests under pytest-randomly."""
    saved = dict(FORGE_TOOL_REGISTRY)
    FORGE_TOOL_REGISTRY.clear()
    yield
    FORGE_TOOL_REGISTRY.clear()
    FORGE_TOOL_REGISTRY.update(saved)


def test_fetch_orders_dispatches_and_returns_value():
    @forge_tool(name="fetch_orders", description="...", args_schema=FetchOrdersArgs)
    def impl(args):
        return {"rows": []}

    result = dispatch_forge_tool("fetch_orders", {"since": "2024-01-01", "limit": 50})
    assert result.ok
    assert result.value == {"rows": []}


def test_fetch_orders_validates_args():
    @forge_tool(name="fetch_orders", description="...", args_schema=FetchOrdersArgs)
    def impl(args):
        return {"rows": []}

    # Missing required ``since``
    result = dispatch_forge_tool("fetch_orders", {"limit": 50})
    assert not result.ok
    assert result.error_type == "ToolValidationError"
```

::: warning Snapshot/restore the registry in your fixture
The naive pattern of `FORGE_TOOL_REGISTRY.clear()` on teardown wipes the production tools registered at module-import time. Under `pytest-randomly`'s shuffled order, that breaks any subsequent test relying on those tools (e.g. the agent-loop tests). The snapshot/restore pattern above is what the project standardises on.
:::

## Migrating from the legacy `_register` pattern

The legacy pattern looked like this — three artefacts to keep in sync:

```python
def _dispatch_my_tool(*, path: str, **_kw):
    ...

_register(
    name="my_tool",
    description="...",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "..."},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    impl=_dispatch_my_tool,
)
```

To migrate:

1. Replace the JSON-Schema dict with a Pydantic model.
2. Refactor the impl to take `args: MyArgs` as the first positional arg instead of `**kwargs`. Field accesses become `args.path`, etc.
3. Replace the `_register(...)` call with the `@forge_tool(...)` decoration on the impl.
4. If the tool touches the filesystem, set `workspace_root_aware=True` and accept `workspace_root` as a kwarg.

The legacy `_register` helper still exists as a back-compat shim — drop-in code from older forks won't break. New tools should use `@forge_tool`.

## Registration & discovery

`@forge_tool`-decorated tools are registered in `FORGE_TOOL_REGISTRY` at module-import time. `dispatch_tool_call(name, args, workspace_root=…)` resolves names through both registries:

1. Legacy `TOOL_REGISTRY` — hand-written dict entries.
2. `FORGE_TOOL_REGISTRY` — Pydantic-typed `@forge_tool` registrations.
3. Staged `_FORGE_DATA_MODEL_TOOL` fallback (gated behind `FLUID_FORGE_STAGED_TOOL_LOOP=1`).

`get_tool_definitions()` returns the merged surface in the shape providers expect, so the LLM sees both registries' tools without needing to know which mechanism registered them.

## Checklist: definition of done

Before opening a PR for a new tool:

- [ ] Pydantic args-model with field-level descriptions
- [ ] `workspace_root_aware=True` set if the impl touches the filesystem
- [ ] Confinement check + extension allow-list + size cap (if filesystem-touching)
- [ ] Errors raised, not swallowed (the dispatcher converts to typed-error dicts)
- [ ] No `str(exc)` quoting in user-facing return messages — keep S-013 scrubbing intact
- [ ] Unit tests cover happy path + arg-validation failure + impl-exception path
- [ ] Snapshot/restore fixture for registry isolation under `pytest-randomly`
- [ ] One-line entry in the agent-loop system prompt (`AGENT_SYSTEM_PROMPT` in `forge_copilot_agent_loop.py`) so the LLM knows when to call your tool

## See also

- [Typed Errors](typed-errors.md) — what `ToolValidationError`, `SchemaValidationError`, and the corrective-feedback flow look like
- [Capability Warnings](capability-warnings.md) — which (provider, model) combos can call tools reliably
- [Agentic Primitives](agentic-primitives.md) — the staged-pipeline model your tool plugs into
- [Contributing Guide → Contribute a Forge Tool](/forge_docs/contributing#contribute-a-forge-tool-forge-tool) — the short version of this page
