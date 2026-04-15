from __future__ import annotations

from agent.orchestrator.state import OrchestratorState


def plan_route(max_attempts: int):
    def route(state: OrchestratorState) -> str:
        has_error = bool(state.get("error"))
        under_limit = state.get("attempts", 0) < max_attempts
        if has_error and under_limit:
            return "retry"
        return "done"

    return route
