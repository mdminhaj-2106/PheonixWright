import os

PANEL_URL = "http://localhost:8000"

# Keep defaults on lower-cost models that are more likely to be available on free-tier keys.
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")

MAX_STEPS = 20
