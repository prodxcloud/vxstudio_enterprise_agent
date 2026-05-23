"""
vxstudio_enterprise_agent — FastAPI entrypoint.

A minimal enterprise customer-experience agent service: two LangChain ReAct
agents (Customer Onboarding + Customer Training) served behind a FastAPI app
on port 8002. Pairs with vxstudio_enterprise_llm on port 8001, which provides
the FAISS-backed support knowledge base both agents consult.

No database. No monitoring stack. No background workers. Just app.py + the
two agents. BYOK for the LLM provider (Anthropic or OpenAI).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env from this folder before importing agents, so api keys are visible.
load_dotenv(Path(__file__).resolve().parent / ".env")

from services.ai.onboarding_agent import build_onboarding_agent  # noqa: E402
from services.ai.training_agent import build_training_agent      # noqa: E402


KB_LLM_URL = os.getenv("KB_LLM_URL", "http://localhost:8001/v1")

app = FastAPI(
    title="vxstudio_enterprise_agent",
    description="Enterprise customer-experience agents (Onboarding + Training) — LangChain over vxstudio_enterprise_llm.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Lazy-build agents on first request so the server boots even when no LLM
# provider key is set (useful for /health checks in CI).
_agents: dict = {}


def _get_agent(name: str):
    if name in _agents:
        return _agents[name]
    if name == "onboarding":
        _agents[name] = build_onboarding_agent()
    elif name == "training":
        _agents[name] = build_training_agent()
    else:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}")
    return _agents[name]


# ── schemas ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    agent: str
    reply: str


class HealthResponse(BaseModel):
    status: str
    agents: list[str]
    kb_llm_url: str
    provider_configured: bool


# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        agents=["onboarding", "training"],
        kb_llm_url=KB_LLM_URL,
        provider_configured=bool(
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        ),
    )


@app.get("/agents/{name}/persona")
def get_persona(name: str) -> dict:
    """Return the soul.md + skill.md the agent loads — readable without an LLM key."""
    folder = {
        "onboarding": "onboarding_agent",
        "training": "training_agent",
    }.get(name)
    if folder is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}")
    base = Path(__file__).resolve().parent / "services" / "ai" / folder
    return {
        "agent": name,
        "soul": (base / "soul.md").read_text(encoding="utf-8"),
        "skill": (base / "skill.md").read_text(encoding="utf-8"),
    }


@app.post("/agents/onboarding/chat", response_model=ChatResponse)
def chat_onboarding(req: ChatRequest) -> ChatResponse:
    try:
        agent = _get_agent("onboarding")
        reply = agent.run(req.message)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return ChatResponse(agent="onboarding", reply=reply)


@app.post("/agents/training/chat", response_model=ChatResponse)
def chat_training(req: ChatRequest) -> ChatResponse:
    try:
        agent = _get_agent("training")
        reply = agent.run(req.message)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return ChatResponse(agent="training", reply=reply)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
