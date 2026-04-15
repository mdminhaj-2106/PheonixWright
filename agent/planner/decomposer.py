from __future__ import annotations

from typing import List, Tuple

from agent.config import PLAN_MAX_ATTEMPTS, PLANNER_MODEL
from agent.orchestrator.chat_orchestrator import ChatOrchestrator
from agent.orchestrator.nodes import make_compile_prompt_node
from agent.planner.fallback import minimal_fallback_graph
from agent.planner.plan_types import PlanPackage
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


class PlannerAdapter:
    """
    Compatibility adapter for planner imports.
    Primary planning workflow ownership lives in ChatOrchestrator.
    """

    def __init__(
        self,
        policy: DashboardPolicy | None = None,
        planner_model: str | None = None,
        max_attempts: int = PLAN_MAX_ATTEMPTS,
        use_langgraph: bool = True,
    ) -> None:
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)
        self._use_orchestrator_workflow = use_langgraph
        self._orchestrator_adapter = (
            ChatOrchestrator(policy=self.policy, planner_model=planner_model or PLANNER_MODEL, max_attempts=max_attempts)
            if use_langgraph
            else None
        )

    def build_plan(self, user_request: str, chat_history: List[Tuple[str, str]] | None = None) -> PlanPackage:
        history = chat_history or []
        if self._use_orchestrator_workflow and self._orchestrator_adapter is not None:
            return self._orchestrator_adapter.prepare_turn(user_request, history).package

        request = self.policy.sanitize_user_request(user_request)
        graph = minimal_fallback_graph(request)
        self.validator.validate(graph)
        prompt = self._compile_compat_prompt(graph, history)
        return PlanPackage(graph=graph, compiled_prompt=prompt)

    def _compile_compat_prompt(self, graph, chat_history: List[Tuple[str, str]]) -> str:
        compile_prompt = make_compile_prompt_node(self.policy)
        result = compile_prompt({"graph_obj": graph, "history": chat_history, "request": graph.user_request})
        return result.get("compiled_prompt", "")

