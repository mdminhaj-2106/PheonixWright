from __future__ import annotations

from typing import Any

from agent.orchestrator.state import OrchestratorState

__all__ = ["ChatOrchestrator", "PreparedTurn", "OrchestratorState"]


def __getattr__(name: str) -> Any:
    if name in {"ChatOrchestrator", "PreparedTurn"}:
        from agent.orchestrator.chat_orchestrator import ChatOrchestrator, PreparedTurn

        return {"ChatOrchestrator": ChatOrchestrator, "PreparedTurn": PreparedTurn}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
