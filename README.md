# Phoenix Wright: Autonomous IT Administration Agent

**Phoenix Wright** is a high-availability, agentic automation infrastructure engineered to securely orchestrate complex IT administration workflows. By bridging the cognitive planning capabilities of the **Gemini 2.0 Flash LLM** with headless browser traversal (`browser-use` & `Playwright`), Phoenix operates fully autonomously to execute stateful tasks against asynchronous FastAPI panels.

---

## Architecture Pipeline

The system is built on a decoupled, deterministic agentic loop utilizing LangGraph pattern principles to enforce rigid constraints over LLM non-determinism.

```mermaid
graph TD
    
    A[Natural Language Request] --> B

    subgraph "Logical Planning Engine - LangGraph"
        B(ChatOrchestrator):::agent --> C{TaskGraphValidator}
        C -- "Schema Violation (Cycle/Bounds)" --> B
        C -- "Valid Map" --> D[PlanPackage]
    end

    D --> E(BrowserAgentService):::llm
    
    subgraph "Execution Layer"
        E -- "Playwright Nav/Click/Type" --> F[(FastAPI Admin Panel - Async SQLAlchemy)]:::web
    end
    
    F -. "Final UI State" .-> E
    E --> G[State Checkpointing & Metrics]
```

## Module-Wise Engineering Rationale

### 1. `agent/orchestrator/` — The Cognitive State Machine
Handles the state transitions between natural language input and strict graph construction.
- **`chat_orchestrator.py`**: The primary owner of the LangGraph workflow. It parses user intent, routes logic, and intercepts schema failure traps via LLM retries (up to `PLAN_MAX_ATTEMPTS`).
- **`nodes.py`**: A factory for isolated, side-effect-free cognitive node operations.
- **`state.py`**: Defines the statically typed `OrchestratorState`, functioning as the source of truth across all graph edges.

### 2. `agent/planner/` — The Validation Sandbox
Ensures LLM output is structurally sound before permitting network execution.
- **`schemas.py` & `validator.py`**: Evaluates LLM intents into a `TaskGraph`. Employs automated Kahn’s Sorting algorithms to intercept infinite topological cycles. Throws isolated fault indicators like `CapacityExceededError` or `UnsupportedActionError` instead of generalized failure states.
- **`plan_prompt.py`**: Injects aggressive boundary alignment instructions, actively restricting drifting and enforcing atomic steps for complex workflows (up to 50 nodes limit).

### 3. Core Robustness & Telemetry infrastructure
Built into the structural backbone for extensive operational reliability (Track B protocol framework).
- **`agent/exceptions.py`**: Granular exception taxonomy mapped perfectly to runtime faults (`BrowserTimeoutError`, `QuotaExhaustedError`, `PlanValidationError`), discarding ambiguity gracefully.
- **`agent/retry.py`**: An asynchronous network resilience wrapper dynamically mapping mathematically capped exponential backoff logic mapping against standard transit anomalies (502, 503, 504 codes).
- **`agent/state_manager.py`**: Realtime `.phoenix_checkpoints/` IO caching of node-level metadata for robust audit-trails.
- **`agent/metrics.py`**: Session retention tracking for timing variances, efficiency markers, and slash command diagnostics.

### 4. `panel/` — The Web Simulation Target
A native, locally hosted asynchronous Python `FastAPI` instance interacting with `SQLite` under `SQLAlchemy` acting as the automation testing vector enforcing dynamic DOM payloads (Forms, Selectors, JS Rendering).

---

## Setup & Deployment Instructions

### 1. Provision the Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Local Environment State
Duplicate `.env.example` into a local `.env` and grant Gemini integration key provisioning:
```env
GEMINI_API_KEY=your_genai_token
```

### 3. Spin Up Infrastructure
Initialize the headless testing backend on terminal 1:
```bash
uvicorn panel.main:app --port 8000
```
> **Critical Edge Testing:** Force a clean `SQLite` initial bootstrap layer using `curl -X POST localhost:8000/reset` to wipe contaminated profile data between test rounds.

### 4. Engage the Agent Output Subsystem
In terminal 2, execute binary entries targeting the central `agent.runner`:

#### Conversational Shell Environment (Default execution)
```bash
python3 -m agent.runner chat
```
Available Slash Directives:
* `/help` — Contextual diagnostic mapping overview
* `/stats` — Granular session-level compute timeline and network telemetry overview
* `/plan` — Visual readout of the compiled micro-step graph dependencies
* `/retry` — Instantly retrigger the previous package loop

#### Direct Command Mode Processing
Launch targeted operational routines seamlessly decoupled from interactive chat instances:

```bash
# Complex ad-hoc relational requests
python3 -m agent.runner query "Go to the panel and list all users with no license"

# Enforced script workflows
python3 -m agent.runner password-reset --name "Alice Johnson" --new-password "new_password123"

# Granular workflow preview constraints (Bypass Automation / Dump AI prompt context logs)
python3 -m agent.runner ensure-license --name "Dave Torres" --email "dave@corp.com" --license "adobe-cc" --dry-run
```
