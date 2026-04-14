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

def conditional_create_and_license(name: str, email: str, license: str) -> str:
    return f"""
You are an IT support agent. Your job:

1. Go to {PANEL_URL}
2. Search for "{name}" using the search bar
3. Wait for the active directory table to fully load. Read the entire results block.
4. BRANCH logic based on results:
   - If the user DEFINITELY appears in results: 
       Click the "Manage" link next to their name.
   - If the user does NOT appear in results (e.g. indicates 'No identities found'):
       Click "+ Provision User" in the navigation bar.
       Fill in Full Name="{name}", Corporate Email="{email}", and leave license as "none".
       Click "Provision Access".
       Wait for the redirect. Find the newly created profile '{name}' in the directory and click "Manage".
5. On the detail page: set the "Seat Assignment" dropdown to "{license}"
6. Click "Commit System Changes"
7. Confirm the change was saved successfully

When done, report one of:
- "Created {name} and assigned {license}."
- "Found existing user {name} and updated license to {license}."
"""
