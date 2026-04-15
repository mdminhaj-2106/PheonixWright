from __future__ import annotations

from typing import Any

from agent.planner.schemas import NodeAction, TaskGraph, TaskNode
from agent.planner.validator import TaskGraphValidationError, TaskGraphValidator

__all__ = [
    "PlanPackage",
    "PlannerAdapter",
    "NodeAction",
    "TaskGraph",
    "TaskNode",
    "TaskGraphValidationError",
    "TaskGraphValidator",
]


def __getattr__(name: str) -> Any:
    if name == "PlanPackage":
        from agent.planner.plan_types import PlanPackage

        return PlanPackage
    if name == "PlannerAdapter":
        from agent.planner.decomposer import PlannerAdapter

        return PlannerAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
