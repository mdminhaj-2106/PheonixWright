# Phoenix Admin Support Agent

An autonomous AI agent orchestrating automated IT administration tasks leveraging **browser-use**, **Playwright**, and the **Gemini 2.0 Flash** LLM acting against a custom asynchronous FastAPI web panel.

## Architecture Pipeline
```text
Natural language request
        │
        ▼
┌─────────────────────────┐
│   browser-use Agent     │  ← Gemini 2.0 Flash
│   Observe → Decide → Act│  ← Playwright headless execution
└────────────┬────────────┘
             │  HTTP (localhost:8000)
             ▼
┌─────────────────────────┐
│   FastAPI Admin Panel   │  ← Asynchronous SQLAlchemy ORM 
│   SQLite Database       │  ← /reset route for clean automation runs
└─────────────────────────┘
```

## Setup & Deployment

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Environment Variables**
   Duplicate `.env.example` into a new `.env` file and insert your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_genai_token
   ```

3. **Start the Fast API Backend**
   In terminal 1, boot the server:
   ```bash
   uvicorn panel.main:app --port 8000
   ```

4. **Prepare the Database state**
   Before running the agent, ensuring the database is in a clean seed state is crucial.
   ```bash
   curl -X POST localhost:8000/reset
   ```

5. **Run Agent Tasks with the CLI**
   In terminal 2, use the CLI in `agent.runner`.

   *Chatbot mode (default)*
   ```bash
   python3 -m agent.runner
   ```
   Then type prompts directly (`you> ...`). Commands:
   - `/help` shows chat commands
   - `/history` shows remembered turns
   - `/clear` clears remembered turns
   - `/exit` exits chat mode

   *Ad-hoc query prompt*
   ```bash
   python3 -m agent.runner query "Go to the panel and list all users with no license"
   ```

   *Password reset workflow*
   ```bash
   python3 -m agent.runner password-reset --name "Alice Johnson" --new-password "new_password123"
   ```

   *Find-or-create + assign license workflow*
   ```bash
   python3 -m agent.runner ensure-license --name "Dave Torres" --email "dave@corp.com" --license "adobe-cc"
   ```

   *Explicit chat mode*
   ```bash
   python3 -m agent.runner chat
   ```

   *Interactive alias (same behavior as chat mode)*
   ```bash
   python3 -m agent.runner interactive
   ```

   *Preview generated prompt without running browser automation*
   ```bash
   python3 -m agent.runner ensure-license --name "Dave Torres" --email "dave@corp.com" --license "adobe-cc" --dry-run
   ```
