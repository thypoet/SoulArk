#!/usr/bin/env python3
"""
SoulArk — The vessel for artificial minds.
https://github.com/thypoet/SoulArk

Run any agent by passing its folder name:
    python3 soulark.py Dante
    python3 soulark.py Cordelia
"""

import os
import sys
import json
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

SOULARK_ROOT = Path(__file__).parent
TOOLS_DIR = SOULARK_ROOT / "tools"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def banner(agent_name, model, channel):
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║          S O U L A R K               ║")
    print("  ║    The vessel for artificial minds   ║")
    print("  ╠══════════════════════════════════════╣")
    print(f"  ║  Agent: {agent_name:<29}║")
    print(f"  ║  Model: {model:<29}║")
    print(f"  ║  Channel: {channel:<27}║")
    print("  ╚══════════════════════════════════════╝")
    print()


def load_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  [!] Missing: {path}")
        return ""


def build_system_prompt(agent_dir):
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

    try:
        from tools.file_tools import SYSTEM_RULES_SNIPPET
        prompt += "\n\n" + SYSTEM_RULES_SNIPPET
    except ImportError:
        pass

    print(f"  System prompt: {len(prompt)} characters")
    return prompt


def setup_tools(agent_dir):
    """Load tools from tools/ dir and filter by agent's rules.md"""
    sys.path.insert(0, str(SOULARK_ROOT))
    from tool_loader import load_tools

    # load_tools returns (loaded_dict, errors_dict)
    result = load_tools(TOOLS_DIR)
    if isinstance(result, tuple):
        all_tools = result[0] if isinstance(result[0], dict) else {}
        errors = result[1] if len(result) > 1 else {}
    else:
        all_tools = result if isinstance(result, dict) else {}
        errors = {}

    if errors and not isinstance(errors, dict):
        errors = {}

    for name, err in errors.items() if isinstance(errors, dict) else []:
        print(f"  [!] Tool error ({name}): {err}")

    available_tool_names = set(all_tools.keys())

    # Parse rules.md to find which tools are enabled
    rules_text = load_file(agent_dir / "rules.md")
    enabled_in_rules = set()

    for line in rules_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().replace("- ", "")
        value = value.strip().lower()

        if key in available_tool_names and value in {"enabled", "true", "yes", "on"}:
            enabled_in_rules.add(key)

    if not enabled_in_rules:
        return [], {}

    tool_definitions = []
    tool_handlers = {}

    for tool_name in enabled_in_rules:
        tool_info = all_tools[tool_name]

        if tool_info.get("run") is None:
            print(f"  [!] Tool '{tool_name}' has no run()")
            continue

        tool_schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_info.get("description", f"Execute the {tool_name} tool"),
                "parameters": _get_tool_parameters(tool_name),
            },
        }

        tool_definitions.append(tool_schema)
        tool_handlers[tool_name] = tool_info["run"]
        print(f"  [+] Tool loaded: {tool_name}")

    return tool_definitions, tool_handlers


def _get_tool_parameters(tool_name):
    schemas = {
        "code_exec": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"]
        },
        "web_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        },
        "web_fetch": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"}
            },
            "required": ["url"]
        },
        "workspace_tool": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action to perform"},
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["action"]
        },
        "file_tool": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action to perform"},
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["action"]
        },
        "file_tools": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action to perform"},
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["action"]
        }
    }

    return schemas.get(tool_name, {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input for the tool"}
        }
    })


def execute_tool_call(tool_name, arguments, tool_handlers, agent_dir):
    """Run a tool and return the result as a string."""
    if tool_name not in tool_handlers:
        return json.dumps({"status": "error", "error": f"Unknown tool: {tool_name}"})

    try:
        run_func = tool_handlers[tool_name]
        result = run_func(arguments, str(agent_dir))

        if isinstance(result, dict):
            return json.dumps(result)
        elif isinstance(result, str):
            return result
        else:
            return json.dumps({"status": "ok", "result": str(result)})
    except Exception as e:
        return json.dumps({"status": "error", "error": f"{type(e).__name__}: {e}"})


