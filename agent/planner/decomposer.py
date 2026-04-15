from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from agent.config import PANEL_URL
from agent.planner.schemas import NodeAction, TaskGraph, TaskNode
from agent.planner.validator import TaskGraphValidator
from agent.policy.dashboard_policy import DashboardPolicy


@dataclass
class PlanPackage:
    graph: TaskGraph
    compiled_prompt: str


class RuleBasedTaskDecomposer:
    def __init__(self, policy: DashboardPolicy | None = None) -> None:
        self.policy = policy or DashboardPolicy()
        self.validator = TaskGraphValidator(self.policy)

    def build_plan(self, user_request: str, chat_history: List[Tuple[str, str]] | None = None) -> PlanPackage:
        sanitized_request = self.policy.sanitize_user_request(user_request)
        intent = self._detect_intent(sanitized_request)

        if intent == "create_user_and_assign_license":
            graph = self._plan_create_user_and_assign_license(sanitized_request)
        elif intent == "create_user":
            graph = self._plan_create_user(sanitized_request)
        elif intent == "password_reset":
            graph = self._plan_password_reset(sanitized_request)
        elif intent == "list_users_without_license":
            graph = self._plan_list_unlicensed_users(sanitized_request)
        else:
            graph = self._plan_generic_dashboard_query(sanitized_request)

        self.validator.validate(graph)
        compiled_prompt = self._compile_prompt(graph, chat_history or [])
        return PlanPackage(graph=graph, compiled_prompt=compiled_prompt)

    def _detect_intent(self, request: str) -> str:
        lowered = request.lower()

        if any(token in lowered for token in ["create", "new user", "provision", "add user"]) and any(
            token in lowered for token in ["license", "microsoft", "google-workspace", "adobe"]
        ):
            return "create_user_and_assign_license"
        if any(token in lowered for token in ["create", "new user", "provision", "add user"]):
            return "create_user"

        if "password" in lowered and any(token in lowered for token in ["reset", "change", "credential"]):
            return "password_reset"

        if any(token in lowered for token in ["no license", "without license", "unlicensed"]):
            return "list_users_without_license"

        return "generic_query"

    def _extract_name(self, request: str) -> str:
        quoted = re.findall(r'"([^"]+)"', request)
        if quoted:
            return quoted[0].strip()

        m = re.search(r"(?:named|name is)\s+([A-Za-z ]{3,})", request, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        return "New User"

    def _extract_email(self, request: str, name: str) -> str:
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", request)
        if email_match:
            return email_match.group(0)

        parts = [p for p in re.split(r"\s+", name.lower()) if p]
        if len(parts) >= 2:
            alias = f"{parts[0]}.{parts[-1]}"
        else:
            alias = parts[0] if parts else "user"
        return f"{alias}@corp.com"

    def _extract_license(self, request: str) -> str:
        lowered = request.lower()
        if any(token in lowered for token in ["microsoft", "m365", "microsoft365"]):
            return "microsoft365"
        if any(token in lowered for token in ["google", "workspace", "google-workspace"]):
            return "google-workspace"
        if any(token in lowered for token in ["adobe", "creative cloud", "adobe-cc"]):
            return "adobe-cc"
        return "none"

    def _plan_create_user_and_assign_license(self, request: str) -> TaskGraph:
        name = self._extract_name(request)
        email = self._extract_email(request, name)
        license_name = self._extract_license(request)

        nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Open user provisioning page",
                action=NodeAction.OPEN_CREATE_USER,
                depends_on=["n1"],
                success_criteria="Provision New Identity form is visible",
            ),
            TaskNode(
                id="n3",
                title="Fill provisioning form",
                action=NodeAction.FILL_CREATE_USER_FORM,
                params={
                    "name": name,
                    "email": email,
                    "license": "none",
                },
                depends_on=["n2"],
                success_criteria="Name and email are populated",
            ),
            TaskNode(
                id="n4",
                title="Submit create form",
                action=NodeAction.SUBMIT_CREATE_FORM,
                depends_on=["n3"],
                success_criteria="User appears in directory or profile page",
            ),
            TaskNode(
                id="n5",
                title="Open created user's detail page",
                action=NodeAction.OPEN_USER_DETAIL,
                params={"name": name},
                depends_on=["n4"],
                success_criteria="Managed profile page for the user is open",
            ),
            TaskNode(
                id="n6",
                title="Assign license",
                action=NodeAction.SET_LICENSE,
                params={"license": license_name},
                depends_on=["n5"],
                success_criteria="Seat Assignment dropdown has the requested license",
            ),
            TaskNode(
                id="n7",
                title="Set random password",
                action=NodeAction.SET_PASSWORD,
                params={"mode": "random_strong"},
                depends_on=["n5"],
                success_criteria="Credential Reset field contains a generated password",
            ),
            TaskNode(
                id="n8",
                title="Commit profile changes",
                action=NodeAction.SUBMIT_USER_UPDATE,
                depends_on=["n6", "n7"],
                success_criteria="Update form is submitted successfully",
            ),
            TaskNode(
                id="n9",
                title="Verify license and password update completed",
                action=NodeAction.VERIFY_OUTCOME,
                params={"name": name, "license": license_name},
                depends_on=["n8"],
                success_criteria="Final response confirms user creation and license assignment",
            ),
        ]

        return TaskGraph(
            intent="create_user_and_assign_license",
            user_request=request,
            nodes=nodes,
            notes=[
                "Always remain on local Phoenix dashboard routes.",
                "Use generated random password and include it in final summary.",
            ],
        )

    def _plan_password_reset(self, request: str) -> TaskGraph:
        name = self._extract_name(request)
        nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Search target user",
                action=NodeAction.SEARCH_USER,
                params={"name": name},
                depends_on=["n1"],
                success_criteria="Matching row is visible",
            ),
            TaskNode(
                id="n3",
                title="Open user detail page",
                action=NodeAction.OPEN_USER_DETAIL,
                params={"name": name},
                depends_on=["n2"],
                success_criteria="Managed profile page is visible",
            ),
            TaskNode(
                id="n4",
                title="Set random password",
                action=NodeAction.SET_PASSWORD,
                params={"mode": "random_strong"},
                depends_on=["n3"],
                success_criteria="Credential Reset has generated password",
            ),
            TaskNode(
                id="n5",
                title="Commit changes and verify",
                action=NodeAction.SUBMIT_USER_UPDATE,
                depends_on=["n4"],
                success_criteria="Final response confirms password reset",
            ),
        ]

        return TaskGraph(intent="password_reset", user_request=request, nodes=nodes)

    def _plan_create_user(self, request: str) -> TaskGraph:
        name = self._extract_name(request)
        email = self._extract_email(request, name)
        wants_random_password = any(token in request.lower() for token in ["random password", "strong password", "password"])

        nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Open user provisioning page",
                action=NodeAction.OPEN_CREATE_USER,
                depends_on=["n1"],
                success_criteria="Provision New Identity form is visible",
            ),
            TaskNode(
                id="n3",
                title="Fill provisioning form",
                action=NodeAction.FILL_CREATE_USER_FORM,
                params={"name": name, "email": email, "license": "none"},
                depends_on=["n2"],
                success_criteria="Form fields are filled with requested data",
            ),
            TaskNode(
                id="n4",
                title="Submit create form",
                action=NodeAction.SUBMIT_CREATE_FORM,
                depends_on=["n3"],
                success_criteria="User is created and visible in directory",
            ),
        ]

        if wants_random_password:
            nodes.extend(
                [
                    TaskNode(
                        id="n5",
                        title="Open created user's detail page",
                        action=NodeAction.OPEN_USER_DETAIL,
                        params={"name": name},
                        depends_on=["n4"],
                        success_criteria="Managed profile page for the user is open",
                    ),
                    TaskNode(
                        id="n6",
                        title="Set random password",
                        action=NodeAction.SET_PASSWORD,
                        params={"mode": "random_strong"},
                        depends_on=["n5"],
                        success_criteria="Credential Reset field contains generated password",
                    ),
                    TaskNode(
                        id="n7",
                        title="Commit changes",
                        action=NodeAction.SUBMIT_USER_UPDATE,
                        depends_on=["n6"],
                        success_criteria="Update form is submitted successfully",
                    ),
                ]
            )

        return TaskGraph(intent="create_user", user_request=request, nodes=nodes)

    def _plan_list_unlicensed_users(self, request: str) -> TaskGraph:
        nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Inspect user table for unlicensed users",
                action=NodeAction.VERIFY_OUTCOME,
                params={"license": "none"},
                depends_on=["n1"],
                success_criteria="Final response includes users with license state none",
            ),
        ]
        return TaskGraph(intent="list_users_without_license", user_request=request, nodes=nodes)

    def _plan_generic_dashboard_query(self, request: str) -> TaskGraph:
        nodes = [
            TaskNode(
                id="n1",
                title="Open Phoenix admin dashboard",
                action=NodeAction.NAVIGATE,
                params={"url": PANEL_URL},
                success_criteria="Directory page is visible",
            ),
            TaskNode(
                id="n2",
                title="Execute user request on dashboard",
                action=NodeAction.VERIFY_OUTCOME,
                params={"request": request},
                depends_on=["n1"],
                success_criteria="Final response directly answers the user request",
            ),
        ]
        return TaskGraph(intent="generic_query", user_request=request, nodes=nodes)

    def _compile_prompt(self, graph: TaskGraph, chat_history: List[Tuple[str, str]]) -> str:
        history_lines: List[str] = []
        for idx, (user_turn, agent_turn) in enumerate(chat_history[-4:], start=1):
            history_lines.append(f"Turn {idx} user: {user_turn}")
            history_lines.append(f"Turn {idx} agent: {agent_turn}")

        step_lines = graph.to_step_lines()

        sections = [
            "You are PhoenixWright admin automation agent.",
            f"Hard boundary: Operate ONLY inside {self.policy.allowed_origin}.",
            self.policy.allowed_paths_description(),
            "If navigation drifts to another domain, immediately return to the dashboard and continue.",
            "",
            f"User intent: {graph.intent}",
            f"Original request: {graph.user_request}",
            "",
            "Execution plan (follow in order, respecting dependencies):",
            *step_lines,
        ]

        if graph.notes:
            sections.extend(["", "Plan notes:", *[f"- {note}" for note in graph.notes]])

        if history_lines:
            sections.extend(["", "Recent conversation context:", *history_lines])

        sections.extend(
            [
                "",
                "Completion requirements:",
                "1. Provide a concise outcome summary.",
                "2. Include key fields changed (name, email, license, password if generated).",
                "3. Mention any failure point with exact step id.",
            ]
        )

        return "\n".join(sections)
