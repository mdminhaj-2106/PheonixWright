# PhoenixWright — Master Upgrade Plan
## Structural Refactor + Robustness Hardening

> Two-track upgrade: first we get the architecture right, then we make it bulletproof.
> Every step is atomic and confirmation-gated before the next one begins.

---

## Why Two Tracks?

| Track | Goal | Risk if skipped |
|---|---|---|
| **Track A — Structure** | Proper LangGraph ownership, clean modules, testable nodes | Future robustness work will embed bugs into wrong layers |
| **Track B — Robustness** | Retry, backoff, observability, complex workflow support | Already designed but has no stable foundation to sit on |

Track A must complete first. Each PR-sized step inside Track A is a pre-condition for the next.

---

## Current State Diagnosis

### The Core Inversion Problem

```
Current ownership:                Correct ownership:
┌─────────────────────┐           ┌──────────────────────────┐
│  ChatOrchestrator   │           │    ChatOrchestrator       │
│  (thin wrapper)     │           │    owns LangGraph          │
│   └─ calls ──►      │           │    routes retry/fallback   │
│  LangGraphDecomposer│           │    compiles prompt         │
│  (owns the graph)   │           └──────────┬───────────────┘
│  - StateGraph       │                      │ delegates to
│  - node fns         │           ┌──────────▼───────────────┐
│  - retry routing    │           │    PlannerNodes (pure fns) │
│  - validation       │           │    - draft_plan            │
│  - prompt compile   │           │    - validate_plan         │
└─────────────────────┘           │    - compile_prompt        │
                                  └──────────────────────────┘
```

### Module Responsibility Violations (current)

| File | Current responsibility | Should be |
|---|---|---|
| `decomposer.py` | Owns StateGraph, routing, LLM calls, validation | Thin adapter / compatibility shim |
| `chat_orchestrator.py` | Calls decomposer, wraps result | Graph owner, state manager, retry router |
| `plan_types.py` | Holds `PlannerState` TypedDict | State should live in orchestrator module |
| `plan_prompt.py` | Standalone prompt builder | Node fn input, stays as util |
| `runner.py` | Calls orchestrator correctly | No change needed |

---

## Track A — Structural Refactor

### Guiding Principles
- No behavior change during Track A. Every step is a pure refactor.
- Tests must pass at every step.
- Each step below maps to one confirmation checkpoint.

---

### Step A-1 — Canonical State in Orchestrator Module

**What changes:**
- Move `PlannerState` TypedDict from `agent/planner/plan_types.py` into `agent/orchestrator/state.py`
- Extend it with fields needed for the full graph: `fallback_used`, `validation_error_count`
- Keep `PlanPackage` dataclass in `plan_types.py` (it is a result type, not graph state)

**New file:** `agent/orchestrator/state.py`
```python
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import TypedDict
from agent.planner.schemas import TaskGraph

class PlannerState(TypedDict, total=False):
    request: str
    history: List[Tuple[str, str]]
    raw_plan: str
    payload: Dict[str, Any]
    graph_obj: Optional[TaskGraph]
    compiled_prompt: str
    error: str
    attempts: int
    fallback_used: bool
    validation_error_count: int
```

**Modified files:**
- `agent/planner/plan_types.py` — import `PlannerState` from orchestrator.state, re-export for backward compat
- `agent/orchestrator/__init__.py` — export `PlannerState`

**Tests to pass:**
- `tests/test_planner.py` — all 3 existing tests unchanged
- Import smoke test: `from agent.orchestrator.state import PlannerState`

**Confirmation gate:** ✅ All existing tests pass, no import errors.

---

### Step A-2 — Extract Pure Node Functions

**What changes:**
- Create `agent/orchestrator/nodes.py`
- Extract the 3 LangGraph node functions from `decomposer.py._build_plan_with_langgraph` into pure, importable functions
- Each function takes `PlannerState` → returns partial `PlannerState` dict
- Node functions receive collaborators (llm, validator, policy) via closure factory

