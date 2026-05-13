# Typed Errors

When a `fluid forge` run fails, the agent layer raises one of seven typed exception classes that distinguish operationally different failure modes. They all inherit from `FluidError` so existing `except FluidError:` callers keep working — but the new classes let the retry envelope honor `Retry-After` headers, fail fast on non-retryable errors, and route corrective feedback to the LLM instead of retrying the same broken prompt.

This page is the operator-facing reference. Read it when a run fails with one of these classes and you're trying to figure out what to do.

## When you'll see these

The hierarchy lives at `fluid_build.copilot.agents.errors`. All seven classes inherit from `AgentExecutionError` → `FluidGenerationError` → `FluidError`:

```
FluidError
  └── FluidGenerationError
        └── AgentExecutionError
              ├── ProviderError
              │     ├── RateLimitError
              │     ├── ProviderTimeoutError
              │     ├── ContextOverflowError
              │     ├── ProviderAuthError
              │     └── ProviderServerError
              ├── SchemaValidationError
              └── ToolValidationError
```

Each `ProviderError` subclass carries `provider`, `status_code`, and (when relevant) a `retry_after` float in seconds. `SchemaValidationError` carries `schema_name`, `validation_errors`, and the offending `raw_output`. `ToolValidationError` carries `tool_name`, `tool_args`, and a redacted `reason`.

## Error reference

### `RateLimitError`

**When it fires:** the provider returned HTTP 429, or a 5xx with a `Retry-After` header.

**What the retry envelope does:** honors the server-supplied `retry_after` value (parsed from the `Retry-After` header, capped at 5 minutes) and sleeps for exactly that long before retrying. Default exponential backoff is overridden — the goal is to NOT hammer rate-limited endpoints into longer cool-downs.

**What you should do:** usually nothing — the retry handles it. If the run aborts after 3 attempts, your account is genuinely throttled. Wait the printed `retry_after` interval before re-running.

**Common cause:** running multiple `fluid forge` invocations in parallel against the same Anthropic / OpenAI key.

### `ContextOverflowError`

**When it fires:** the pre-flight token budget check refused the prompt because `system_prompt + user_prompt` exceeds `context_window - output_reservation` for the resolved model. Or the provider returned a context-length-exceeded error at submit time.

**What the retry envelope does:** **non-retryable.** Fails fast. Re-issuing the same prompt against the same model is guaranteed to fail again, so the envelope doesn't waste credits on it.

**What you should do:** compact the inputs or pick a longer-context model. Concrete options:

- Switch to a model with a larger window — `claude-opus-4-7` (1M), `gemini-2.5-pro` (2M), `gpt-4.1` (1M).
- Override the assumed window per-session via `capability_matrix["context_window"]` (useful for custom-deployed Azure/Ollama models with extended context).
- Trigger the multi-turn agent loop's compaction earlier with `FLUID_AGENT_COMPACT_AFTER=4` (default 6).
- For the multi-turn loop specifically, set `FLUID_COMPACTION_STRATEGY=summarize` or `hybrid` — see [Agentic primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-preflight-and-compaction).

**Common cause:** running on a tight-context Ollama model (`gemma2` 8K, `phi-3` 4K) with a verbose intent file or a long agent loop that accumulated tool results.

### `ProviderTimeoutError`

**When it fires:** `httpx` raised `TimeoutException` — read or connect timeout. Retryable with the standard exponential backoff (1s → 2s → 4s, capped at 8s, with up to 10% jitter).

**What you should do:** if it persists beyond 3 retries, check your network. Increase `FLUID_LLM_TIMEOUT_SECONDS` if you're running through a slow proxy. For Ollama on a small GPU, local inference of a 30B+ model can legitimately take >2 minutes — bump the timeout or switch to a smaller model.

### `ProviderAuthError`

**When it fires:** HTTP 401 or 403. The API key is invalid, expired, or scoped wrong (or, for Anthropic enterprise PATs, the lifetime exceeds the org policy).

**What the retry envelope does:** **non-retryable.** Surfaces immediately so you know to fix the credentials. Retrying with the same broken key just burns time.

**What you should do:**

