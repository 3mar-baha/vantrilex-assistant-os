"""One-time Telegram userbot login (v1.1 live-call prerequisite).

Prints the session string PyTgCalls needs — run ONCE on the owner's PC:
    .venv\\Scripts\\python -m src.telegram_login
The string lands in .env as TELEGRAM_USER_SESSION_STRING (never committed).
Uses Telethon (the PyTgCalls engine's own session format). Interactive by
design — this module is NEVER imported by the bot (docs/OWNER_ACTION_REQUIRED.md §1).
"""

from __future__ import annotations


def main() -> int:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("telethon is not installed yet — it arrives with the v1.1")
        print("calling sprint (pytgcalls dependency). Install preview:")
        print("  .venv\\Scripts\\pip install telethon")
        return 1

    api_id = input("TELEGRAM_API_ID (from my.telegram.org): ").strip()
    api_hash = input("TELEGRAM_API_HASH: ").strip()
    client = TelegramClient(StringSession(), api_id, api_hash)
    client.start()  # asks phone + the code Telegram sends your app
    print("\nSESSION STRING (paste into .env as TELEGRAM_USER_SESSION_STRING):\n")
    print(client.session.save())
    print("\nKeep it secret — it IS your logged-in account. Never commit it.")
    client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
