from __future__ import annotations

import os
from typing import List, Optional, Tuple

from agent.config import PLAN_MAX_ATTEMPTS, PLANNER_MODEL
from agent.planner.fallback import minimal_fallback_graph
from agent.planner.plan_parser import graph_from_payload, message_to_text, parse_payload
from agent.planner.plan_prompt import build_planner_prompt
from agent.planner.plan_types import PlanPackage, PlannerState
from agent.planner.schemas import TaskGraph
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


class TaskDecomposer:
    """Dynamic task planner with strict validation and minimal fallback."""

    def __init__(
        self,
        policy: DashboardPolicy | None = None,
        planner_model: str | None = None,
        max_attempts: int = PLAN_MAX_ATTEMPTS,
        use_langgraph: bool = True,
    ) -> None:
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)
        self.planner_model = planner_model or PLANNER_MODEL
        self.max_attempts = max_attempts
        self.use_langgraph = use_langgraph

    def build_plan(self, user_request: str, chat_history: List[Tuple[str, str]] | None = None) -> PlanPackage:
        request = self.policy.sanitize_user_request(user_request)
        history = chat_history or []

        graph = self._build_plan_with_langgraph(request, history) if self.use_langgraph else None
        if graph is None:
            graph = minimal_fallback_graph(request)

        self.validator.validate(graph)
        prompt = self._compile_prompt(graph, history)
        return PlanPackage(graph=graph, compiled_prompt=prompt)

    def _build_plan_with_langgraph(self, request: str, history: List[Tuple[str, str]]) -> Optional[TaskGraph]:
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None

        llm = self._get_llm()
        if llm is None:
            return None

        def draft_plan(state: PlannerState) -> PlannerState:
            prompt = build_planner_prompt(
                request=state["request"],
                history=state.get("history", []),
                policy=self.policy,
                prior_error=state.get("error", ""),
            )
            raw = message_to_text(llm.invoke(prompt))
            return {"raw_plan": raw, "attempts": state.get("attempts", 0) + 1, "error": ""}

        def validate_plan(state: PlannerState) -> PlannerState:
            try:
                payload = parse_payload(state.get("raw_plan", ""))
                graph_obj = graph_from_payload(payload, user_request=state["request"])
                self.validator.validate(graph_obj)
                return {"payload": payload, "graph_obj": graph_obj, "error": ""}
            except Exception as exc:
                return {"error": str(exc)}

        def route(state: PlannerState) -> str:
            if state.get("error") and state.get("attempts", 0) < self.max_attempts:
                return "retry"
            return "done"

        workflow = StateGraph(PlannerState)
        workflow.add_node("draft_plan", draft_plan)
        workflow.add_node("validate_plan", validate_plan)
        workflow.add_edge(START, "draft_plan")
        workflow.add_edge("draft_plan", "validate_plan")
        workflow.add_conditional_edges("validate_plan", route, {"retry": "draft_plan", "done": END})

        result = workflow.compile().invoke({"request": request, "history": history, "attempts": 0})
        return result.get("graph_obj")

    def _get_llm(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except Exception:
            return None

        return ChatGoogleGenerativeAI(model=self.planner_model, google_api_key=api_key, temperature=0)

    def _compile_prompt(self, graph: TaskGraph, chat_history: List[Tuple[str, str]]) -> str:
        history_lines: List[str] = []
        for idx, (user_turn, agent_turn) in enumerate(chat_history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {user_turn}")
            history_lines.append(f"Turn {idx} agent: {agent_turn}")

        sections = [
            "You are PhoenixWright admin automation agent.",
            f"Hard boundary: Operate ONLY inside {self.policy.allowed_origin}.",
            self.policy.allowed_paths_description(),
            "If navigation drifts to another domain, immediately return to the dashboard and continue.",
            "",
            f"User intent: {graph.intent}",
            f"Original request: {graph.user_request}",
            "",
            "Execution plan (follow in order, respecting dependencies):",
            *graph.to_step_lines(),
        ]

        if graph.notes:
            sections.extend(["", "Plan notes:", *[f"- {note}" for note in graph.notes]])

        if history_lines:
            sections.extend(["", "Recent conversation context:", *history_lines])

        sections.extend(
            [
                "",
                "Completion requirements:",
                "1. Provide a concise outcome summary.",
                "2. Include key fields changed (name, email, license, password if generated).",
                "3. Mention any failure point with exact step id.",
            ]
        )

        return "\n".join(sections)
