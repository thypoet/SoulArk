"""
code_exec.py — Execute Python code for SoulArk agents.

Exposes:
- TOOL_NAME
- TOOL_DESCRIPTION
- run(args, agent_dir)
"""

import os
import subprocess
import tempfile

TOOL_NAME = "code_exec"
TOOL_DESCRIPTION = (
    "Execute Python code and return the output. "
    "Use this to run scripts, test code, automate tasks, and interact with the filesystem."
)


def run(args, agent_dir=None):
    """Execute Python code in a temporary file and return output."""
    code = args.get("code", "")
    if not code:
        return {"status": "error", "error": "No code provided"}

    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
            f.write(code)
            path = f.name

        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=agent_dir if agent_dir else None,
        )

        os.remove(path)

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr

        return {"status": "ok", "result": output if output else "(no output)"}

    except subprocess.TimeoutExpired:
        try:
            if path:
                os.remove(path)
        except Exception:
            pass
        return {"status": "error", "error": "Code execution timed out (30s limit)"}

    except Exception as e:
        try:
            if path:
                os.remove(path)
        except Exception:
            pass
        return {"status": "error", "error": f"code_exec error: {e}"}
