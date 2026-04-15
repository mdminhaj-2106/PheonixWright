from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class NodeAction(str, Enum):
    NAVIGATE = "navigate"
    SEARCH_USER = "search_user"
    OPEN_CREATE_USER = "open_create_user"
    FILL_CREATE_USER_FORM = "fill_create_user_form"
    SUBMIT_CREATE_FORM = "submit_create_form"
    OPEN_USER_DETAIL = "open_user_detail"
    SET_LICENSE = "set_license"
    SET_PASSWORD = "set_password"
    SUBMIT_USER_UPDATE = "submit_user_update"
    VERIFY_OUTCOME = "verify_outcome"


@dataclass
class TaskNode:
    id: str
    title: str
    action: NodeAction
    params: Dict[str, str] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    success_criteria: str = ""


@dataclass
class TaskGraph:
    intent: str
    user_request: str
    nodes: List[TaskNode]
    notes: List[str] = field(default_factory=list)

    def to_step_lines(self) -> List[str]:
        lines: List[str] = []
        for idx, node in enumerate(self.nodes, start=1):
            param_view = ", ".join(f"{k}={v}" for k, v in node.params.items())
            if param_view:
                lines.append(f"{idx}. [{node.action.value}] {node.title} ({param_view})")
            else:
                lines.append(f"{idx}. [{node.action.value}] {node.title}")
        return lines
