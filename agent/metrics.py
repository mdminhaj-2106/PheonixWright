from dataclasses import dataclass, field
from typing import List
import time

@dataclass
class TaskMetrics:
    intent: str
    success: bool
    duration_s: float
    node_count: int

@dataclass
class MetricsCollector:
    tasks: List[TaskMetrics] = field(default_factory=list)

    def record(self, m: TaskMetrics) -> None:
        self.tasks.append(m)

    def success_rate(self) -> float:
        if not self.tasks: return 0.0
        return sum(1 for t in self.tasks if t.success) / len(self.tasks)

    def generate_report(self) -> str:
        if not self.tasks:
            return "No tasks recorded yet."
        rate = self.success_rate()
        avg_dur = sum(t.duration_s for t in self.tasks) / len(self.tasks)
        lines = [
            f"Session tasks: {len(self.tasks)}",
            f"Success rate:  {rate:.0%}",
            f"Avg duration:  {avg_dur:.1f}s",
        ]
        for t in self.tasks[-5:]:
            status = "✅" if t.success else "❌"
            lines.append(f"  {status} [{t.intent}] {t.duration_s:.1f}s ({t.node_count} nodes)")
        return "\n".join(lines)
