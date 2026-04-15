from __future__ import annotations
from agent.metrics import MetricsCollector

def handle_slash_command(
    cmd: str,
    *,
    metrics: MetricsCollector,
    history: list,
    orchestrator,
    last_prepared_input: str,
    last_run_summary: str,
    exit_token: str,
) -> bool:
    """
    Dispatch a slash command. Returns True if handled, False if unknown.
    Adding new commands: only touch this file.
    """
    if cmd == "/stats":
        print(metrics.generate_report())
    elif cmd == "/performance":
        for t in metrics.tasks[-5:]:
            print(f"[{t.intent}] {t.duration_s:.1f}s ({t.node_count} nodes)")
    elif cmd == "/explain-error":
        err = getattr(metrics, "_last_error", None)
        print(err or "No error recorded in this session.")
    elif cmd == "/help":
        _print_help(exit_token)
    elif cmd == "/last-run":
        print(last_run_summary or "No execution has completed yet.")
    elif cmd == "/clear":
        history.clear()
        print("Conversation memory cleared.")
    elif cmd == "/history":
        if not history:
            print("No remembered turns yet.")
        for idx, (q, a) in enumerate(history, start=1):
            print(f"[{idx}] You: {q}")
            print(f"[{idx}] Agent: {a}")
    else:
        return False  # unknown command — let runner handle
    return True


def _print_help(exit_token: str) -> None:
    print("Commands:")
    print(f"  /exit or {exit_token}  End chat")
    print("  /plan                  Show plan of last prepared request")
    print("  /last-run              Show summary of last execution")
    print("  /retry                 Retry last prepared request")
    print("  /clear                 Clear conversation memory")
    print("  /history               Show remembered turns")
    print("  /stats                 Session success rate + task list")
    print("  /performance           Last 5 action timings")
    print("  /explain-error         Last structured error detail")
    print("  /help                  Show this list")
