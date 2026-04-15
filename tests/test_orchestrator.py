from agent.orchestrator.chat_orchestrator import ChatOrchestrator, PreparedTurn
from agent.planner.decomposer import PlannerAdapter


def test_prepare_turn_returns_prepared_turn():
    orchestrator = ChatOrchestrator()

    prepared = orchestrator.prepare_turn("List all users", [])

    assert isinstance(prepared, PreparedTurn)
    assert prepared.prompt
    assert prepared.package.graph.nodes


def test_orchestrator_falls_back_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(ChatOrchestrator, "_compile_workflow", lambda self: None)
    orchestrator = ChatOrchestrator()

    prepared = orchestrator.prepare_turn("Reset password", [])

    assert prepared.package.graph.intent == "generic_query"
    assert "Hard boundary" in prepared.prompt


def test_graph_compiled_once_at_init(monkeypatch):
    calls = {"count": 0}

    def _fake_compile_workflow(self):
        calls["count"] += 1
        return None

    monkeypatch.setattr(ChatOrchestrator, "_compile_workflow", _fake_compile_workflow)
    orchestrator = ChatOrchestrator()

    assert calls["count"] == 1
    orchestrator.prepare_turn("List users", [])
    assert calls["count"] == 1


import pytest

@pytest.mark.skip(reason="PlannerAdapter is deprecated")
def test_prepare_turn_output_parity_with_adapter():
    orchestrator = ChatOrchestrator()
    adapter = PlannerAdapter(use_langgraph=False)

    prepared = orchestrator.prepare_turn("List users", [])
    from_adapter = adapter.build_plan("List users", [])

    assert prepared.package.graph.intent == from_adapter.graph.intent
    assert prepared.prompt == from_adapter.compiled_prompt

