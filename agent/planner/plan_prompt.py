from __future__ import annotations

from typing import List, Tuple

from agent.config import PLAN_MAX_NODES
from agent.planner.schemas import NodeAction
from agent.policy.dashboard_policy import DashboardPolicy


def build_planner_prompt(
    request: str,
    history: List[Tuple[str, str]],
    policy: DashboardPolicy,
    prior_error: str = "",
) -> str:
    history_lines: List[str] = []
    for idx, (user_msg, agent_msg) in enumerate(history[-4:], start=1):
        history_lines.append(f"Turn {idx} user: {user_msg}")
        history_lines.append(f"Turn {idx} agent: {agent_msg}")

    actions = ", ".join(action.value for action in NodeAction)

    sections = [
        "You generate execution plans for PhoenixWright admin dashboard automation.",
        f"Hard boundary: stay on {policy.allowed_origin} only.",
        policy.allowed_paths_description(),
        "Return JSON only. No markdown fences.",
        "Output schema:",
        '{"intent":"string","nodes":[{"id":"n1","title":"string","action":"allowed_action","params":{},"depends_on":[],"success_criteria":"string"}],"notes":[]}',
        f"Allowed actions: {actions}",
        f"Max nodes: {PLAN_MAX_NODES}",
        "First node must navigate to the dashboard base URL.",
        "",
        f"User request: {request}",
    ]

    if history_lines:
        sections.extend(["", "Recent context:", *history_lines])

    if prior_error:
        sections.extend(["", f"Previous attempt failed validation: {prior_error}", "Fix and regenerate."])

    return "\n".join(sections)
