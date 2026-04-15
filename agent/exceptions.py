class PhoenixWrightError(Exception):
    """Base class for all agent-related errors."""
    pass


class ConfigError(PhoenixWrightError):
    """Invalid or missing configuration (API keys, env)."""
    pass


class APIError(PhoenixWrightError):
    """LLM or external API failure."""

    def __init__(self, code: int, message: str, retry_after: int | None = None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(message)


class QuotaExhaustedError(APIError):
    """API quota exceeded."""
    pass


class PlanValidationError(PhoenixWrightError):
    """Planner generated invalid graph."""
    pass


class BrowserTimeoutError(PhoenixWrightError):
    """Browser action exceeded allowed time."""

    def __init__(self, action: str, seconds: int):
        self.action = action
        self.seconds = seconds
        super().__init__(f"{action} timed out after {seconds}s")


class StagnationError(PhoenixWrightError):
    """Agent made no progress."""
    pass


class RetryExhaustedError(PhoenixWrightError):
    """Retry attempts exceeded."""
    pass