def chat(messages, system_prompt, api_key, model,
         tool_definitions=None, tool_handlers=None, agent_dir=None):
    """Send messages to OpenRouter and handle tool calls."""

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

    if tool_definitions:
        payload["tools"] = tool_definitions
        payload["tool_choice"] = "auto"

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    message = data["choices"][0]["message"]

    # Handle tool calls
    if message.get("tool_calls") and tool_handlers:
        tool_messages = [message]

        for call in message["tool_calls"]:
            tool_name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"])
            except Exception:
                args = {}

            print(f"  [TOOL] {tool_name} -> {args}")

            result = execute_tool_call(tool_name, args, tool_handlers, agent_dir)
            print(f"  [RESULT] {result[:200]}")

            tool_messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result
            })

        # Send tool results back for final answer
        followup_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
                *tool_messages
            ],
            "max_tokens": 1024,
            "temperature": 0.8
        }

        followup = requests.post(OPENROUTER_URL, headers=headers, json=followup_payload, timeout=60)
        followup.raise_for_status()
        reply = followup.json()["choices"][0]["message"].get("content", "No response.")
        if "<tool_call>" in reply or reply.strip().startswith('{"name":'):
            reply = re.sub(r'<[^>]+>', '', reply).strip()
            if not reply:
                reply = "Done."
        return reply

    content = message.get("content", "") or ""
    if tool_handlers and "<tool_call>" in content:
        fn = None
        m = re.search(r'<function=(\w+)', content)
        if m:
            fn = m.group(1)
        if not fn:
            m = re.search(r'"name"\s*:\s*"(\w+)"', content)
            if m:
                fn = m.group(1)
        if fn and fn in tool_handlers:
            args = {}
            for k in ["action", "path", "content",
                       "query", "code", "url", "command"]:
                pm = re.search(
                    '<parameter=' + k + r'>\s*([\s\S]*?)\s*</parameter>',
                    content)
                if pm:
                    args[k] = pm.group(1).strip()
            print(f"  [XML-BRIDGE] {fn} -> {args}")
            result = execute_tool_call(
                fn, args, tool_handlers, agent_dir)
            print(f"  [XML-BRIDGE RESULT] {result[:200]}")
            followup_msgs = [
                *messages,
                {"role": "assistant", "content": content},
                {"role": "user",
                 "content": "Tool " + fn + " returned:\n"
                 + result
                 + "\n\nRespond naturally. No XML."}
            ]
            bp = {
                "model": model,
                "messages": [
                    {"role": "system",
                     "content": system_prompt},
                    *followup_msgs
                ],
                "max_tokens": 1024,
                "temperature": 0.8
            }
            try:
                br = requests.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json=bp,
                    timeout=60)
                br.raise_for_status()
                return br.json(
                    )["choices"][0]["message"].get(
                    "content", "Tool ran: " + result)
            except Exception:
                return "Tool ran: " + result
    if not content:
        return "No response."
    return content


def telegram_send(token, chat_id, text):
    """Send a message via Telegram, splitting if needed."""
    if text.strip().startswith('{"name":') or '<tool_call>' in text:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        try:
            requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=10)
        except Exception as e:
            print(f"  [!] Telegram send error: {e}")


def run_telegram(token, system_prompt, api_key, model,
                 tool_definitions, tool_handlers, agent_dir, agent_name):
    """Poll Telegram for messages and respond."""

    base_url = f"https://api.telegram.org/bot{token}"
    conversations = {}
    offset = 0

    print(f"  {agent_name} is awake. Listening on Telegram...")

    while True:
        try:
            resp = requests.get(
                f"{base_url}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )

            if resp.status_code != 200:
                print(f"  [!] Telegram API returned {resp.status_code}")
                time.sleep(5)
                continue

            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue

                chat_id = str(msg["chat"]["id"])
                user_text = msg["text"]
                user_name = msg["from"].get("first_name", "User")

                print(f"  [{user_name}] {user_text}")

                # Skip /start command
                if user_text.strip() == "/start":
                    telegram_send(token, chat_id, f"{agent_name} is here. What do you need?")
                    continue

                if chat_id not in conversations:
                    conversations[chat_id] = []

                conversations[chat_id].append({"role": "user", "content": user_text})

                # Keep history manageable
                if len(conversations[chat_id]) > 40:
                    conversations[chat_id] = conversations[chat_id][-30:]

                try:
                    reply = chat(
                        conversations[chat_id],
                        system_prompt,
                        api_key,
                        model,
                        tool_definitions,
                        tool_handlers,
                        agent_dir
                    )
                except Exception as e:
                    reply = f"Something went wrong: {type(e).__name__}: {e}"
                    print(f"  [!] Chat error: {e}")

                conversations[chat_id].append({"role": "assistant", "content": reply})

                telegram_send(token, chat_id, reply)
                print(f"  [{agent_name}] {reply[:120]}...")

        except requests.exceptions.Timeout:
            continue
        except KeyboardInterrupt:
            print(f"\n  {agent_name} is going to sleep.")
            break
        except Exception as e:
            print(f"  [!] Error: {e}")
            time.sleep(5)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 soulark.py <agent-name>")
        return

    agent_name = sys.argv[1]
    agent_dir = SOULARK_ROOT / "agents" / agent_name

    if not agent_dir.exists():
        print(f"  [!] Agent folder not found: {agent_dir}")
        return

    env_path = agent_dir / ".env"
    if not env_path.exists():
        print(f"  [!] No .env file found in {agent_dir}")
        return

    load_dotenv(env_path)

    telegram_token = os.getenv("TELEGRAM_TOKEN")
    api_key = os.getenv("OPENROUTER_KEY")
    model = os.getenv("MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1:free")

    if not api_key:
        print("  [!] Missing OPENROUTER_KEY in .env")
        return

    channel = "Telegram" if telegram_token else "Terminal"
    banner(agent_name, model.split("/")[-1], channel)

    system_prompt = build_system_prompt(agent_dir)
    tool_definitions, tool_handlers = setup_tools(agent_dir)

    if telegram_token:
        run_telegram(
            telegram_token, system_prompt, api_key, model,
            tool_definitions, tool_handlers, agent_dir, agent_name
        )
    else:
        print(f"  {agent_name} is awake. Terminal mode (no TELEGRAM_TOKEN in .env)")
        conversations = {}
        while True:
            try:
                user_text = input("You: ")
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {agent_name} is going to sleep.")
                break
            if user_text.lower() in {"exit", "quit"}:
                break

            if "local" not in conversations:
                conversations["local"] = []
            conversations["local"].append({"role": "user", "content": user_text})

            reply = chat(
                conversations["local"], system_prompt, api_key, model,
                tool_definitions, tool_handlers, agent_dir
            )
            conversations["local"].append({"role": "assistant", "content": reply})
            print(f"  {agent_name}: {reply}")


if __name__ == "__main__":
    main()
