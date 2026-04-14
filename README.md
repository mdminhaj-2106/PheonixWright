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

5. **Deploy the Agent Tasks**
   In terminal 2, execute the runner specifying the command payloads defined in `agent/tasks.py`.
   
   *Example 1: The Password Reset loop*
   ```bash
   python -m agent.runner "$(python -c "from agent.tasks import password_reset; print(password_reset('Alice Johnson', 'new_password123'))")"
   ```
   
   *Example 2: The Complex Conditional Loop*
   ```bash
   python -m agent.runner "$(python -c "from agent.tasks import conditional_create_and_license; print(conditional_create_and_license('Dave Torres', 'dave@corp.com', 'adobe-cc'))")"
   ```
