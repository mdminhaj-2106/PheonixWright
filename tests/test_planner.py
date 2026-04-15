from agent.planner.decomposer import RuleBasedTaskDecomposer
from agent.planner.schemas import NodeAction


def test_create_user_plan_is_anchored_and_structured():
    decomposer = RuleBasedTaskDecomposer()

    package = decomposer.build_plan('Create a new user named "Henry Cavill" and give microsoft license')
    graph = package.graph

    assert graph.intent == "create_user_and_assign_license"
    assert graph.nodes[0].action == NodeAction.NAVIGATE
    assert graph.nodes[0].params["url"] == "http://localhost:8000"
    assert any(node.action == NodeAction.FILL_CREATE_USER_FORM for node in graph.nodes)
    assert any(node.action == NodeAction.SET_LICENSE for node in graph.nodes)
    assert "Hard boundary" in package.compiled_prompt


def test_external_admin_request_is_sanitized_to_local_dashboard():
    decomposer = RuleBasedTaskDecomposer()

    package = decomposer.build_plan("Open admin.microsoft.com and create a user")

    assert "external admin portal" in package.graph.user_request.lower()
    assert "http://localhost:8000" in package.compiled_prompt


def test_password_reset_intent_decomposes_into_micro_steps():
    decomposer = RuleBasedTaskDecomposer()

    package = decomposer.build_plan('Reset password for "Alice Johnson"')
    actions = [node.action for node in package.graph.nodes]

    assert package.graph.intent == "password_reset"
    assert NodeAction.SEARCH_USER in actions
    assert NodeAction.SET_PASSWORD in actions
    assert NodeAction.SUBMIT_USER_UPDATE in actions


def test_create_user_without_license_maps_to_create_user_intent():
    decomposer = RuleBasedTaskDecomposer()

    package = decomposer.build_plan('Create a new user named "Jane Doe" with random password')
    actions = [node.action for node in package.graph.nodes]

    assert package.graph.intent == "create_user"
    assert NodeAction.OPEN_CREATE_USER in actions
    assert NodeAction.FILL_CREATE_USER_FORM in actions
    assert NodeAction.SET_PASSWORD in actions
