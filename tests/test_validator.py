import pytest
from agent.planner.schemas import TaskGraph, TaskNode, NodeAction
from agent.planner.validator import TaskGraphValidator, TaskGraphValidationError

def test_cyclic_plan_raises():
    nodes = [
        TaskNode(id="n1", title="nav", action=NodeAction.NAVIGATE, params={"url":"http://localhost:8000"}, depends_on=["n2"]),
        TaskNode(id="n2", title="search", action=NodeAction.SEARCH_USER, depends_on=["n1"])
    ]
    graph = TaskGraph(intent="test", user_request="test", nodes=nodes)
    validator = TaskGraphValidator()
    with pytest.raises(TaskGraphValidationError, match="dependency cycle"):
        validator.validate(graph)

def test_orphaned_dependency_raises():
    nodes = [
        TaskNode(id="n1", title="nav", action=NodeAction.NAVIGATE, params={"url":"http://localhost:8000"}, depends_on=["unknown_node"])
    ]
    graph = TaskGraph(intent="test", user_request="test", nodes=nodes)
    validator = TaskGraphValidator()
    with pytest.raises(TaskGraphValidationError, match="unknown dependency unknown_node"):
        validator.validate(graph)

def test_complexity_score_correct():
    def make_nodes(n):
        return [TaskNode(id=f"n{i}", title="nav", action=NodeAction.NAVIGATE, params={"url":"http://localhost:8000"} if i==0 else {}) for i in range(n)]
        
    assert TaskGraph(intent="t", user_request="t", nodes=make_nodes(2)).complexity_score == "simple"
    assert TaskGraph(intent="t", user_request="t", nodes=make_nodes(5)).complexity_score == "medium"
    assert TaskGraph(intent="t", user_request="t", nodes=make_nodes(6)).complexity_score == "complex"