**New file:** `agent/orchestrator/nodes.py`
```python
"""
Pure LangGraph node functions for the planning workflow.
Each function is a state transformer: PlannerState -> dict[str, Any]
Collaborators are injected via factory closures to keep nodes testable.
"""
from __future__ import annotations
from typing import Any, Callable, Dict
from agent.orchestrator.state import PlannerState
from agent.planner.plan_parser import graph_from_payload, message_to_text, parse_payload
from agent.planner.plan_prompt import build_planner_prompt
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


def make_draft_plan_node(llm: Any, policy: DashboardPolicy) -> Callable[[PlannerState], Dict]:
    """Factory: returns a draft_plan node fn bound to the given llm + policy."""
    def draft_plan(state: PlannerState) -> Dict:
        prompt = build_planner_prompt(
            request=state["request"],
            history=state.get("history", []),
            policy=policy,
            prior_error=state.get("error", ""),
        )
        raw = message_to_text(llm.invoke(prompt))
        return {
            "raw_plan": raw,
            "attempts": state.get("attempts", 0) + 1,
            "error": "",
        }
    return draft_plan


def make_validate_plan_node(
    validator: TaskGraphValidator,
) -> Callable[[PlannerState], Dict]:
    """Factory: returns a validate_plan node fn bound to the given validator."""
    def validate_plan(state: PlannerState) -> Dict:
        try:
            payload = parse_payload(state.get("raw_plan", ""))
            graph_obj = graph_from_payload(payload, user_request=state["request"])
            validator.validate(graph_obj)
            return {
                "payload": payload,
                "graph_obj": graph_obj,
                "error": "",
            }
        except Exception as exc:
            current_count = state.get("validation_error_count", 0)
            return {
                "error": str(exc),
                "validation_error_count": current_count + 1,
            }
    return validate_plan


def make_compile_prompt_node(policy: DashboardPolicy) -> Callable[[PlannerState], Dict]:
    """Factory: returns a compile_prompt node fn that builds the final agent prompt."""
    def compile_prompt(state: PlannerState) -> Dict:
        graph = state.get("graph_obj")
        history = state.get("history", [])
        if graph is None:
            return {"compiled_prompt": ""}

        history_lines = []
        for idx, (user_turn, agent_turn) in enumerate(history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {user_turn}")
            history_lines.append(f"Turn {idx} agent: {agent_turn}")

        sections = [
            "You are PhoenixWright admin automation agent.",
            f"Hard boundary: Operate ONLY inside {policy.allowed_origin}.",
            policy.allowed_paths_description(),
            "If navigation drifts to another domain, immediately return to the dashboard.",
            "",
            f"User intent: {graph.intent}",
            f"Original request: {graph.user_request}",
            "",
            "Execution plan (follow in order, respecting dependencies):",
            *graph.to_step_lines(),
        ]
        if graph.notes:
            sections += ["", "Plan notes:", *[f"- {n}" for n in graph.notes]]
        if history_lines:
            sections += ["", "Recent conversation context:", *history_lines]
        sections += [
            "",
            "Completion requirements:",
            "1. Provide a concise outcome summary.",
            "2. Include key fields changed (name, email, license, password if generated).",
            "3. Mention any failure point with exact step id.",
        ]
        return {"compiled_prompt": "\n".join(sections)}
    return compile_prompt
```

**Modified files:**
- `agent/decomposer.py` — `_build_plan_with_langgraph` now imports and uses these node factories instead of inline closures. Behavior identical.

**Tests to add:** `tests/test_nodes.py`
```python
def test_draft_plan_node_increments_attempts():
    ...

def test_validate_plan_node_captures_error():
    ...

def test_compile_prompt_node_contains_hard_boundary():
    ...
```

**Confirmation gate:** ✅ All old tests pass. New node unit tests pass.

---

### Step A-3 — Extract Routing Logic

**What changes:**
- Create `agent/orchestrator/routing.py`
- Move the `route()` conditional edge function out of `decomposer.py`
- Routing is now a pure function of state + max_attempts

