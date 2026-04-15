import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.orchestrator.chat_orchestrator import ChatOrchestrator
from agent.services.browser_agent import BrowserAgentService
from agent.tasks.user_tasks import UserTasks
from agent.state_manager import ExecutionState
from agent.logging_config import configure_logging
from agent.metrics import MetricsCollector, TaskMetrics
from agent.cli_commands import handle_slash_command
import time
from agent.exceptions import (
    ConfigError,
    QuotaExhaustedError,
    BrowserTimeoutError,
    PlanValidationError,
    RetryExhaustedError,
    PhoenixWrightError
)

load_dotenv()


def _read_prompt_from_input(args: argparse.Namespace) -> str:
    if getattr(args, "prompt", None):
        return args.prompt

    prompt_file = getattr(args, "prompt_file", None)
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8").strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return ""


def _build_prompt(args: argparse.Namespace) -> str:
    if args.command == "password-reset":
        return UserTasks.get_password_reset_prompt(args.name, args.new_password).strip()

    if args.command == "ensure-license":
        return UserTasks.get_conditional_create_license_prompt(args.name, args.email, args.license).strip()

    return _read_prompt_from_input(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent.runner",
        description="CLI for querying and operating the Phoenix Wright browser agent.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated task prompt without executing the browser agent.",
    )

    subparsers = parser.add_subparsers(dest="command")

    query_parser = subparsers.add_parser(
        "query",
        help="Run a natural-language prompt against the agent.",
    )
    query_parser.add_argument("prompt", nargs="?", help="Natural language task prompt.")
    query_parser.add_argument(
        "--prompt-file",
        help="Path to a file containing the task prompt.",
    )

    reset_parser = subparsers.add_parser(
        "password-reset",
        help="Reset a user's password from the panel.",
    )
    reset_parser.add_argument("--name", required=True, help="User full name.")
    reset_parser.add_argument(
        "--new-password",
        required=True,
        help="New password to set in Credential Reset.",
    )

    license_parser = subparsers.add_parser(
        "ensure-license",
        help="Find or create a user, then assign the requested license.",
    )
    license_parser.add_argument("--name", required=True, help="User full name.")
    license_parser.add_argument("--email", required=True, help="User corporate email.")
    license_parser.add_argument(
        "--license",
        required=True,
        dest="license",
        help="License slug to assign (for example: adobe-cc).",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Launch chatbot mode with multi-turn context and slash commands.",
    )
    chat_parser.add_argument(
        "--exit-token",
        default="exit",
        help="Keyword used to end the chat session (default: exit).",
    )
    chat_parser.add_argument(
        "--history-turns",
        type=int,
        default=6,
        help="How many user/assistant turns to keep for context (default: 6).",
    )

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Alias for `chat`.",
    )
    interactive_parser.add_argument(
        "--exit-token",
        default="exit",
        help="Keyword used to end the chat session (default: exit).",
    )
    interactive_parser.add_argument(
        "--history-turns",
        type=int,
        default=6,
        help="How many user/assistant turns to keep for context (default: 6).",
    )

    return parser


async def _run_prompt(task_prompt: str):
    return await BrowserAgentService.run_task(task_prompt)


def _stringify_agent_result(result: object) -> str:
    if result is None:
        return ""

    if hasattr(result, "final_result"):
        try:
            final = result.final_result()
            if final:
                return str(final).strip()
        except Exception:
            pass

    return str(result).strip()


def _print_chat_help(exit_token: str) -> None:
    print("Commands:")
    print(f"  /exit or {exit_token}  End chat")
    print("  /plan                  Show plan of last prepared request")
    print("  /last-run              Show summary of last execution")
    print("  /retry                 Retry last prepared request")
    print("  /clear                 Clear conversation memory")
    print("  /history               Show remembered turns")
    print("  /help                  Show command list")


def _print_plan(orchestrator: ChatOrchestrator, user_input: str, history: list[tuple[str, str]]) -> str:
    prepared = orchestrator.prepare_turn(user_input, history)
    graph = prepared.package.graph
    print(f"Plan intent: {graph.intent}")
    for line in graph.to_step_lines():
        print(line)
    return prepared.prompt


