import os
from browser_use import Agent
from browser_use.llm.google.chat import ChatGoogle
from agent.config import FALLBACK_MODEL, MODEL, MAX_STEPS

class BrowserAgentService:
    @staticmethod
    def get_agent(task_prompt: str) -> Agent:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in environment.")

        llm = ChatGoogle(model=MODEL, api_key=api_key)
        fallback_llm = None
        if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
            fallback_llm = ChatGoogle(model=FALLBACK_MODEL, api_key=api_key)

        return Agent(task=task_prompt, llm=llm, fallback_llm=fallback_llm, max_steps=MAX_STEPS)
    
    @staticmethod
    async def run_task(task_prompt: str):
        agent = BrowserAgentService.get_agent(task_prompt)
        result = await agent.run()
        return result