**New file:** `agent/orchestrator/routing.py`
```python
from __future__ import annotations
from agent.orchestrator.state import PlannerState


def plan_route(max_attempts: int):
    """Returns routing fn for LangGraph conditional edge."""
    def route(state: PlannerState) -> str:
        has_error = bool(state.get("error"))
        under_limit = state.get("attempts", 0) < max_attempts
        if has_error and under_limit:
            return "retry"
        return "done"
    return route
```

**Modified files:**
- `agent/planner/decomposer.py` — replaces inline `route` closure with `plan_route(self.max_attempts)`

**Tests to add:** `tests/test_routing.py`
```python
def test_route_retries_when_error_and_under_limit():
    ...

def test_route_done_when_no_error():
    ...

def test_route_done_when_limit_reached():
    ...
```

**Confirmation gate:** ✅ Routing tests pass, decomposer behavior unchanged.

---

### Step A-4 — Orchestrator Owns the Graph (Main Refactor)

This is the inversion fix. The graph now lives in `ChatOrchestrator`, not `LangGraphTaskDecomposer`.

**What changes:**

`agent/orchestrator/chat_orchestrator.py` becomes the graph owner:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from langgraph.graph import END, START, StateGraph

from agent.orchestrator.nodes import (
    make_compile_prompt_node,
    make_draft_plan_node,
    make_validate_plan_node,
)
from agent.orchestrator.routing import plan_route
from agent.orchestrator.state import PlannerState
from agent.planner.fallback import minimal_fallback_graph
from agent.planner.plan_types import PlanPackage
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy
from agent.config import PLAN_MAX_ATTEMPTS, PLANNER_MODEL
import os


@dataclass
class PreparedTurn:
    package: PlanPackage
    prompt: str


class ChatOrchestrator:
    """
    Owns the LangGraph planning workflow.
    Responsible for: state shape, node wiring, retry routing, fallback.
    """

    def __init__(
        self,
        policy: DashboardPolicy | None = None,
        planner_model: str | None = None,
        max_attempts: int = PLAN_MAX_ATTEMPTS,
    ) -> None:
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)
        self.planner_model = planner_model or PLANNER_MODEL
        self.max_attempts = max_attempts
        self._graph = self._compile_graph()

    def _get_llm(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            return None
        return ChatGoogleGenerativeAI(
            model=self.planner_model, google_api_key=api_key, temperature=0
        )

    def _compile_graph(self):
        """Build and compile the LangGraph planning workflow once at init."""
        llm = self._get_llm()
        if llm is None:
            return None

        draft_node = make_draft_plan_node(llm, self.policy)
        validate_node = make_validate_plan_node(self.validator)
        compile_node = make_compile_prompt_node(self.policy)
        router = plan_route(self.max_attempts)

        workflow = StateGraph(PlannerState)
        workflow.add_node("draft_plan", draft_node)
        workflow.add_node("validate_plan", validate_node)
        workflow.add_node("compile_prompt", compile_node)
        workflow.add_edge(START, "draft_plan")
        workflow.add_edge("draft_plan", "validate_plan")
        workflow.add_conditional_edges(
            "validate_plan", router, {"retry": "draft_plan", "done": "compile_prompt"}
        )
        workflow.add_edge("compile_prompt", END)
        return workflow.compile()

    def prepare_turn(
        self, user_input: str, history: List[Tuple[str, str]]
    ) -> PreparedTurn:
        request = self.policy.sanitize_user_request(user_input)

        graph_obj = None
        compiled_prompt = ""

        if self._graph is not None:
            result = self._graph.invoke({
                "request": request,
                "history": history,
                "attempts": 0,
                "fallback_used": False,
                "validation_error_count": 0,
            })
            graph_obj = result.get("graph_obj")
            compiled_prompt = result.get("compiled_prompt", "")

        if graph_obj is None:
            graph_obj = minimal_fallback_graph(request)
            # compile prompt for fallback
            from agent.orchestrator.nodes import make_compile_prompt_node
            compile_fn = make_compile_prompt_node(self.policy)
            fallback_result = compile_fn({
                "graph_obj": graph_obj,
                "history": history,
                "request": request,
            })
            compiled_prompt = fallback_result["compiled_prompt"]

        self.validator.validate(graph_obj)
        package = PlanPackage(graph=graph_obj, compiled_prompt=compiled_prompt)
        return PreparedTurn(package=package, prompt=compiled_prompt)
```

**`LangGraphTaskDecomposer` becomes a compatibility adapter:**
```python
class LangGraphTaskDecomposer:
    """
    Compatibility adapter. Delegates to ChatOrchestrator.
    Kept so existing tests and call sites don't break.
    Will be deprecated after Track B.
    """
    def __init__(self, policy=None, planner_model=None,
                 max_attempts=PLAN_MAX_ATTEMPTS, use_langgraph=True):
        self._orchestrator = ChatOrchestrator(
            policy=policy, planner_model=planner_model, max_attempts=max_attempts
        ) if use_langgraph else None
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)
        self._use_langgraph = use_langgraph

    def build_plan(self, user_request, chat_history=None) -> PlanPackage:
        if self._use_langgraph and self._orchestrator:
            return self._orchestrator.prepare_turn(
                user_request, chat_history or []
            ).package
        # fallback path (use_langgraph=False, used in existing tests)
        request = self.policy.sanitize_user_request(user_request)
        graph = minimal_fallback_graph(request)
        self.validator.validate(graph)
        prompt = self._compile_compat_prompt(graph, chat_history or [])
        return PlanPackage(graph=graph, compiled_prompt=prompt)

    def _compile_compat_prompt(self, graph, history):
        from agent.orchestrator.nodes import make_compile_prompt_node
        fn = make_compile_prompt_node(self.policy)
        return fn({"graph_obj": graph, "history": history, "request": graph.user_request})[
            "compiled_prompt"
        ]
