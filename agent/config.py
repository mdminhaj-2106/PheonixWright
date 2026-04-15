import os

PANEL_URL = "http://localhost:8000"
ALLOWED_ORIGINS = [PANEL_URL]
ALLOWED_PANEL_PATH_PREFIXES = ["/", "/users", "/reset"]

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
PLANNER_MODEL = os.getenv("GEMINI_PLANNER_MODEL", FALLBACK_MODEL or MODEL)

MAX_STEPS = 20
PLAN_MAX_NODES = 15
PLAN_MAX_ATTEMPTS = 2

RETRY_CONFIG = {
    "max_retries": 5,
    "base_delay_seconds": 1.0,
    "max_delay_seconds": 60.0,
}
