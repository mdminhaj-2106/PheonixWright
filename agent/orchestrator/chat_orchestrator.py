from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

from agent.config import PLAN_MAX_ATTEMPTS, PLANNER_MODEL
from agent.orchestrator.nodes import (
    make_compile_prompt_node,
    make_draft_plan_node,
    make_validate_plan_node,
)
from agent.orchestrator.routing import plan_route
from agent.orchestrator.state import OrchestratorState
from agent.planner.fallback import minimal_fallback_graph
from agent.planner.plan_types import PlanPackage
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


@dataclass
class PreparedTurn:
    package: PlanPackage
    prompt: str


class ChatOrchestrator:
    def __init__(
        self,
        policy: DashboardPolicy | None = None,
        planner_model: str | None = None,
        max_attempts: int = PLAN_MAX_ATTEMPTS,
    ) -> None:
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)
        self.planner_model = planner_model or PLANNER_MODEL
        self.max_attempts = max_attempts
        self._workflow_app = self._compile_workflow()

    def _build_planner_llm(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except Exception:
            return None
        return ChatGoogleGenerativeAI(model=self.planner_model, google_api_key=api_key, temperature=0)

    def _compile_workflow(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None

        llm = self._build_planner_llm()
        if llm is None:
            return None

        from agent.planner.plan_prompt import build_planner_prompt

        draft_node = make_draft_plan_node(llm, self.policy, build_planner_prompt)
        validate_node = make_validate_plan_node(self.validator)
        compile_node = make_compile_prompt_node(self.policy)
        route = plan_route(self.max_attempts)

        workflow = StateGraph(OrchestratorState)
        workflow.add_node("draft_plan", draft_node)
        workflow.add_node("validate_plan", validate_node)
        workflow.add_node("compile_prompt", compile_node)
        workflow.add_edge(START, "draft_plan")
        workflow.add_edge("draft_plan", "validate_plan")
        workflow.add_conditional_edges("validate_plan", route, {"retry": "draft_plan", "done": "compile_prompt"})
        workflow.add_edge("compile_prompt", END)
        return workflow.compile()

    def prepare_turn(self, user_input: str, history: List[Tuple[str, str]]) -> PreparedTurn:
        request = self.policy.sanitize_user_request(user_input)
        graph_obj = None
        compiled_prompt = ""

        if self._workflow_app is not None:
            result = self._workflow_app.invoke(
                {
                    "request": request,
                    "history": history,
                    "attempts": 0,
                    "fallback_used": False,
                    "validation_error_count": 0,
                }
            )
            graph_obj = result.get("graph_obj")
            compiled_prompt = result.get("compiled_prompt", "")

        if graph_obj is None:
            graph_obj = minimal_fallback_graph(request)
            compile_prompt = make_compile_prompt_node(self.policy)
            compiled_prompt = compile_prompt(
                {"request": request, "history": history, "graph_obj": graph_obj, "fallback_used": True}
            ).get("compiled_prompt", "")

        self.validator.validate(graph_obj)
        package = PlanPackage(graph=graph_obj, compiled_prompt=compiled_prompt)
        return PreparedTurn(package=package, prompt=compiled_prompt)
