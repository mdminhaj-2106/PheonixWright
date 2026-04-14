import asyncio
from dotenv import load_dotenv
from agent.services.browser_agent import BrowserAgentService

load_dotenv()

async def main():
    import sys
    task_prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task_prompt:
        print("Usage: python -m agent.runner \"<task string>\"")
        sys.exit(1)
        
    try:
        result = await BrowserAgentService.run_task(task_prompt)
        print("Agent output:", result)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
