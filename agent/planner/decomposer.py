from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from agent.config import PANEL_URL, PLAN_MAX_ATTEMPTS, PLAN_MAX_NODES, PLANNER_MODEL
from agent.planner.schemas import NodeAction, TaskGraph, TaskNode
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


@dataclass
class PlanPackage:
    graph: TaskGraph
    compiled_prompt: str


class _PlannerState(TypedDict, total=False):
    request: str
    history: List[Tuple[str, str]]
    raw_plan: str
    payload: Dict[str, Any]
    graph_obj: TaskGraph
    error: str
    attempts: int


class LangGraphTaskDecomposer:
    """Dynamic planner backed by LangGraph with deterministic fallback."""

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
        sanitized_request = self.policy.sanitize_user_request(user_request)
        history = chat_history or []

        graph = None
        if self.use_langgraph:
            graph = self._build_plan_with_langgraph(sanitized_request, history)

        if graph is None:
            graph = self._fallback_plan(sanitized_request)

        self.validator.validate(graph)
        compiled_prompt = self._compile_prompt(graph, history)
        return PlanPackage(graph=graph, compiled_prompt=compiled_prompt)

    def _build_plan_with_langgraph(self, request: str, history: List[Tuple[str, str]]) -> Optional[TaskGraph]:
        try:
            from langgraph.graph import END, START, StateGraph
        except Exception:
            return None

        llm = self._get_llm()
        if llm is None:
            return None

        def draft_plan(state: _PlannerState) -> _PlannerState:
            attempts = state.get("attempts", 0)
            prior_error = state.get("error", "")
            prompt = self._planner_prompt(request=state["request"], history=state.get("history", []), prior_error=prior_error)
            response = llm.invoke(prompt)
            raw = self._message_to_text(response)
            return {"raw_plan": raw, "attempts": attempts + 1, "error": ""}

        def validate_plan(state: _PlannerState) -> _PlannerState:
            raw = state.get("raw_plan", "")
            try:
                payload = self._parse_payload(raw)
                graph_obj = self._graph_from_payload(payload, user_request=state["request"])
                self.validator.validate(graph_obj)
                return {"payload": payload, "graph_obj": graph_obj, "error": ""}
            except Exception as exc:
                return {"error": str(exc)}

        def route_after_validate(state: _PlannerState) -> str:
            if state.get("error") and state.get("attempts", 0) < self.max_attempts:
                return "retry"
            return "done"

        graph_builder = StateGraph(_PlannerState)
        graph_builder.add_node("draft_plan", draft_plan)
        graph_builder.add_node("validate_plan", validate_plan)
        graph_builder.add_edge(START, "draft_plan")
        graph_builder.add_edge("draft_plan", "validate_plan")
        graph_builder.add_conditional_edges(
            "validate_plan",
            route_after_validate,
            {"retry": "draft_plan", "done": END},
        )

        workflow = graph_builder.compile()
        result = workflow.invoke({"request": request, "history": history, "attempts": 0})
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

    def _planner_prompt(self, request: str, history: List[Tuple[str, str]], prior_error: str = "") -> str:
        history_lines: List[str] = []
        for idx, (u, a) in enumerate(history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {u}")
            history_lines.append(f"Turn {idx} agent: {a}")

        actions = ", ".join(action.value for action in NodeAction)

        sections = [
            "You generate execution plans for PhoenixWright admin dashboard automation.",
            f"Hard boundary: stay on {self.policy.allowed_origin} only.",
            self.policy.allowed_paths_description(),
            "Return JSON only. Do not include markdown fences.",
            "Output schema:",
            '{"intent": "string", "nodes": [{"id": "n1", "title": "string", "action": "one_of_allowed", "params": {"k":"v"}, "depends_on": ["n0"], "success_criteria": "string"}], "notes": ["string"]}',
            f"Allowed actions: {actions}",
            f"Max nodes: {PLAN_MAX_NODES}",
            "First node must navigate to the dashboard base URL.",
            "Use concise dependency edges and include explicit success criteria.",
            "",
            f"User request: {request}",
        ]

        if history_lines:
            sections.extend(["", "Recent context:", *history_lines])

        if prior_error:
            sections.extend(["", f"Previous attempt failed validation: {prior_error}", "Fix and regenerate."])

        return "\n".join(sections)

    def _message_to_text(self, response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return "\n".join(parts).strip()
        return str(content).strip()

    def _parse_payload(self, raw: str) -> Dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]

        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Planner output is not a JSON object")
        return payload

    def _graph_from_payload(self, payload: Dict[str, Any], user_request: str) -> TaskGraph:
        intent = str(payload.get("intent") or "dynamic_query")
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise ValueError("Planner returned no nodes")

        nodes: List[TaskNode] = []
        for idx, raw_node in enumerate(raw_nodes[:PLAN_MAX_NODES], start=1):
            if not isinstance(raw_node, dict):
                raise ValueError(f"Invalid node at index {idx}")

            node_id = str(raw_node.get("id") or f"n{idx}")
            title = str(raw_node.get("title") or f"Step {idx}")
            action = self._normalize_action(raw_node.get("action"))
            params = raw_node.get("params") if isinstance(raw_node.get("params"), dict) else {}
            params = {str(k): str(v) for k, v in params.items()}

            depends_on = raw_node.get("depends_on") if isinstance(raw_node.get("depends_on"), list) else []
            depends_on = [str(dep) for dep in depends_on]

            success_criteria = str(raw_node.get("success_criteria") or "Step completed successfully")

            nodes.append(
                TaskNode(
                    id=node_id,
                    title=title,
                    action=action,
                    params=params,
                    depends_on=depends_on,
                    success_criteria=success_criteria,
                )
            )

        nodes = self._anchor_nodes(nodes)

        notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
        notes = [str(note) for note in notes]

        return TaskGraph(intent=intent, user_request=user_request, nodes=nodes, notes=notes)

    def _normalize_action(self, raw_action: Any) -> NodeAction:
        if raw_action is None:
            return NodeAction.VERIFY_OUTCOME

        token = str(raw_action).strip().lower().replace("-", "_").replace(" ", "_")
        for action in NodeAction:
            if token == action.value:
                return action

        aliases = {
            "open_dashboard": NodeAction.NAVIGATE,
            "go_to_dashboard": NodeAction.NAVIGATE,
            "search": NodeAction.SEARCH_USER,
            "create_user": NodeAction.FILL_CREATE_USER_FORM,
            "open_create": NodeAction.OPEN_CREATE_USER,
            "submit": NodeAction.SUBMIT_USER_UPDATE,
            "verify": NodeAction.VERIFY_OUTCOME,
        }
        return aliases.get(token, NodeAction.VERIFY_OUTCOME)

    def _anchor_nodes(self, nodes: List[TaskNode]) -> List[TaskNode]:
        if not nodes:
            return [
                TaskNode(
                    id="n1",
                    title="Open Phoenix admin dashboard",
                    action=NodeAction.NAVIGATE,
                    params={"url": PANEL_URL},
                    success_criteria="Directory page is visible",
                )
            ]

        first = nodes[0]
        if first.action == NodeAction.NAVIGATE:
            first.params["url"] = PANEL_URL
            return nodes

        anchored_nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            )
        ]

        for idx, node in enumerate(nodes, start=2):
            new_id = f"n{idx}"
            deps = node.depends_on or ["n1"]
            anchored_nodes.append(
                TaskNode(
                    id=new_id,
                    title=node.title,
                    action=node.action,
                    params=node.params,
                    depends_on=deps,
                    success_criteria=node.success_criteria,
                )
            )

        return anchored_nodes

    def _fallback_plan(self, request: str) -> TaskGraph:
        lowered = request.lower()
        nodes: List[TaskNode] = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            )
        ]

        if "create" in lowered or "provision" in lowered or "new user" in lowered or "add user" in lowered:
            wants_password = "password" in lowered
            nodes.extend(
                [
                    TaskNode(
                        id="n2",
                        title="Open provisioning form",
                        action=NodeAction.OPEN_CREATE_USER,
                        depends_on=["n1"],
                        success_criteria="Provision form is visible",
                    ),
                    TaskNode(
                        id="n3",
                        title="Fill create form from request",
                        action=NodeAction.FILL_CREATE_USER_FORM,
                        depends_on=["n2"],
                        success_criteria="Name/email/license fields are populated",
                    ),
                    TaskNode(
                        id="n4",
                        title="Submit create form",
                        action=NodeAction.SUBMIT_CREATE_FORM,
                        depends_on=["n3"],
                        success_criteria="New user is created",
                    ),
                ]
            )
            if wants_password:
                nodes.extend(
                    [
                        TaskNode(
                            id="n5",
                            title="Open created user profile",
                            action=NodeAction.OPEN_USER_DETAIL,
                            depends_on=["n4"],
                            success_criteria="User detail page is visible",
                        ),
                        TaskNode(
                            id="n6",
                            title="Set generated password",
                            action=NodeAction.SET_PASSWORD,
                            params={"mode": "random_strong"},
                            depends_on=["n5"],
                            success_criteria="Credential field is populated",
                        ),
                        TaskNode(
                            id="n7",
                            title="Commit user profile changes",
                            action=NodeAction.SUBMIT_USER_UPDATE,
                            depends_on=["n6"],
                            success_criteria="Profile changes are saved",
                        ),
                    ]
                )
            intent = "create_user"
        elif "password" in lowered and any(token in lowered for token in ["reset", "change", "credential"]):
            nodes.extend(
                [
                    TaskNode(
                        id="n2",
                        title="Search target user in directory",
                        action=NodeAction.SEARCH_USER,
                        depends_on=["n1"],
                        success_criteria="Target user row is visible",
                    ),
                    TaskNode(
                        id="n3",
                        title="Open target user profile",
                        action=NodeAction.OPEN_USER_DETAIL,
                        depends_on=["n2"],
                        success_criteria="User detail page is visible",
                    ),
                    TaskNode(
                        id="n4",
                        title="Set credential reset value",
                        action=NodeAction.SET_PASSWORD,
                        params={"mode": "random_strong"},
                        depends_on=["n3"],
                        success_criteria="Credential field is populated",
                    ),
                    TaskNode(
                        id="n5",
                        title="Commit changes",
                        action=NodeAction.SUBMIT_USER_UPDATE,
                        depends_on=["n4"],
                        success_criteria="Form submit completes successfully",
                    ),
                ]
            )
            intent = "password_reset"
        else:
            nodes.append(
                TaskNode(
                    id="n2",
                    title="Resolve request on dashboard and verify",
                    action=NodeAction.VERIFY_OUTCOME,
                    depends_on=["n1"],
                    params={"request": request},
                    success_criteria="Final response addresses request",
                )
            )
            intent = "generic_query"

        return TaskGraph(
            intent=intent,
            user_request=request,
            nodes=nodes,
            notes=["Fallback planner used due to unavailable/invalid LangGraph plan."],
        )

    def _compile_prompt(self, graph: TaskGraph, chat_history: List[Tuple[str, str]]) -> str:
        history_lines: List[str] = []
        for idx, (user_turn, agent_turn) in enumerate(chat_history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {user_turn}")
            history_lines.append(f"Turn {idx} agent: {agent_turn}")

        step_lines = graph.to_step_lines()

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
            *step_lines,
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


# Backwards-compatible alias for existing imports.
RuleBasedTaskDecomposer = LangGraphTaskDecomposer
