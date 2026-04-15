from __future__ import annotations

from urllib.parse import urlparse

from agent.config import PANEL_URL


class DashboardPolicy:
    """Guards planning/execution so the agent stays inside the local admin dashboard."""

    def __init__(self, panel_url: str = PANEL_URL) -> None:
        self.panel_url = panel_url.rstrip("/")
        parsed = urlparse(self.panel_url)
        self._allowed_origin = f"{parsed.scheme}://{parsed.netloc}"

    @property
    def allowed_origin(self) -> str:
        return self._allowed_origin

    def is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin == self._allowed_origin

    def sanitize_user_request(self, text: str) -> str:
        """Strip unsupported external-domain instructions while preserving admin intent."""
        lowered = text.lower()
        blocked_tokens = [
            "admin.microsoft.com",
            "microsoft 365 admin center",
            "google admin",
            "okta",
            "entra",
        ]
        if any(token in lowered for token in blocked_tokens):
            return (
                "Operate only on the local Phoenix admin dashboard. "
                "Do not open any external admin portal. "
                f"Original intent: {text.strip()}"
            )
        return text.strip()

    def allowed_paths_description(self) -> str:
        return (
            "Allowed routes: /, /users/create, /users/{id}, /users/{id}/update, /reset. "
            "Avoid all other domains and admin portals."
        )
