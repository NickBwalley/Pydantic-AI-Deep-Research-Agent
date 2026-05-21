# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Run the app
python main.py                 # Launches Gradio UI at http://127.0.0.1:7860
```

No test suite exists yet. To test changes, run `main.py` and submit a query through the UI.

## Environment

Requires a `.env` file in the project root:
```
OPENAI_API_KEY=sk-...
```

## Architecture

This is a multi-agent deep research system with a strict pipeline. All orchestration lives in `research_agent.py`; `main.py` is only UI (Gradio).

### Data Flow

```
User Input → classify_agent → plan_agent → research_worker_agent (×N parallel) → writer_agent → ResearchReport
```

The `deep_research()` function in `research_agent.py` is an **async generator** — it yields status strings throughout execution, and finally yields a `ResearchReport` Pydantic model. `main.py` consumes this generator to drive the Gradio chat stream.

### Four Agents and Their Roles

| Agent | Role | Output Type |
|---|---|---|
| `classify_agent` | Determines if input is a stock ticker or general topic | `ClassificationResult` |
| `plan_agent` | Generates 3–4 distinct research angles | `List[ResearchAngle]` |
| `research_worker_agent` | Researches one angle using web tools | `ResearchSection` |
| `writer_agent` | Synthesizes all sections into final report | `ResearchReport` |

### Tools (registered on `research_worker_agent` only)

- `search` — wraps `search_tool()`, which calls DuckDuckGo (`ddgs`) for up to 5 results
- `fetch_page` — wraps `fetch_page_tool()`, fetches a URL via `httpx`, strips HTML with BeautifulSoup, returns up to 10,000 chars

Tools receive a `RunContext[ResearchDeps]` for dependency injection. `ResearchDeps` holds a shared `httpx.AsyncClient` that is created once per `deep_research()` call.

### Key Pydantic Models

- `ResearchAngle` — title, keywords list, description (planner output, worker input)
- `ResearchSection` — title, content, sources list (one per research angle)
- `ResearchReport` — executive_summary, sections, risks_uncertainties, what_to_watch_next

### Parallelism

The four `process_angle()` coroutines inside `deep_research()` run concurrently via `asyncio.gather`. All agents use `openai:gpt-5-mini-2025-08-07`.

## Adding New Agents or Tools

- Define new agents using `Agent(model, system_prompt=..., output_type=...)` in `research_agent.py`
- Register tools on an agent with `@agent.tool` decorator; functions must accept `ctx: RunContext[ResearchDeps]` as first arg
- Keep `ResearchDeps` as the single dependency container — add fields there rather than creating new dep types
