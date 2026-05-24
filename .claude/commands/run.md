---
description: Start the vxstudio_enterprise_agent FastAPI server (uvicorn on port 8002) in the background
argument-hint: "[port]"
---

Start the FastAPI app from `app.py` using uvicorn, in the background, so the chat keeps flowing.

Steps:
1. If `$ARGUMENTS` is non-empty, use it as the port; otherwise default to **8002**.
2. Check if anything is already listening on that port. If yes, report the PID and stop — do NOT kill it without asking the user.
3. Activate the local `venv` if present (`venv\Scripts\activate` on Windows, `venv/bin/activate` otherwise).
4. Launch:
   ```
   python -m uvicorn app:app --host 0.0.0.0 --port <port> --log-level info
   ```
   Run it with `run_in_background: true` and redirect stdout → `server.out.log`, stderr → `server.err.log`.
5. Wait briefly, then `curl http://localhost:<port>/health` once to confirm it booted.
6. Report: PID, port, and the `/health` JSON. If `provider_configured` is `false`, remind the user to set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`.

Do not run any tests, do not commit anything — just boot the server.
