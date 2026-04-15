from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import TypedDict
from agent.planner.schemas import TaskGraph

class PlannerState(TypedDict, total=False):
    request: str
    history: List[Tuple[str, str]]
    raw_plan: str
    payload: Dict[str, Any]
    graph_obj: Optional[TaskGraph]
    compiled_prompt: str
    error: str
    attempts: int
    fallback_used: bool
    validation_error_count: int
