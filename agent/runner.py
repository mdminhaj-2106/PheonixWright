import asyncio
import os
from browser_use import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.config import MODEL, MAX_STEPS
from dotenv import load_dotenv

# Load secret environment variables
load_dotenv()

async def run_task(task: str):
    llm = ChatGoogleGenerativeAI(model=MODEL)
    agent = Agent(task=task, llm=llm, max_steps=MAX_STEPS)
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
        print(f"Agent failed with exception: {e}")
