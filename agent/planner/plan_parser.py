from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from agent.config import PANEL_URL, PLAN_MAX_NODES
from agent.planner.schemas import NodeAction, TaskGraph, TaskNode


def message_to_text(response: Any) -> str:
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


def parse_payload(raw: str) -> Dict[str, Any]:
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


def graph_from_payload(payload: Dict[str, Any], user_request: str) -> TaskGraph:
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
        action = normalize_action(raw_node.get("action"))

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

    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    notes = [str(note) for note in notes]

    return TaskGraph(intent=intent, user_request=user_request, nodes=anchor_nodes(nodes), notes=notes)


def normalize_action(raw_action: Any) -> NodeAction:
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


def anchor_nodes(nodes: List[TaskNode]) -> List[TaskNode]:
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

    if nodes[0].action == NodeAction.NAVIGATE:
        nodes[0].params["url"] = PANEL_URL
        return nodes

    anchored = [
        TaskNode(
            id="n1",
            title="Open Phoenix admin dashboard",
            action=NodeAction.NAVIGATE,
            params={"url": PANEL_URL},
            success_criteria="Directory page is visible",
        )
    ]

    for idx, node in enumerate(nodes, start=2):
        anchored.append(
            TaskNode(
                id=f"n{idx}",
                title=node.title,
                action=node.action,
                params=node.params,
                depends_on=node.depends_on or ["n1"],
                success_criteria=node.success_criteria,
            )
        )

    return anchored
