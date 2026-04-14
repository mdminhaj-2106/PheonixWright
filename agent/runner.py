import asyncio
import os
from browser_use import Agent
from browser_use.llm.google.chat import ChatGoogle
from agent.config import FALLBACK_MODEL, MODEL, MAX_STEPS
from dotenv import load_dotenv

load_dotenv()

async def run_task(task: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in environment.")

    llm = ChatGoogle(model=MODEL, api_key=api_key)
    fallback_llm = None
    if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
        fallback_llm = ChatGoogle(model=FALLBACK_MODEL, api_key=api_key)

    agent = Agent(task=task, llm=llm, fallback_llm=fallback_llm, max_steps=MAX_STEPS)
    result = await agent.run()
    print("Agent output:", result)
    return result

if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task:
        print("Usage: python -m agent.runner \"<task string>\"")
        sys.exit(1)
        
    try:
        asyncio.run(run_task(task))
    except Exception as e:
        import traceback
        traceback.print_exc()
