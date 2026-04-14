# IT Support Agent — Implementation Plan & Pseudo-code Guide

This document outlines the detailed architecture and pseudo-code for the IT Support Agent system, bridging a FastAPI administrative backend with a headless browser-use agent for automated IT provisioning tasks.

## 1. Project Structure

The repository maintains a clean separation of concerns across a web panel and an automated agent module:

```
it-support-agent/
├── panel/
│   ├── main.py            # FastAPI main router and lifespans
│   ├── database.py        # Asynchronous SQLite operations
│   ├── models.py          # Pydantic schemas for data validation
│   └── templates/         # Jinja2 HTML views
│       ├── base.html
│       ├── users.html
│       ├── create.html
│       └── detail.html
├── agent/
│   ├── runner.py          # Entry point for browser-use agent
│   ├── tasks.py           # NLP instructions mapping for Claude
│   └── config.py          # LLM and generic environment configs
├── tests/
│   ├── test_panel.py
│   └── test_agent.py
├── requirements.txt
├── .env.example
├── Plan.md                # This planning document
└── README.md
```

---

## 2. Phase 1: FastAPI Admin Panel (Pseudo-code)

The goal is to establish a non-SPA frontend. This simplifies the testing environment avoiding dynamic client-side rendering complexities during agent interactions.

### `panel/database.py`

**Purpose**: Manage database schema and baseline mock data.

```python
# pseudo-code: panel/database.py

import asynchronous_sqlite_library

DEFINE database_path as "panel/it_support.db"
DEFINE schema with fields: id, name, email, password, license, created_at

FUNCTION init_db():
    CONNECT to db asynchronously
    EXECUTE schema creation
    INSERT seed data (Alice, Bob, Carol) IF NOT EXISTS
    COMMIT

FUNCTION reset_db():
    CONNECT to db asynchronously
    DROP table users
    CALL init_db logic
```

### `panel/models.py`

**Purpose**: Input validation to defend routes against malformed requests.

```python
# pseudo-code: panel/models.py
import robust_validation_library (e.g., pydantic)

DEFINE Enum LicenseType (none, microsoft, google, adobe)

CLASS UserCreate (BaseModel):
    name: string
    email: valid_email_string
    license: LicenseType default 'none'

CLASS UserUpdate:
    license: LicenseType
    password: optional_string
```

### `panel/main.py`

**Purpose**: Handle server routing and template rendering.

```python
# pseudo-code: panel/main.py
import web_framework, templating_engine, database_module

INITIALIZE app
INITIALIZE view_templates from "panel/templates"

ON STARTUP:
    CALL init_db()

ROUTE GET '/' (Query Params: q=""):
    IF q provided:
        SEARCH db where name OR email matches %q%
    ELSE:
        FETCH ALL users
    RENDER "users.html" with context {users, query=q}

ROUTE GET '/users/create':
    RENDER "create.html"

ROUTE POST '/users/create' (Form Data: name, email, license):
    TRY:
        INSERT into db (name, email, license)
        REDIRECT to '/'
    CATCH DuplicateEmailError:
        RETURN HTTP 409

ROUTE GET '/users/{user_id}':
    FETCH user from db where ID = user_id
    IF NOT user: RETURN HTTP 404
    RENDER "detail.html" with context {user}

ROUTE POST '/users/{user_id}/update' (Form Data: license, password=None):
    UPDATE user in db set license = provided_license
    IF password is not None:
        UPDATE user in db set password = provided_password
    REDIRECT to '/users/{user_id}'

ROUTE POST '/reset':
    CALL reset_db()
    RETURN success_message
```

---

## 3. Phase 2: Agent Execution System (Pseudo-code)

We will abstract complex browser control through an LLM reasoning engine mapping intent to action.

### `agent/config.py`

**Purpose**: Maintain static constraints and URIs.

```python
# pseudo-code: agent/config.py

PANEL_URL = HTTP_ADDRESS_OF_PANEL
LLM_MODEL = "claude-sonnet-4-20250514"
AGENT_TIMEOUT_STEPS = 20
```

### `agent/tasks.py`

**Purpose**: Format prompt instruction strings.

```python
# pseudo-code: agent/tasks.py

FUNCTION password_reset(name, new_password):
    RETURN formatted_string:
        1. Navigate to PANEL_URL
        2. Enter {name} into search bar and submit
        3. Click user name in results
        4. Populate 'password' input with {new_password}
        5. Submit Save button

FUNCTION conditional_create_and_license(name, email, license):
    RETURN formatted_string:
        1. Navigate to PANEL_URL
        2. Search for {name}
        3. IF RESULTS EXIST:
            Click user profile
        4. IF RESULTS DO NOT EXIST:
            Click '+ New User'
            Fill form ({name}, {email})
            Submit form
            Click the newly created user profile
        5. Select {license} from license dropdown
        6. Submit Save button
```

### `agent/runner.py`

**Purpose**: The entry script that dispatches the agent against Playwright environments.

```python
# pseudo-code: agent/runner.py

import browser_agent_library, llm_integration
import config, tasks

ASYNC FUNCTION execute_task(task_instruction):
    INITIALIZE llm_engine with config.LLM_MODEL
    INITIALIZE agent with (task_instruction, llm_engine, max_steps=config.AGENT_TIMEOUT_STEPS)
    RESULT = AWAIT agent.run_sequence()
    RETURN RESULT

IF SCRIPT RUN DIRECTLY:
    PARSE CLI argument as task_instruction
    RUN execute_task(task_instruction)
```

## 4. Workflows

**1. Normal Dev Execution**:
1. Spawn terminal running the fastAPI app via equivalent of `uvicorn panel.main:app`.
2. Spawn agent runner pointing at the panel targeting an action string.

**2. Test Execution Context**:
Before engaging integration tests, `reset_db()` is explicitly pinged to return to pristine schemas, avoiding state leakage between test executions or demo recordings.
