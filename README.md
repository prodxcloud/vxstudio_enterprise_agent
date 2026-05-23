# vxstudio_enterprise_agent

**Enterprise Customer-Experience Agents — Customer Onboarding + Customer Training.**

Minimal LangChain ReAct agent service. Two agents, one FastAPI app, no database, no monitoring stack. Pairs with [vxstudio_enterprise_llm](../vxstudio_enterprise_llm/) which provides the FAISS-backed customer-support knowledge base both agents call as a tool.

## Layout

```
vxstudio_enterprise_agent/
├── app.py                          # FastAPI on port 8002
├── requirements.txt
└── services/
    └── ai/
        ├── onboarding_agent/
        │   ├── agent.py            # LangChain ReAct agent (Aria)
        │   ├── soul.md             # persona + boundaries
        │   └── skill.md            # tools + patterns
        └── training_agent/
            ├── agent.py            # LangChain ReAct agent (Theo)
            ├── soul.md
            └── skill.md
```

## Run it

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (or: source venv/bin/activate on Unix)
pip install -r requirements.txt

# BYOK — set one of these:
$env:ANTHROPIC_API_KEY = "sk-ant-..."     # PowerShell
# or
$env:OPENAI_API_KEY = "sk-..."

python app.py
```

Server listens on **port 8002**. Pair-deployed with `vxstudio_enterprise_llm` on **port 8001**.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health`                       | Readiness probe + provider/LLM-URL status |
| GET  | `/agents/{name}/persona`        | Inspect the loaded soul.md + skill.md |
| POST | `/agents/onboarding/chat`       | Talk to Aria (onboarding) |
| POST | `/agents/training/chat`         | Talk to Theo (training) |

Request body for `/chat`:

```json
{ "message": "I just signed up, where do I start?" }
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | unset | BYOK. First one set wins (Anthropic preferred). |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Override Anthropic model |
| `OPENAI_MODEL` | `gpt-4o-mini` | Override OpenAI model |
| `SUPPORT_LLM_URL` | `http://localhost:8001` | Where `support_kb_lookup` calls the FAISS brain |

## Design notes

- **No database.** Customer state (onboarding milestones, lesson progress) is stubbed in the agent files so demos are deterministic without infra. Plug in a real backend when you hand it to a client.
- **No monitoring, no Celery, no Kafka, no Redis.** Deliberate. This is a starter, not a platform.
- **LangChain ReAct** with `max_iterations=4` and `handle_parsing_errors=True` so agents fail gracefully instead of looping.
- **Tools are pure functions** in `agent.py` — easy to swap for real implementations without touching the FastAPI layer.
- **Persona is data, not code.** Edit `soul.md` / `skill.md` to re-tune Aria or Theo without touching Python.
