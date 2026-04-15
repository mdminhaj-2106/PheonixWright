from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, TypedDict

from agent.planner.schemas import TaskGraph


@dataclass
class PlanPackage:
    graph: TaskGraph
    compiled_prompt: str


class PlannerState(TypedDict, total=False):
    request: str
    history: List[Tuple[str, str]]
    raw_plan: str
    payload: Dict[str, Any]
    graph_obj: TaskGraph
    error: str
    attempts: int
