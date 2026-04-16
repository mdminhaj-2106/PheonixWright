from __future__ import annotations

from typing import Any, Callable

from agent.orchestrator.state import OrchestratorState
from agent.planner.plan_parser import graph_from_payload, message_to_text, parse_payload
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


def make_draft_plan_node(llm: Any, policy: DashboardPolicy, prompt_builder: Callable[..., str]) -> Callable[[OrchestratorState], dict[str, Any]]:
    def draft_plan(state: OrchestratorState) -> dict[str, Any]:
        prompt = prompt_builder(
            request=state["request"],
            history=state.get("history", []),
            policy=policy,
            prior_error=state.get("error", ""),
        )
        raw = message_to_text(llm.invoke(prompt))
        return {
            "raw_plan": raw,
            "attempts": state.get("attempts", 0) + 1,
            "error": "",
        }

    return draft_plan


def make_validate_plan_node(validator: TaskGraphValidator) -> Callable[[OrchestratorState], dict[str, Any]]:
    def validate_plan(state: OrchestratorState) -> dict[str, Any]:
        try:
            payload = parse_payload(state.get("raw_plan", ""))
            graph_obj = graph_from_payload(payload, user_request=state["request"])
            validator.validate(graph_obj)
            return {
                "payload": payload,
                "graph_obj": graph_obj,
                "error": "",
            }
        except Exception as exc:
            current_count = state.get("validation_error_count", 0)
            return {
                "error": str(exc),
                "validation_error_count": current_count + 1,
            }

    return validate_plan


def make_compile_prompt_node(policy: DashboardPolicy) -> Callable[[OrchestratorState], dict[str, Any]]:
    def compile_prompt(state: OrchestratorState) -> dict[str, Any]:
        graph = state.get("graph_obj")
        history = state.get("history", [])
        if graph is None:
            return {"compiled_prompt": ""}

        history_lines: list[str] = []
        for idx, (user_turn, agent_turn) in enumerate(history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {user_turn}")
            history_lines.append(f"Turn {idx} agent: {agent_turn}")

        total_steps = len(graph.nodes)
        sections: list[str] = [
            "You are PhoenixWright admin automation agent.",
            f"Hard boundary: Operate ONLY inside {policy.allowed_origin}.",
            policy.allowed_paths_description(),
            "If navigation drifts to another domain, immediately return to the dashboard and continue.",
            "",
            f"User intent: {graph.intent}",
            f"Original request: {graph.user_request}",
            "",
            f"MANDATORY EXECUTION CHECKLIST — {total_steps} steps total.",
            f"You MUST execute ALL {total_steps} steps below in order before calling done.",
            "Do NOT call done after completing only part of the plan. Each step is required.",
            "If a step fails, note the failure and continue to the next step — do not stop early.",
            "",
            "Steps (execute in order):",
            *graph.to_step_lines(),
        ]
        if graph.notes:
            sections.extend(["", "Plan notes:", *[f"- {note}" for note in graph.notes]])
        if history_lines:
            sections.extend(["", "Recent conversation context:", *history_lines])
        sections.extend(
            [
                "",
                "Completion requirements (only after ALL steps above are done):",
                "1. Provide a concise outcome summary covering ALL steps.",
                "2. Include key fields changed (name, email, license, password if generated).",
                "3. Mention any failure point with exact step number.",
                "4. Confirm whether retries or fallbacks were triggered.",
            ]
        )
        return {"compiled_prompt": "\n".join(sections)}

    return compile_prompt
