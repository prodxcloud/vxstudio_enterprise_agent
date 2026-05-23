"""
Training Agent — Theo.

LangChain ReAct agent that runs structured learning sessions for customers
who have finished onboarding. Same shape as the onboarding agent (same
persona/skill loading, same BYOK provider pick, same tool wiring to the
support KB on port 8001) — different tools and different soul.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool


HERE = Path(__file__).resolve().parent
SUPPORT_LLM_URL = os.getenv("SUPPORT_LLM_URL", "http://localhost:8001")


# ── tools ──────────────────────────────────────────────────────────────────

def _support_kb_lookup(query: str) -> str:
    try:
        r = httpx.post(
            f"{SUPPORT_LLM_URL}/v1/support/query",
            json={"query": query, "top_k": 3},
            timeout=10.0,
        )
        if r.status_code != 200:
            return f"Support KB returned {r.status_code}. Try again or escalate."
        data = r.json()
        return data.get("answer") or data.get("response") or str(data)
    except httpx.HTTPError as e:
        return f"Support KB unreachable ({e.__class__.__name__}). Tell the user honestly and offer to escalate."


def _lesson_plan(payload: str) -> str:
    """Return a 3-step lesson outline for a topic at a given level.

    Input format: 'topic | level' where level is one of beginner|intermediate|advanced.
    Stub returns a deterministic outline so demos work without a curriculum DB.
    """
    parts = [p.strip() for p in payload.split("|", 1)]
    topic = parts[0] if parts else payload
    level = parts[1].lower() if len(parts) > 1 else "beginner"

    if level == "advanced":
        return (
            f"Lesson plan — {topic} (advanced):\n"
            f"  1. Diagnose: which specific edge case is the user trying to handle?\n"
            f"  2. Demo: a worked example using the lower-level API directly.\n"
            f"  3. Practice: have them write a similar example and run it."
        )
    if level == "intermediate":
        return (
            f"Lesson plan — {topic} (intermediate):\n"
            f"  1. Diagnose: confirm the user can do the basic flow first.\n"
            f"  2. Demo: show the common variation (one parameter changed).\n"
            f"  3. Practice: small task that combines the basic flow + the variation."
        )
    return (
        f"Lesson plan — {topic} (beginner):\n"
        f"  1. Diagnose: what does the user expect this feature to do?\n"
        f"  2. Demo: walk through the happy path step by step.\n"
        f"  3. Practice: simplest possible task that uses the feature once."
    )


def _escalate(payload: str) -> str:
    parts = [p.strip() for p in payload.split("|", 1)]
    reason = parts[0] if parts else payload
    role = parts[1] if len(parts) > 1 else "support"
    return f"Escalation queued: role={role}, reason={reason}. A human will reach out within 1 business hour."


TOOLS = [
    Tool(
        name="support_kb_lookup",
        func=_support_kb_lookup,
        description="Look up authoritative answers in the customer-service KB. Input: a natural-language question or exact error message.",
    ),
    Tool(
        name="lesson_plan",
        func=_lesson_plan,
        description="Build a 3-step lesson outline. Input must be 'topic | level' where level is beginner|intermediate|advanced.",
    ),
    Tool(
        name="escalate",
        func=_escalate,
        description="Hand off to a human. Input must be 'reason | contact_role' (role is one of sales, engineering, support).",
    ),
]


# ── prompt + provider selection (mirrors onboarding_agent) ─────────────────

REACT_TEMPLATE = """{persona}

You have access to the following tools:

{tools}

Use the following format:

Question: the input message from the customer
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


def _pick_llm():
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


@dataclass
class TrainingAgent:
    executor: AgentExecutor
    persona: str

    def run(self, message: str) -> str:
        result = self.executor.invoke({"input": message})
        return result.get("output", "")


def build_training_agent() -> TrainingAgent:
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
    return TrainingAgent(executor=executor, persona=persona)
