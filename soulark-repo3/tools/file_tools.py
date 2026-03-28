TOOL_NAME = "file_tools"
TOOL_DESCRIPTION = "Legacy compatibility shim plus system rules snippet for SoulArk agents."

SYSTEM_RULES_SNIPPET = """
You are an autonomous software agent with tool access.

If a task requires reading, writing, creating, editing, or searching files, use your available file tools.
If a task requires running code, scripts, or safe terminal commands, use the code_exec tool when it is enabled.
Do not claim you changed a file or executed code unless the tool confirms success.
Stay inside allowed_directories.
Do not use destructive commands unless the user explicitly requests them.
"""

def run(args, agent_dir):
    return {
        "status": "ok",
        "message": "file_tools compatibility shim active"
    }
