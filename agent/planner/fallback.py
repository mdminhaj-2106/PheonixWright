from __future__ import annotations

from agent.config import PANEL_URL
from agent.planner.schemas import NodeAction, TaskGraph, TaskNode


def minimal_fallback_graph(request: str) -> TaskGraph:
    return TaskGraph(
        intent="generic_query",
        user_request=request,
        nodes=[
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Resolve request on dashboard and verify",
                action=NodeAction.VERIFY_OUTCOME,
                params={"request": request},
                depends_on=["n1"],
                success_criteria="Final response addresses request",
            ),
        ],
        notes=["Minimal fallback used because dynamic planner was unavailable or invalid."],
    )
