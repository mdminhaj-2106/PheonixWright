from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict


class OrchestratorState(TypedDict, total=False):
    request: str
    history: List[Tuple[str, str]]
    raw_plan: str
    payload: Dict[str, Any]
    graph_obj: Optional[Any]
    compiled_prompt: str
    error: str
    attempts: int
    fallback_used: bool
    validation_error_count: int