async def _run_chat(exit_token: str, dry_run: bool, history_turns: int, metrics: MetricsCollector) -> None:
    print("PhoenixWright chat mode")
    print(f"Type your query and press Enter. Use '/exit' or '{exit_token}' to quit.")
    print("Use '/help' for commands.")

    history: list[tuple[str, str]] = []
    orchestrator = ChatOrchestrator()
    last_prepared_prompt = ""
    last_prepared_input = ""
    last_run_summary = ""

    while True:
        try:
            user_input = input("you> ").strip()
        except EOFError:
            print()
            break

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in {"/exit", exit_token.lower()}:
            break
        
        if handle_slash_command(
            lower,
            metrics=metrics,
            history=history,
            orchestrator=orchestrator,
            last_prepared_input=last_prepared_input,
            last_run_summary=last_run_summary,
            exit_token=exit_token,
        ):
            continue

        if lower == "/plan":
            if not last_prepared_input:
                print("No request prepared yet. Send a query first.")
                continue
            last_prepared_prompt = _print_plan(orchestrator, last_prepared_input, history)
            continue

        current_history = history[-history_turns:] if history_turns > 0 else []

        if lower == "/retry":
            if not last_prepared_prompt:
                print("No prepared request available to retry.")
                continue
            user_input = last_prepared_input
            task_prompt = last_prepared_prompt
            plan_intent = "retry_previous_plan"
            node_count = getattr(metrics, "_last_node_count", 0)
        else:
            prepared = orchestrator.prepare_turn(user_input, current_history)
            task_prompt = prepared.prompt
            plan_intent = prepared.package.graph.intent
            last_prepared_input = user_input
            last_prepared_prompt = task_prompt
            node_count = len(prepared.package.graph.nodes)
            metrics._last_node_count = node_count

        if dry_run:
            print("\nGenerated prompt:\n")
            print(task_prompt)
            print()
            continue

        state = ExecutionState.create(user_input, plan_intent)
        state.mark_running()
        
        start_time = time.time()
        success = False

        try:
            result = await _run_prompt(task_prompt)
            state.mark_complete()
            success = True
            assistant_text = _stringify_agent_result(result)
            if assistant_text:
                print(f"agent> {assistant_text}")
            else:
                print("agent> Completed with no textual output.")
            history.append((user_input, assistant_text or "Completed with no textual output."))
            last_run_summary = (
                f"Last run intent={plan_intent}; input={user_input}; "
                f"output={assistant_text or 'Completed with no textual output.'}"
            )
        except QuotaExhaustedError as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            print(f"\n❌ API quota exceeded. Retry after {e.retry_after}s\n")
        except BrowserTimeoutError as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            print(f"\n⏱️  Timeout during [{e.action}] after {e.seconds}s\n")
        except PlanValidationError as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            print(f"\n🚨 Plan validation failed: {e}\n")
        except RetryExhaustedError as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            print(f"\n🔄 Retry budget exhausted: {e}\n")
        except PhoenixWrightError as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            print(f"\n⚠️  Agent error: {e}\n")
        except Exception as e:
            metrics._last_error = str(e)
            state.mark_error(e)
            import logging
            logging.getLogger(__name__).error("Unexpected error", exc_info=True)
            print(f"\n⚠️  Unexpected: {type(e).__name__}: {str(e)[:120]}\n")
            
        dur = time.time() - start_time
        metrics.record(TaskMetrics(intent=plan_intent, success=success, duration_s=dur, node_count=node_count))


def _legacy_prompt_from_argv(argv: list[str]) -> str:
    if not argv:
        return ""

    first = argv[0]
    known_commands = {"query", "password-reset", "ensure-license", "chat", "interactive"}
    if first in known_commands or first.startswith("-"):
        return ""

    return " ".join(argv).strip()


async def _validate_startup() -> None:
    try:
        BrowserAgentService.validate_api_key()
    except ConfigError as e:
        print(f"\n❌ Configuration error: {e}\n")
        sys.exit(1)


async def main() -> None:
    await _validate_startup()
    configure_logging()
    parser = _build_parser()
    legacy_prompt = _legacy_prompt_from_argv(sys.argv[1:])

    if legacy_prompt:
        args = argparse.Namespace(command="query", prompt=legacy_prompt, prompt_file=None, dry_run=False)
    else:
        args = parser.parse_args()

    if args.command is None and not sys.stdin.isatty():
        args = argparse.Namespace(command="query", prompt=None, prompt_file=None, dry_run=args.dry_run)

    if args.command is None and sys.stdin.isatty():
        args = argparse.Namespace(command="chat", exit_token="exit", history_turns=6, dry_run=args.dry_run)

    if args.command in {"chat", "interactive"}:
        metrics = MetricsCollector()
        await _run_chat(args.exit_token, args.dry_run, args.history_turns, metrics)
        return

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    task_prompt = _build_prompt(args)
    if not task_prompt:
        parser.error("No prompt provided. Pass text, --prompt-file, or pipe input to stdin.")

    if args.command == "query":
        orchestrator = ChatOrchestrator()
        task_prompt = orchestrator.prepare_turn(task_prompt, []).prompt

    if args.dry_run:
        print(task_prompt)
        return

    try:
        result = await _run_prompt(task_prompt)
        rendered = _stringify_agent_result(result)
        print("Agent output:", rendered if rendered else result)
    except QuotaExhaustedError as e:
        print(f"\n❌ API quota exceeded. Retry after {e.retry_after}s\n")
        sys.exit(1)
    except BrowserTimeoutError as e:
        print(f"\n⏱️  Timeout during [{e.action}] after {e.seconds}s\n")
        sys.exit(1)
    except PlanValidationError as e:
        print(f"\n🚨 Plan validation failed: {e}\n")
        sys.exit(1)
    except RetryExhaustedError as e:
        print(f"\n🔄 Retry budget exhausted: {e}\n")
        sys.exit(1)
    except PhoenixWrightError as e:
        print(f"\n⚠️  Agent error: {e}\n")
        sys.exit(1)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Unexpected error", exc_info=True)
        print(f"\n⚠️  Unexpected: {type(e).__name__}: {str(e)[:120]}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
