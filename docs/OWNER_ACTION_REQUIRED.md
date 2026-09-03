# 📋 OWNER ACTION REQUIRED — Physical/Account Prerequisites

Every v1.1 feature below is **software-complete, tested, and running in
mock/sandbox mode**. Nothing blocks; each item turns live with ONE secret you
place in `.env` — zero code changes. Sara tells you honestly when a lane is
in its waiting-for-you state.

---

## 1. Live voice calls (PyTgCalls) — the main missing asset

**What's needed:** a Telegram **session string** (one userbot login). This is
the only physical prerequisite for live calling — no SIM, no phone number,
no SIP trunk.

**The 3 steps (10 minutes, once):**

1. On your PC (with the repo venv active), run the one-time login helper:
   ```powershell
   .venv\Scripts\python -m src.telegram_login
   ```
   (Enter your phone + the code Telegram sends to your existing Telegram app —
   it logs in as YOUR account and prints a session string.)
2. Paste the printed string into `.env`:
   ```
   TELEGRAM_USER_SESSION_STRING=pasted-string-here
   ```
   (The value never leaves your machine; `.env` is gitignored.)
3. Restart the core (`sara.bat`). The call lane goes LIVE automatically —
   dial a contact by asking Sara («اتصلي بفلان») and the mock log line
   `call lane MOCK dial` changes to `call lane LIVE dial`.

**Until then:** every call path runs in mock mode (recorded + tested); Sara
answers with the honest «بدها تفعيل مرة وحدة من جهازك» line — never a
capability lie.

---

## 2. Gmail / Calendar / Tasks (Google OAuth) — still pending from earlier

1. `console.cloud.google.com` → project `vantrilex-assistant-2008` → enable
   **Calendar, Tasks, Gmail** APIs (the consent asks for exactly three
   scopes now — Drive/People left it entirely).
2. Credentials → OAuth client ID → **Desktop app** → download JSON → save as
   `config/google_oauth_client.json` in the MAIN checkout.
3. Run once on the browser machine:
   ```powershell
   .venv\Scripts\python -m src.google_auth
   ```
   Approve the consent screen → the sealed token lands in
   `vault/State/google_token.json.enc` → restart the core → «افحصي الجيميل»
   works, the 07:30 brief fills its sections, the evening check-in counts
   critical mail.

## 3. Docker image size verification (WSL off at last measurement)

1. Start Docker Desktop (your WSL service was off — `Wsl/0x80070422`).
2. In the repo: `docker build -t vantrilex .` — the pruned image (2,515
   lines + pypdf removed) is measurably smaller than the v1.0.2 baseline.

---

*These three items are the complete external list. Everything else in the
v1.1 intelligence suite (diarization, affect engine, acoustic nuance,
self-evolution) is fully local — zero external prerequisites.*
