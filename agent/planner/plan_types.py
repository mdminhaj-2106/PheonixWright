from __future__ import annotations

from dataclasses import dataclass

from agent.orchestrator.state import PlannerState
from agent.planner.schemas import TaskGraph


@dataclass
class PlanPackage:
    graph: TaskGraph
    compiled_prompt: str

__all__ = ["PlanPackage", "PlannerState"]