```

**Modified files:**
- `agent/orchestrator/chat_orchestrator.py` — full rewrite (graph owner)
- `agent/planner/decomposer.py` — becomes thin adapter
- `agent/orchestrator/__init__.py` — export `ChatOrchestrator`, `PreparedTurn`, `PlannerState`

**Tests to add:** `tests/test_orchestrator.py`
```python
def test_prepare_turn_returns_prepared_turn():
    ...

def test_orchestrator_falls_back_when_llm_unavailable():
    ...

def test_graph_compiled_once_at_init():
    ...

def test_prepare_turn_output_parity_with_old_decomposer():
    # Same input → same compiled_prompt structure
    ...
```

**Confirmation gate:** ✅ All old tests pass. New orchestrator tests pass. `runner.py` untouched.

---

### Step A-5 — Clean Up Exports and README

**What changes:**
- `agent/planner/__init__.py` — remove `LangGraphTaskDecomposer` from public API, add deprecation note
- `agent/orchestrator/__init__.py` — clean public surface
- `README.md` — update architecture diagram + module descriptions

**Updated architecture section in README:**
```text
Natural language request
        │
        ▼
┌───────────────────────────────────┐
│         ChatOrchestrator          │  ← Owns LangGraph workflow
│  ┌────────┐  ┌──────────────────┐ │
│  │ nodes/ │  │   routing.py     │ │  ← Pure node fns + retry router
│  │ state/ │  │   state.py       │ │  ← Canonical PlannerState
│  └────────┘  └──────────────────┘ │
└────────────────┬──────────────────┘
                 │ PlanPackage
                 ▼
┌───────────────────────────────────┐
│         BrowserAgentService       │  ← Gemini 2.0 Flash + Playwright
└────────────────┬──────────────────┘
                 │ HTTP (localhost:8000)
                 ▼
