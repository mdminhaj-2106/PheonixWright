from __future__ import annotations

from agent.planner.schemas import NodeAction, TaskGraph
from agent.policy.dashboard_policy import DashboardPolicy


from agent.exceptions import PlanValidationError

class TaskGraphValidationError(PlanValidationError):
    pass


class TaskGraphValidator:
    def __init__(self, policy: DashboardPolicy | None = None) -> None:
        self.policy = policy or DashboardPolicy()

    def validate(self, graph: TaskGraph) -> None:
        if not graph.nodes:
            raise TaskGraphValidationError("Plan graph is empty")

        first = graph.nodes[0]
        if first.action != NodeAction.NAVIGATE:
            raise TaskGraphValidationError("First plan step must be a dashboard navigation step")

        first_url = first.params.get("url", "")
        if not self.policy.is_allowed_url(first_url):
            raise TaskGraphValidationError(f"First step url is outside allowed origin: {first_url}")

        node_ids = {node.id for node in graph.nodes}
        for node in graph.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise TaskGraphValidationError(f"Node {node.id} has unknown dependency {dep}")

            if node.action == NodeAction.NAVIGATE:
                url = node.params.get("url", "")
                if not self.policy.is_allowed_url(url):
                    raise TaskGraphValidationError(f"Disallowed navigation url in node {node.id}: {url}")
