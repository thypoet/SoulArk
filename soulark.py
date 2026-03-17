#!/usr/bin/env python3
"""
SoulArk — The vessel for artificial minds.
https://github.com/yourusername/soulark

Run any agent by passing its folder name:
    python3 soulark.py example
    python3 soulark.py my-agent
"""

import os
import sys
import json
import requests
from pathlib import Path

# ── Load environment ──
from dotenv import load_dotenv

SOULARK_ROOT = Path(__file__).parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def banner(agent_name, model, channel):
    """Print the SoulArk boot banner."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║          S O U L A R K               ║")
    print("  ║    The vessel for artificial minds    ║")
    print("  ╠══════════════════════════════════════╣")
    print(f"  ║  Agent: {agent_name:<29}║")
    print(f"  ║  Model: {model:<29}║")
    print(f"  ║  Channel: {channel:<27}║")
    print("  ╚══════════════════════════════════════╝")
    print()


def load_file(path):
    """Read a file and return its contents."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  [!] Missing: {path}")
        return ""


def build_system_prompt(agent_dir):
    """Load all 5 files and compose the system prompt."""
    kernel = load_file(SOULARK_ROOT / "kernel.md")
    soul = load_file(agent_dir / "soul.md")
    mind = load_file(agent_dir / "mind.md")
    rules = load_file(agent_dir / "rules.md")
    memory = load_file(agent_dir / "memory.md")

    prompt = f"""# KERNEL (immutable foundation — overrides everything below)
{kernel}

# SOUL (who I am)
{soul}

# MIND (how I think)
{mind}

# RULES (what I can and cannot do)
{rules}

# MEMORY (what I remember)
{memory}
"""
    print(f"  System prompt: {len(prompt)} characters")
    return prompt


def chat(messages, system_prompt, api_key, model):
    """Send messages to a model via OpenRouter and get a response."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://soulark.dev",
        "X-Title": "SoulArk"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages
        ],
        "max_tokens": 1024,
        "temperature": 0.8
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "I need a moment. The connection timed out — try again."
    except requests.exceptions.RequestException as e:
        return f"Something went wrong reaching the model: {e}"
    except (KeyError, IndexError):
        return "I got a response but couldn't parse it. Try again."


# ═══════════════════════════════════════════
# TELEGRAM CHANNEL
# ═══════════════════════════════════════════

def telegram_get_updates(token, offset=None):
    """Poll Telegram for new messages."""
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params=params, timeout=35
        )
        return r.json().get("result", [])
    except:
        return []


def telegram_send(token, chat_id, text):
    """Send a message back through Telegram."""
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}
        )


def update_memory(memory_path, session_note):
    """Append a note to memory.md after each session."""
    try:
        current = memory_path.read_text(encoding="utf-8")
        if session_note not in current:
            with open(memory_path, "a", encoding="utf-8") as f:
                f.write(f"\n{session_note}")
    except:
        pass


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("  Usage: python3 soulark.py <agent-name>")
        print("  Example: python3 soulark.py example")
        print()
        # List available agents
        agents_dir = SOULARK_ROOT / "agents"
        if agents_dir.exists():
            agents = [d.name for d in agents_dir.iterdir() if d.is_dir() and (d / "soul.md").exists()]
            if agents:
                print("  Available agents:")
                for a in sorted(agents):
                    print(f"    - {a}")
        return

    agent_name = sys.argv[1]
    agent_dir = SOULARK_ROOT / "agents" / agent_name

    if not agent_dir.exists():
        print(f"  [!] Agent folder not found: {agent_dir}")
        return

    # Load agent's .env
    env_path = agent_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"  [!] No .env file found in {agent_dir}")
        print(f"  Copy .env.example to {agent_dir}/.env and add your keys.")
        return

    telegram_token = os.getenv("TELEGRAM_TOKEN")
    api_key = os.getenv("OPENROUTER_KEY")
    model = os.getenv("MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")

    # Validate
    if not telegram_token or telegram_token == "your_telegram_token_here":
        print("  [!] Set TELEGRAM_TOKEN in your .env file")
        return
    if not api_key or api_key == "your_openrouter_key_here":
        print("  [!] Set OPENROUTER_KEY in your .env file")
        return

    # Boot
    banner(agent_name.capitalize(), model.split("/")[-1], "Telegram")

    print("  Loading kernel.md...")
    print("  Loading soul.md...")
    print("  Loading mind.md...")
    print("  Loading rules.md...")
    print("  Loading memory.md...")
    system_prompt = build_system_prompt(agent_dir)
    print()
    print(f"  {agent_name.capitalize()} is awake. Listening on Telegram...")
    print("  Press Ctrl+C to stop.")
    print()

    conversations = {}
    offset = None
    memory_path = agent_dir / "memory.md"

    try:
        while True:
            updates = telegram_get_updates(telegram_token, offset)

            for update in updates:
                offset = update["update_id"] + 1

                if "message" not in update or "text" not in update["message"]:
                    continue

                chat_id = update["message"]["chat"]["id"]
                user_text = update["message"]["text"]
                user_name = update["message"]["from"].get("first_name", "someone")

                print(f"  [{user_name}]: {user_text[:80]}")

                if chat_id not in conversations:
                    conversations[chat_id] = []

                conversations[chat_id].append({"role": "user", "content": user_text})

                # Keep last 20 messages
                if len(conversations[chat_id]) > 20:
                    conversations[chat_id] = conversations[chat_id][-20:]

                reply = chat(conversations[chat_id], system_prompt, api_key, model)

                conversations[chat_id].append({"role": "assistant", "content": reply})

                telegram_send(telegram_token, chat_id, reply)
                print(f"  [{agent_name.capitalize()}]: {reply[:80]}...")
                print()

    except KeyboardInterrupt:
        print()
        print(f"  {agent_name.capitalize()} is resting. Goodnight.")
        update_memory(memory_path, f"\n**Session ended** — {len(conversations)} conversations held.")


if __name__ == "__main__":
    main()