┌───────────────────────────────────┐
│         FastAPI Admin Panel       │  ← SQLAlchemy + SQLite
└───────────────────────────────────┘
```

**Confirmation gate:** ✅ `python -m agent.runner --dry-run` still works end to end.

---

### Final Track A File Structure

```
agent/
├── __init__.py
├── config.py                        # unchanged
├── runner.py                        # unchanged
│
├── orchestrator/
│   ├── __init__.py                  # exports: ChatOrchestrator, PreparedTurn, PlannerState
│   ├── chat_orchestrator.py         # REWRITTEN — graph owner
│   ├── nodes.py                     # NEW — pure node factory fns
│   ├── routing.py                   # NEW — routing logic
│   └── state.py                     # NEW — canonical PlannerState
│
├── planner/
│   ├── __init__.py                  # LangGraphTaskDecomposer marked deprecated
│   ├── decomposer.py                # SHRUNK — compatibility adapter only
│   ├── fallback.py                  # unchanged
│   ├── plan_parser.py               # unchanged
│   ├── plan_prompt.py               # unchanged
│   ├── plan_types.py                # PlanPackage only; PlannerState re-exported
│   ├── schemas.py                   # unchanged
│   └── validator.py                 # unchanged
│
├── policy/
│   ├── __init__.py                  # unchanged
│   └── dashboard_policy.py          # unchanged
│
├── services/
│   ├── __init__.py                  # unchanged
│   └── browser_agent.py             # unchanged
│
└── tasks/
    ├── __init__.py                  # unchanged
    └── user_tasks.py                # unchanged

tests/
├── test_panel.py                    # unchanged
├── test_agent.py                    # unchanged
├── test_planner.py                  # unchanged (existing 3 tests)
├── test_nodes.py                    # NEW — A-2
├── test_routing.py                  # NEW — A-3
└── test_orchestrator.py             # NEW — A-4
```

---

## Track B — Robustness Hardening

> Track B begins only after Track A Step A-5 confirmation. All modules below attach cleanly to the new structure.

---

### Step B-1 — Custom Exception Hierarchy

**New file:** `agent/exceptions.py`

```python
class PhoenixWrightError(Exception): ...
class ConfigError(PhoenixWrightError): ...
class APIError(PhoenixWrightError):
    def __init__(self, code, message, retry_after=None): ...
class PlanValidationError(PhoenixWrightError): ...
class BrowserTimeoutError(PhoenixWrightError): ...
class StagnationError(PhoenixWrightError): ...
class RetryExhaustedError(PhoenixWrightError): ...
```

Touch points: `browser_agent.py`, `chat_orchestrator.py`, `runner.py` import from here instead of raising bare exceptions.

**Confirmation gate:** ✅ `from agent.exceptions import PhoenixWrightError` works. No behavior change.

---

### Step B-2 — Retry Strategy + Rate Limiting

**New file:** `agent/retry.py`

```python
class RetryStrategy:
    def __init__(self, max_retries=5, base_delay=1, max_delay=60): ...
    def is_transient_error(self, code: int) -> bool: ...
    async def execute_with_retry(self, fn, *args): ...
```

**Integration points:**
- `BrowserAgentService.run_task` → wrapped in retry strategy
- `ChatOrchestrator._get_llm` → LLM calls wrapped
- Config in `agent/config.py`:
  ```python
  RETRY_CONFIG = {"max_retries": 5, "base_delay_seconds": 1, "max_delay_seconds": 60}
  ```

**Tests:** `tests/test_retry.py`
- Backoff delay increases correctly
- Permanent errors not retried
- RetryExhaustedError raised after limit

**Confirmation gate:** ✅ Retry tests pass.

---

### Step B-3 — API Key Validation on Startup

**Modified file:** `agent/services/browser_agent.py`

Add `validate_api_key()` called in `get_agent()` before constructing the Agent. Raises `ConfigError` with clear messages for missing/invalid/quota-exhausted keys.

**Modified file:** `agent/runner.py`

Wrap `main()` startup in validation:
```python
async def main():
    await validate_startup()   # NEW: checks key + model before entering chat loop
    ...
```

**Tests:** unit test for each failure case (missing, invalid, quota).

**Confirmation gate:** ✅ Clear error messages on bad credentials before any browser opens.

---

### Step B-4 — Structured Error Handling in Chat Loop

**Modified file:** `agent/runner.py`

Replace bare `except Exception: traceback.print_exc()` with structured handler:

```python
except QuotaExhaustedError as e:
    print(f"\n❌ API quota exceeded. Retry after {e.retry_after}s\n")
except BrowserTimeoutError as e:
    print(f"\n⏱️  Timeout during [{e.action}] after {e.seconds}s\n")
