import os

PANEL_URL = "http://localhost:8000"
ALLOWED_ORIGINS = [PANEL_URL]
ALLOWED_PANEL_PATH_PREFIXES = ["/", "/users", "/reset"]

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")

MAX_STEPS = 20
PLAN_MAX_NODES = 15