- Re-check the env var (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`) is set in the shell that's running the CLI.
- For `fluid ai setup`-managed keys: `fluid ai setup --provider <name>` to re-enter.
- For Anthropic enterprise users: confirm your PAT lifetime is ≤365 days if your org has the fine-grained-PAT-lifetime restriction.

### `ProviderServerError`

**When it fires:** HTTP 5xx without a `Retry-After` header — generic transient. Retryable with exponential backoff.

**What you should do:** usually nothing — the retry handles it. If the run aborts after 3 attempts, the provider's status page is the next stop.

### `SchemaValidationError`

**When it fires:** the LLM returned output that failed Pydantic / JSON-schema validation against the stage's expected output model. Carries `schema_name`, the list of `validation_errors`, and the `raw_output`.

**What the retry envelope does:** **non-retryable** in the envelope itself — re-prompting with the same input gives the same broken output. **But the agent loop layer** intercepts these and routes a corrective message back to the LLM ("your previous output failed validation with these specific errors: …, please correct your approach"), which usually fixes it on the next iteration. So in practice you rarely see this surface to the CLI.

**What you should do (when it does surface):**

- Read the printed `validation_errors`. If the LLM is consistently emitting a wrong shape for one stage, the model is likely below the structured-output bar — switch to a stronger model.
- For Gemini specifically: `gemini-1.5-flash` may struggle with very large nested schemas; try `gemini-2.5-flash` or `gemini-2.5-pro`.
- For OpenAI specifically: enable `FLUID_OPENAI_STRICT_SCHEMA=1` (see [OpenAI strict schema](#openai-strict-schema-mode) below).

### `ToolValidationError`

**When it fires:** an LLM-issued tool call had wrong arg types, missing required fields, an unknown tool name, or hit the workspace-confinement boundary (path outside the workspace root).

**What the retry envelope does:** non-retryable directly. Like `SchemaValidationError`, the agent loop converts it into a corrective message — `"Tool X failed with class ToolValidationError. Your tool arguments did not match the tool's input schema. Re-read the tool's schema definition above and submit values that satisfy every required field with the correct types."`

**What you should do:** usually nothing — the corrective-feedback loop fixes it. If you see this repeatedly across iterations, the LLM is probably below the tool-use accuracy bar (common on Ollama llama3.1 — see [Capability Warnings](capability-warnings.md) for the per-model accuracy notes).

## How errors flow through a run

### Corrective-feedback layer

The multi-turn agent loop appends a deterministic guidance message to the conversation right after a failed tool call:

```
[user] Tool ``read_sample_schema`` failed with error class ``ToolValidationError``.
       Your tool arguments did not match the tool's input schema. Re-read the tool's
       schema definition above and submit values that satisfy every required field
       with the correct types.
```

The guidance is keyed off the error class only — never quotes the original `error_message`. That keeps the security posture intact (see next section) while still giving the LLM enough signal to course-correct on the next turn instead of retrying the same broken call until the iteration cap fires.

### What gets scrubbed before reaching the LLM (S-013)

Tool-dispatch failures return `{"error": "<ClassName>", "message": "Tool '<name>' failed — see server logs"}` to the LLM-bound result, NOT the raw exception text. The full detail is logged server-side via `LOG.warning(...)` for operator debugging.

This is the SECURITY_REVIEW S-013 invariant: paths under `$HOME`, hostnames, env-var values, and any config fragments quoted into derived `CopilotGenerationError` instances stay out of the model context. Codified by `tests/test_slice_ux_k_agent_loop.py::test_tool_failure_does_not_leak_path_like_exception_text` and the parallel `test_forge_tool_failure_does_not_leak_path_via_bridge` (added when the `@forge_tool` migration created a new dispatch path that needed the same scrubbing).

## Mapping from provider exceptions

The internal helper `classify_provider_error()` (in `fluid_build.copilot.agents.error_classification`) maps low-level `httpx` exceptions to the right typed class:

| Source exception | Mapped to | Why |
|---|---|---|
| `httpx.TimeoutException` | `ProviderTimeoutError` | Network / read timeout |
| `httpx.HTTPStatusError` 429 | `RateLimitError` | Rate-limit; honors `Retry-After` |
| `httpx.HTTPStatusError` 401/403 | `ProviderAuthError` | Auth failure; non-retryable |
| `httpx.HTTPStatusError` 5xx | `ProviderServerError` | Transient; retryable |
| `httpx.HTTPStatusError` 400 with `context_length_exceeded`-style body | `ContextOverflowError` | Body string-match fallback |
| Other `HTTPStatusError` | generic `ProviderError` | Not a known recoverable shape |
| Pydantic `ValidationError` on output | `SchemaValidationError` | Wrapped in `BaseStageAgent._call_once` |

## OpenAI strict-schema mode

OpenAI's strict `response_format = json_schema` mode requires every object node in the schema to declare `additionalProperties: false` AND list every property under `required`. The legacy `FORGE_RESPONSE_SCHEMA` has nested objects (`contract`, `additional_files`) that intentionally use `additionalProperties: true` because the contract is free-form — sending that schema to strict mode used to return a 400 `Invalid schema for response_format`.

`FLUID_OPENAI_STRICT_SCHEMA=1` enables a recursive walker that hardens the schema (deep-copy + strict-mode rewrite) before submission. Free-form nested objects are rewritten as JSON-encoded strings so the LLM can still return arbitrary nested data; the caller `json.loads`-es those fields. Default is OFF for one release while the corpus replay suite signs off.

## See also

- [Agentic Primitives → Token-budget pre-flight & compaction](agentic-primitives.md#token-budget-preflight-and-compaction) — what `ContextOverflowError` is preventing
- [Capability Warnings](capability-warnings.md) — the run-start banner that catches degraded combos before they fail
- [LLM Providers → Environment variables](llm-providers.md#environment-variables) — `FLUID_OPENAI_STRICT_SCHEMA`, `FLUID_AGENT_COMPACT_AFTER`, etc.
- [Custom Providers → Error Handling](/forge_docs/providers/custom-providers#error-handling) — how infrastructure-provider errors (`ProviderError`, `ProviderInternalError`) relate to (and are distinct from) these copilot-layer errors
