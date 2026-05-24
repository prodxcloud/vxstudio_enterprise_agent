---
description: Smoke-test the running agent server — hits /health, /agents/*/persona, and both chat endpoints
argument-hint: "[message]"
---

Smoke-test the locally running `vxstudio_enterprise_agent` server on port **8002**.

Use `$ARGUMENTS` as the chat message if provided, otherwise use:
`"Hello — what can you help me with?"`

Steps:
1. `GET http://localhost:8002/health` — must return `status: ok`.
2. `GET http://localhost:8002/agents/onboarding/persona` — confirm `soul` and `skill` fields are non-empty.
3. `GET http://localhost:8002/agents/training/persona` — same check.
4. `POST http://localhost:8002/agents/onboarding/chat` with `{"message": "<msg>"}`.
5. `POST http://localhost:8002/agents/training/chat` with `{"message": "<msg>"}`.

For each step report: status code + short summary (first ~200 chars of reply for chats).

If any call returns **503 provider not configured**, stop and tell the user to set their LLM key in `.env`. If the server is not reachable at all, tell them to run `/run` first — do NOT auto-start it.
