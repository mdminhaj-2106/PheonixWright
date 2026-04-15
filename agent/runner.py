import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.services.browser_agent import BrowserAgentService
from agent.tasks.user_tasks import UserTasks

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


def _build_chat_task_prompt(history: list[tuple[str, str]], user_input: str, history_turns: int) -> str:
    turns = history[-history_turns:] if history_turns > 0 else []
    if not turns:
        return user_input

    transcript_lines = [
        "Conversation context (most recent turns):",
    ]
    for prev_user, prev_assistant in turns:
        transcript_lines.append(f"User: {prev_user}")
        transcript_lines.append(f"Assistant: {prev_assistant}")

    transcript_lines.extend(
        [
            "",
            "New user request:",
            user_input,
            "",
            "Instruction: Use conversation context only where relevant. Prioritize the new request.",
        ]
    )
    return "\n".join(transcript_lines)


def _print_chat_help(exit_token: str) -> None:
    print("Commands:")
    print(f"  /exit or {exit_token}  End chat")
    print("  /clear                 Clear conversation memory")
    print("  /history               Show remembered turns")
    print("  /help                  Show command list")


async def _run_chat(exit_token: str, dry_run: bool, history_turns: int) -> None:
    print("PhoenixWright chat mode")
    print(f"Type your query and press Enter. Use '/exit' or '{exit_token}' to quit.")
    print("Use '/help' for commands.")

    history: list[tuple[str, str]] = []

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
        if lower == "/help":
            _print_chat_help(exit_token)
            continue
        if lower == "/clear":
            history.clear()
            print("Conversation memory cleared.")
            continue
        if lower == "/history":
            if not history:
                print("No remembered turns yet.")
                continue
            for idx, (q, a) in enumerate(history, start=1):
                print(f"[{idx}] You: {q}")
                print(f"[{idx}] Agent: {a}")
            continue

        task_prompt = _build_chat_task_prompt(history, user_input, history_turns)

        if dry_run:
            print("\nGenerated prompt:\n")
            print(task_prompt)
            print()
            continue

        try:
            result = await _run_prompt(task_prompt)
            assistant_text = _stringify_agent_result(result)
            if assistant_text:
                print(f"agent> {assistant_text}")
            else:
                print("agent> Completed with no textual output.")
            history.append((user_input, assistant_text or "Completed with no textual output."))
        except Exception:
            import traceback

            traceback.print_exc()


def _legacy_prompt_from_argv(argv: list[str]) -> str:
    if not argv:
        return ""

    first = argv[0]
    known_commands = {"query", "password-reset", "ensure-license", "chat", "interactive"}
    if first in known_commands or first.startswith("-"):
        return ""

    return " ".join(argv).strip()


async def main() -> None:
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
        await _run_chat(args.exit_token, args.dry_run, args.history_turns)
        return

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    task_prompt = _build_prompt(args)
    if not task_prompt:
        parser.error("No prompt provided. Pass text, --prompt-file, or pipe input to stdin.")

    if args.dry_run:
        print(task_prompt)
        return

    try:
        result = await _run_prompt(task_prompt)
        rendered = _stringify_agent_result(result)
        print("Agent output:", rendered if rendered else result)
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
