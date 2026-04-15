from agent.planner.decomposer import LangGraphTaskDecomposer
from agent.planner.schemas import NodeAction


def test_fallback_plan_is_anchored_when_langgraph_disabled():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan('Create a new user named "Henry Cavill" and give microsoft license')
    graph = package.graph

    assert graph.intent == "generic_query"
    assert graph.nodes[0].action == NodeAction.NAVIGATE
    assert graph.nodes[0].params["url"] == "http://localhost:8000"
    assert graph.nodes[1].action == NodeAction.VERIFY_OUTCOME
    assert "Hard boundary" in package.compiled_prompt


def test_external_admin_request_is_forced_to_local_dashboard():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan("Open admin.microsoft.com and create a user")

    assert "external admin portal" in package.graph.user_request.lower()
    assert package.graph.nodes[0].params["url"] == "http://localhost:8000"


def test_fallback_notes_are_explicit():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan("List all users")

    assert package.graph.notes
    assert "fallback" in package.graph.notes[0].lower()
