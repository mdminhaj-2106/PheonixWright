import os

PANEL_URL = "http://localhost:8000"
ALLOWED_ORIGINS = [PANEL_URL]
ALLOWED_PANEL_PATH_PREFIXES = ["/", "/users", "/reset"]

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
PLANNER_MODEL = os.getenv("GEMINI_PLANNER_MODEL", FALLBACK_MODEL or MODEL)

MAX_STEPS = 100
PLAN_MAX_NODES = 50
PLAN_MAX_ATTEMPTS = 3

ACTION_TIMEOUTS: dict[str, int] = {
    "navigate":               15,
    "search_user":            10,
    "fill_create_user_form":   8,
    "submit_create_form":     10,
    "set_license":             8,
    "set_password":            8,
    "submit_user_update":     10,
    "delete_user":            10,
    "dynamic_routine":       120,
    "verify_outcome":         20,
}
RETRY_CONFIG = {
    "max_retries": 5,
    "base_delay_seconds": 1.0,
    "max_delay_seconds": 60.0,
}
