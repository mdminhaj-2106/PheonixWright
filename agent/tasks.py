from agent.config import PANEL_URL

def password_reset(name: str, new_password: str) -> str:
    return f"""
You are an IT support agent. Your job:

1. Go to {PANEL_URL}
2. Find the user named "{name}" using the search bar
3. Click the "Manage" link next to their name to open their detail page
4. In the "Credential Reset" field, type "{new_password}"
5. Click "Commit System Changes"
6. Confirm the page reloaded without errors

When done, report: "Password reset complete for {name}."
Do not navigate anywhere else. Do not create new users.
"""
