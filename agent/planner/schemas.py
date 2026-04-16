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
    DYNAMIC_ROUTINE = "dynamic_routine"
    DELETE_USER = "delete_user"
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
            if node.action == NodeAction.DYNAMIC_ROUTINE:
                instruction = node.params.get("instruction", "")
                lines.append(f"{idx}. [dynamic_routine] {node.title}")
                lines.append(f"   INSTRUCTION: {instruction}")
                if node.success_criteria:
                    lines.append(f"   SUCCESS: {node.success_criteria}")
            else:
                param_view = ", ".join(f"{k}={v}" for k, v in node.params.items())
                if param_view:
                    lines.append(f"{idx}. [{node.action.value}] {node.title} ({param_view})")
                else:
                    lines.append(f"{idx}. [{node.action.value}] {node.title}")
        return lines

    @property
    def complexity_score(self) -> str:
        n = len(self.nodes)
        if n <= 2:  return "simple"
        if n <= 5:  return "medium"
        return "complex"

    def has_cycles(self) -> bool:
        """Topological sort (Kahn's algorithm) — returns True if a cycle exists."""
        in_degree = {node.id: 0 for node in self.nodes}
        adj = {node.id: [] for node in self.nodes}
        
        for node in self.nodes:
            for dep in node.depends_on:
                if dep in adj:
                    adj[dep].append(node.id)
                    if node.id in in_degree:
                        in_degree[node.id] += 1
                        
        queue = [nid for nid, degree in in_degree.items() if degree == 0]
        visited_count = 0
        
        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj.get(curr, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
                        
        return visited_count != len(self.nodes)