except PlanValidationError as e:
    print(f"\n🚨 Plan validation failed: {e}\n")
except PhoenixWrightError as e:
    print(f"\n⚠️  Agent error: {e}\n")
except Exception as e:
    logger.error("Unexpected", exc_info=True)
    print(f"\n⚠️  Unexpected: {type(e).__name__}: {str(e)[:100]}\n")
```

**Confirmation gate:** ✅ Each error type prints correct user-facing message.

---

### Step B-5 — Increase Step Limits + Per-Action Timeouts

**Modified file:** `agent/config.py`

```python
MAX_STEPS = 50          # was 20
PLAN_MAX_NODES = 20     # was 15
PLAN_MAX_ATTEMPTS = 3   # was 2

ACTION_TIMEOUTS = {
    "navigate": 15,
    "search_user": 10,
    "fill_create_user_form": 8,
    "submit_create_form": 10,
    "set_license": 8,
    "set_password": 8,
    "submit_user_update": 10,
    "verify_outcome": 20,
}
```

**Modified file:** `agent/services/browser_agent.py` — pass timeouts to Agent constructor.

**Confirmation gate:** ✅ Config values read correctly. Agent instantiates with new limits.

---

### Step B-6 — Improve Planner Prompts

**Modified file:** `agent/planner/plan_prompt.py`

Add complexity guidance and pattern examples to the prompt (detailed in `IMPLEMENTATION_PLAN.md` §2.2).

This is a pure prompt engineering change — no structural impact.

**Confirmation gate:** ✅ Prompt output reviewed manually for multi-step request.

---

### Step B-7 — Enhanced Plan Validation (Cycle Detection + Complexity Scoring)

**Modified file:** `agent/planner/schemas.py` — add `complexity_score` property and `has_cycles()` to `TaskGraph`.

**Modified file:** `agent/planner/validator.py` — add cycle detection, orphan node detection, complexity logging.

**Tests:** `tests/test_validator.py` (new)
- Cyclic plan → ValidationError
- Orphaned node → ValidationError
- 6-node plan → "complex"

**Confirmation gate:** ✅ Validation tests pass.

---

### Step B-8 — State Checkpointing

**New file:** `agent/state_manager.py` — `ExecutionState` class with `save()`, `load()`, `mark_complete()`, `mark_error()`.

**Integration:** `ChatOrchestrator.prepare_turn` creates checkpoint at start. `BrowserAgentService.run_task` saves state after execution.

**Tests:** checkpoint → crash simulation → resume → verify correct step skipped.

**Confirmation gate:** ✅ Resume behavior verified.

---

### Step B-9 — Structured Logging + Metrics

**New files:**
- `agent/logging_config.py` — `StructuredLogger` with JSON file handler
- `agent/metrics.py` — `MetricsCollector`, `TaskMetrics`, `generate_report()`

**Integration:** Logging added to `decomposer.py` (plan generated), `browser_agent.py` (action timing), `runner.py` (per-session).

**New CLI commands in `runner.py`:**
- `/stats` — session success rates
- `/performance` — last 5 action timings
- `/quota-status` — estimated remaining quota
- `/explain-error` — structured last-error explanation

**Confirmation gate:** ✅ `/stats` outputs valid report after 2+ queries.

---

### Step B-10 — Test Suite Completion

**New test files:**
- `tests/test_error_handling.py` — retry, backoff, exception hierarchy
- `tests/test_complex_workflows.py` — multi-step plan integration
- `tests/test_load.py` — quota simulation + backoff timing
- `tests/test_e2e.py` — full panel + agent round-trip (requires live panel)

**Coverage target:** 70%+ across `agent/` module.

**Confirmation gate:** ✅ All tests pass. Coverage report generated.

---

## Full Final File Structure (Post Both Tracks)

```
phoenix-wright/
├── agent/
│   ├── __init__.py
│   ├── config.py                    # B-5: MAX_STEPS=50, ACTION_TIMEOUTS, RETRY_CONFIG
│   ├── exceptions.py                # B-1: NEW — full exception hierarchy
│   ├── metrics.py                   # B-9: NEW — MetricsCollector
│   ├── logging_config.py            # B-9: NEW — StructuredLogger
│   ├── retry.py                     # B-2: NEW — RetryStrategy
│   ├── runner.py                    # B-3,B-4,B-9: startup validation, structured errors, /stats
│   ├── state_manager.py             # B-8: NEW — ExecutionState checkpointing
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── chat_orchestrator.py     # A-4: REWRITTEN — graph owner
│   │   ├── nodes.py                 # A-2: NEW — pure node factories
│   │   ├── routing.py               # A-3: NEW — routing logic
│   │   └── state.py                 # A-1: NEW — canonical PlannerState
│   │
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── decomposer.py            # A-4: compat adapter (deprecated)
│   │   ├── fallback.py
│   │   ├── plan_parser.py
│   │   ├── plan_prompt.py           # B-6: enhanced with examples
│   │   ├── plan_types.py            # PlanPackage only
│   │   ├── schemas.py               # B-7: complexity_score, has_cycles
│   │   └── validator.py             # B-7: cycle detection, orphan check
│   │
│   ├── policy/
│   │   ├── __init__.py
│   │   └── dashboard_policy.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── browser_agent.py         # B-2,B-3,B-5: retry, validation, timeouts
│   │
│   └── tasks/
│       ├── __init__.py
│       └── user_tasks.py
│
├── panel/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── controllers/user.py
│   ├── models/user.py
│   ├── routes/user.py
│   ├── schemas/user.py
│   ├── static/css/style.css
│   └── templates/
│       ├── base.html
│       ├── users.html
│       ├── create.html
│       └── detail.html
│
├── tests/
│   ├── test_panel.py
│   ├── test_agent.py
│   ├── test_planner.py              # existing — unchanged
│   ├── test_nodes.py                # A-2: NEW
│   ├── test_routing.py              # A-3: NEW
│   ├── test_orchestrator.py         # A-4: NEW
│   ├── test_retry.py                # B-2: NEW
│   ├── test_validator.py            # B-7: NEW
│   ├── test_error_handling.py       # B-10: NEW
│   ├── test_complex_workflows.py    # B-10: NEW
│   ├── test_load.py                 # B-10: NEW
│   └── test_e2e.py                  # B-10: NEW
│
├── .env.example
├── .gitignore
├── LICENSE
├── Plan.md
├── IMPLEMENTATION_PLAN.md
├── PHOENIX_UPGRADE_PLAN.md          # This document
├── README.md
└── requirements.txt
```

---

## Execution Sequence — Confirmation Gates

```
A-1 State → [✅ confirm] →
A-2 Nodes → [✅ confirm] →
A-3 Routing → [✅ confirm] →
A-4 Orchestrator owns graph → [✅ confirm] →
A-5 Cleanup + README → [✅ confirm] →

B-1 Exceptions → [✅ confirm] →
B-2 Retry → [✅ confirm] →
B-3 Startup validation → [✅ confirm] →
B-4 Structured errors → [✅ confirm] →
B-5 Step limits + timeouts → [✅ confirm] →
B-6 Prompt improvements → [✅ confirm] →
B-7 Validator hardening → [✅ confirm] →
B-8 Checkpointing → [✅ confirm] →
B-9 Logging + metrics → [✅ confirm] →
B-10 Full test suite → [✅ confirm → DONE]
```

---

## Success Metrics

| Metric | Before | After Track A | After Track B |
|---|---|---|---|
| Orchestrator owns graph | ❌ | ✅ | ✅ |
| Node fns independently testable | ❌ | ✅ | ✅ |
| Simple task success (1-2 steps) | 85-95% | 85-95% | 95%+ |
| Medium task success (3-5 steps) | 60-75% | 60-75% | 85%+ |
| Complex task success (6-10 steps) | 40-50% | 40-50% | 75%+ |
| Quota error recovery | 0% | 0% | 100% |
| Max steps before timeout | 20 | 20 | 50 |
| Test coverage | <10% | ~35% | 70%+ |
| Observability | None | None | Full |
| Error message clarity | 10% | 10% | 95%+ |