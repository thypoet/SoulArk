import importlib.util
from pathlib import Path

def parse_rules(rules_text):
    enabled = {}
    allowed_dirs = []

    if not rules_text:
        return enabled, allowed_dirs

    for line in rules_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().lower()

        if key == "allowed_directories":
            allowed_dirs = [p.strip() for p in value.split(",") if p.strip()]
        else:
            enabled[key] = value == "enabled"

    return enabled, allowed_dirs


def _load_module(file_path):
    spec = importlib.util.spec_from_file_location(file_path.stem, str(file_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tools(tools_dir):
    # handle if caller accidentally passed a dict
    if isinstance(tools_dir, dict):
        if "tools_dir" in tools_dir:
            tools_dir = tools_dir["tools_dir"]
        else:
            return {}, {"error": "tools_dir passed as dict"}

    tools_dir = Path(tools_dir)

    loaded = {}
    errors = {}

    if not tools_dir.exists():
        return loaded, {"error": f"Tools directory not found: {tools_dir}"}

    for file_path in tools_dir.glob("*.py"):
        if file_path.name == "tool_loader.py":
            continue

        try:
            module = _load_module(file_path)
            name = getattr(module, "TOOL_NAME", file_path.stem)
            desc = getattr(module, "TOOL_DESCRIPTION", "")
            run = getattr(module, "run", None)

            if callable(run):
                loaded[name] = {
                    "name": name,
                    "description": desc,
                    "run": run
                }
            else:
                errors[file_path.name] = "Missing run()"

        except Exception as e:
            errors[file_path.name] = str(e)

    return loaded, errors


def get_agent_tools(rules_text):
    enabled, allowed_dirs = parse_rules(rules_text)

    return {
        "enabled": enabled,
        "allowed_directories": allowed_dirs
    }


def execute_tool(tool, args, agent_dir):
    return tool["run"](args, agent_dir)
import json
import os

def workspace_tool(action=None, path=None, pattern=None):
    try:
        if action == "list_dir":
            target = path or "."
            return {"ok": True, "result": os.listdir(target)}

        if action == "search_files":
            target = path or "."
            matches = []
            for root, _, files in os.walk(target):
                for name in files:
                    if pattern and pattern.lower() in name.lower():
                        matches.append(os.path.join(root, name))
            return {"ok": True, "result": matches}

        return {"ok": False, "error": f"unknown action: {action}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_tool_call(raw_message):
    try:
        text = raw_message if isinstance(raw_message, str) else str(raw_message)
        text = text.strip()

        if text.startswith("<tool_call>") and text.endswith("</tool_call>"):
            text = text[len("<tool_call>"): -len("</tool_call>")].strip()

        data = json.loads(text)

        if data.get("name") != "workspace_tool":
            return None

        args = data.get("arguments", {})
        return workspace_tool(
            action=args.get("action"),
            path=args.get("path"),
            pattern=args.get("pattern"),
        )
    except Exception as e:
        return {"ok": False, "error": f"tool parse failed: {e}"}
