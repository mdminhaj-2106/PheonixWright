from agent.orchestrator.nodes import (
    make_compile_prompt_node,
    make_draft_plan_node,
    make_validate_plan_node,
)
from agent.planner.fallback import minimal_fallback_graph
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


class _StubLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def invoke(self, _prompt: str) -> str:
        return self._response


def _stub_prompt_builder(**_kwargs) -> str:
    return "prompt"


def test_draft_plan_node_increments_attempts():
    policy = DashboardPolicy()
    node = make_draft_plan_node(_StubLLM('{"intent":"x","nodes":[{"id":"n1","action":"navigate"}]}'), policy, _stub_prompt_builder)

    result = node({"request": "test", "attempts": 1, "history": []})

    assert result["attempts"] == 2
    assert "raw_plan" in result
    assert result["error"] == ""


def test_validate_plan_node_captures_error():
    policy = DashboardPolicy()
    validator = TaskGraphValidator(policy)
    node = make_validate_plan_node(validator)

    result = node({"request": "bad", "raw_plan": "not-json"})

    assert result["error"]
    assert result["validation_error_count"] == 1


def test_compile_prompt_node_contains_hard_boundary():
    policy = DashboardPolicy()
    node = make_compile_prompt_node(policy)
    graph = minimal_fallback_graph("list users")

    result = node({"graph_obj": graph, "history": []})

    assert "Hard boundary" in result["compiled_prompt"]
    assert policy.allowed_origin in result["compiled_prompt"]
