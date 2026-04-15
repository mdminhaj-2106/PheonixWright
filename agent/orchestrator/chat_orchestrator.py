from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from agent.planner.decomposer import PlanPackage, RuleBasedTaskDecomposer


@dataclass
class PreparedTurn:
    package: PlanPackage
    prompt: str


class ChatOrchestrator:
    def __init__(self) -> None:
        self.decomposer = RuleBasedTaskDecomposer()

    def prepare_turn(self, user_input: str, history: List[Tuple[str, str]]) -> PreparedTurn:
        package = self.decomposer.build_plan(user_input, history)
        return PreparedTurn(package=package, prompt=package.compiled_prompt)
