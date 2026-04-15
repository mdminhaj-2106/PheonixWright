import json, time, uuid
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

CHECKPOINT_DIR = Path(".phoenix_checkpoints")

@dataclass
class ExecutionState:
    session_id: str
    user_input: str
    plan_intent: str
    status: str          # "pending" | "running" | "complete" | "error"
    error: Optional[str]
    started_at: float
    completed_at: Optional[float]

    @classmethod
    def create(cls, user_input: str, intent: str) -> "ExecutionState":
        return cls(session_id=str(uuid.uuid4()), user_input=user_input,
                   plan_intent=intent, status="pending", error=None,
                   started_at=time.time(), completed_at=None)

    def save(self) -> None:
        CHECKPOINT_DIR.mkdir(exist_ok=True)
        path = CHECKPOINT_DIR / f"{self.session_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2))

    def mark_running(self) -> None:
        self.status = "running"; self.save()

    def mark_complete(self) -> None:
        self.status = "complete"; self.completed_at = time.time(); self.save()

    def mark_error(self, exc: Exception) -> None:
        self.status = "error"; self.error = str(exc); self.completed_at = time.time(); self.save()
