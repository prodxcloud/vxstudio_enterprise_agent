---
description: Show the last N lines of server.out.log and server.err.log from the running agent server
argument-hint: "[lines]"
---

Show recent output from the vxstudio_enterprise_agent server.

Use `$ARGUMENTS` as the number of lines if provided, otherwise default to **50**.

Steps:
1. Read the last N lines of `server.out.log` (skip if missing).
2. Read the last N lines of `server.err.log` (skip if missing).
3. Print each under a clear header. If `server.err.log` contains stack traces or `ERROR`/`CRITICAL` lines, call them out at the top in 1–2 sentences.
4. If both files are missing, tell the user the server has never been started here — suggest `/run`.

Do not truncate stack traces. Do not modify or delete the log files.
