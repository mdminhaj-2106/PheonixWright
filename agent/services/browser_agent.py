import os
from browser_use import Agent
from agent.exceptions import ConfigError
from browser_use.llm.google.chat import ChatGoogle
from agent.config import FALLBACK_MODEL, MODEL, MAX_STEPS, RETRY_CONFIG, ACTION_TIMEOUTS
from agent.retry import RetryStrategy

class BrowserAgentService:
    @staticmethod
    def validate_api_key() -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ConfigError("GEMINI_API_KEY is not set. Add it to your .env file.")
        if len(api_key) < 20:
            raise ConfigError("GEMINI_API_KEY looks malformed (too short).")

    @staticmethod
    def get_agent(task_prompt: str) -> Agent:
        BrowserAgentService.validate_api_key()
        api_key = os.getenv("GEMINI_API_KEY")

        llm = ChatGoogle(model=MODEL, api_key=api_key)
        fallback_llm = None
        if FALLBACK_MODEL and FALLBACK_MODEL != MODEL:
            fallback_llm = ChatGoogle(model=FALLBACK_MODEL, api_key=api_key)

        return Agent(
            task=task_prompt,
            llm=llm,
            fallback_llm=fallback_llm,
            max_steps=MAX_STEPS,
            action_timeouts=ACTION_TIMEOUTS
        )
    
    @staticmethod
    async def run_task(task_prompt: str):
        agent = BrowserAgentService.get_agent(task_prompt)
        retry_strategy = RetryStrategy(
            max_retries=RETRY_CONFIG["max_retries"],
            base_delay=RETRY_CONFIG["base_delay_seconds"],
            max_delay=RETRY_CONFIG["max_delay_seconds"]
        )
        return await retry_strategy.execute_with_retry(agent.run)
