import asyncio, random, logging
from agent.exceptions import APIError, RetryExhaustedError

TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}

class RetryStrategy:
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def is_transient_error(self, exc: Exception) -> bool:
        if isinstance(exc, APIError):
            return exc.code in TRANSIENT_HTTP_CODES
        return False

    async def execute_with_retry(self, fn, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                if attempt == self.max_retries or not self.is_transient_error(exc):
                    raise
                delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 0.5), self.max_delay)
                await asyncio.sleep(delay)
        raise RetryExhaustedError(f"All {self.max_retries} retries consumed")
