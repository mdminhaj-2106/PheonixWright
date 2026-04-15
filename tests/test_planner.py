from agent.planner.decomposer import LangGraphTaskDecomposer
from agent.planner.schemas import NodeAction


def test_dynamic_planner_fallback_stays_anchored_when_langgraph_disabled():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan('Create a new user named "Henry Cavill" and give microsoft license')
    graph = package.graph

    assert graph.nodes[0].action == NodeAction.NAVIGATE
    assert graph.nodes[0].params["url"] == "http://localhost:8000"
    assert "Hard boundary" in package.compiled_prompt


def test_dynamic_planner_password_flow_fallback_contains_micro_steps():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan('Reset password for "Alice Johnson"')
    actions = [node.action for node in package.graph.nodes]

    assert package.graph.intent == "password_reset"
    assert NodeAction.SEARCH_USER in actions
    assert NodeAction.SET_PASSWORD in actions
    assert NodeAction.SUBMIT_USER_UPDATE in actions


def test_dynamic_planner_create_user_with_password_keeps_create_flow():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan('Create a new user named "Jane Doe" with random password')
    actions = [node.action for node in package.graph.nodes]

    assert package.graph.intent == "create_user"
    assert NodeAction.OPEN_CREATE_USER in actions
    assert NodeAction.SUBMIT_CREATE_FORM in actions
    assert NodeAction.SET_PASSWORD in actions


def test_external_admin_request_is_forced_to_local_dashboard():
    decomposer = LangGraphTaskDecomposer(use_langgraph=False)

    package = decomposer.build_plan("Open admin.microsoft.com and create a user")

    assert "external admin portal" in package.graph.user_request.lower()
    assert "http://localhost:8000" in package.compiled_prompt
