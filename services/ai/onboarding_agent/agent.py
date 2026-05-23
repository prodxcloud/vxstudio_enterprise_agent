"""
Onboarding Agent — Aria.

LangChain ReAct agent that walks newly-signed customers through their first
30 days. Reads soul.md + skill.md from this folder at construction time so
operators can re-tune the persona without touching Python.

BYOK: picks the first available provider in this order: Anthropic, OpenAI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool


HERE = Path(__file__).resolve().parent
KB_LLM_URL = os.getenv("KB_LLM_URL", "http://localhost:8001/v1")
KB_LLM_MODEL = os.getenv("KB_LLM_MODEL", "vxstudio-enterprise-slm")


# ── tools ──────────────────────────────────────────────────────────────────

def _support_kb_lookup(query: str) -> str:
    """Hit the SLM brain's OpenAI-compatible /v1/chat/completions and return the answer.

    The KB server (vxstudio_enterprise_llm) follows the OpenAI Chat Completions
    convention, so this same code path works against any OpenAI-compatible
    backend (vLLM, Ollama, LM Studio, TGI) by changing KB_LLM_URL.

    Falls back to a helpful 'KB unreachable' message rather than raising so the
    agent can recover and tell the user honestly.
    """
    try:
        r = httpx.post(
            f"{KB_LLM_URL}/chat/completions",
            json={
                "model": KB_LLM_MODEL,
                "messages": [{"role": "user", "content": query}],
                "temperature": 0.2,
                "max_tokens": 400,
            },
            timeout=15.0,
        )
        if r.status_code != 200:
            return f"KB returned {r.status_code}. Try again or escalate."
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        return f"KB unreachable ({e.__class__.__name__}). Tell the user honestly and offer to escalate."
    except (KeyError, IndexError, TypeError) as e:
        return f"KB returned malformed response ({e}). Try again or escalate."


def _checklist_state(customer_id: str) -> str:
    """Stub for the onboarding-milestone state lookup.

    In a real deployment this would call the customer-success backend. In the
    template we return a deterministic fixture so demos are reproducible without
    any DB connection.
    """
    return (
        "Customer onboarding milestones:\n"
        "  [x] account_verified\n"
        "  [x] workspace_created\n"
        "  [ ] first_teammate_invited\n"
        "  [ ] first_integration_connected\n"
        "  [ ] 14_day_checkin_scheduled\n"
        "Next recommended action: invite first teammate."
    )


def _escalate(payload: str) -> str:
    """Stub for the human-handoff queue. Accepts 'reason | contact_role'."""
    parts = [p.strip() for p in payload.split("|", 1)]
    reason = parts[0] if parts else payload
    role = parts[1] if len(parts) > 1 else "support"
    return f"Escalation queued: role={role}, reason={reason}. A human will reach out within 1 business hour."


TOOLS = [
    Tool(
        name="support_kb_lookup",
        func=_support_kb_lookup,
        description="Search the customer-service knowledge base. Input: a natural-language question. Output: an answer drawn from the company's KB.",
    ),
    Tool(
        name="checklist_state",
        func=_checklist_state,
        description="Get the current onboarding milestone state for a customer. Input: customer_id (string). Output: which milestones are complete and which is next.",
    ),
    Tool(
        name="escalate",
        func=_escalate,
        description="Hand the conversation to a human. Input must be 'reason | contact_role' (role is one of billing, sales, legal, engineering, support).",
    ),
]


# ── prompt assembly ────────────────────────────────────────────────────────

REACT_TEMPLATE = """{persona}

You have access to the following tools:

{tools}

Use the following format:

Question: the input question or message from the customer
Thought: think about what to do next
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (Thought/Action/Action Input/Observation can repeat 0 or more times)
Thought: I now know the final answer
Final Answer: the response to send back to the customer

Question: {input}
Thought:{agent_scratchpad}"""


def _load_persona() -> str:
    soul = (HERE / "soul.md").read_text(encoding="utf-8")
    skill = (HERE / "skill.md").read_text(encoding="utf-8")
    return f"You are an AI agent governed by the following persona and skill spec.\n\n--- SOUL ---\n{soul}\n\n--- SKILLS ---\n{skill}"


# ── LLM provider selection (BYOK) ──────────────────────────────────────────

def _pick_llm():
    """Return the first available provider — Anthropic, then OpenAI.

    Raises RuntimeError with a clear message if neither key is set so the
    /chat endpoint can surface it to the caller.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            temperature=0.2,
        )
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
        )
    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
    )


# ── public API ─────────────────────────────────────────────────────────────

@dataclass
class OnboardingAgent:
    executor: AgentExecutor
    persona: str

    def run(self, message: str) -> str:
        result = self.executor.invoke({"input": message})
        return result.get("output", "")


def build_onboarding_agent() -> OnboardingAgent:
    persona = _load_persona()
    llm = _pick_llm()
    prompt = PromptTemplate.from_template(REACT_TEMPLATE).partial(persona=persona)
    agent = create_react_agent(llm, TOOLS, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=4,
    )
    return OnboardingAgent(executor=executor, persona=persona)
