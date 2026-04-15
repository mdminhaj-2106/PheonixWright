from agent.orchestrator.routing import plan_route


def test_route_retries_when_error_and_under_limit():
    route = plan_route(3)
    assert route({"error": "boom", "attempts": 1}) == "retry"


def test_route_done_when_no_error():
    route = plan_route(3)
    assert route({"error": "", "attempts": 1}) == "done"


def test_route_done_when_limit_reached():
    route = plan_route(3)
    assert route({"error": "boom", "attempts": 3}) == "done"
