from agent.planner.decomposer import PlannerAdapter
from agent.planner.schemas import NodeAction


def test_adapter_fallback_plan_is_dashboard_anchored():
    adapter = PlannerAdapter(use_langgraph=False)

    package = adapter.build_plan('Create a new user named "Henry Cavill" and give microsoft license')
    graph = package.graph

    assert graph.intent == "generic_query"
    assert graph.nodes[0].action == NodeAction.NAVIGATE
    assert graph.nodes[0].params["url"] == "http://localhost:8000"
    assert graph.nodes[1].action == NodeAction.VERIFY_OUTCOME
    assert "Hard boundary" in package.compiled_prompt


def test_adapter_forces_external_requests_to_local_dashboard():
    adapter = PlannerAdapter(use_langgraph=False)

    package = adapter.build_plan("Open admin.microsoft.com and create a user")

    assert "external admin portal" in package.graph.user_request.lower()
    assert package.graph.nodes[0].params["url"] == "http://localhost:8000"


def test_adapter_fallback_notes_are_explicit():
    adapter = PlannerAdapter(use_langgraph=False)

    package = adapter.build_plan("List all users")

    assert package.graph.notes
    assert "fallback" in package.graph.notes[0].lower()
