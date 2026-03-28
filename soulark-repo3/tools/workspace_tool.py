import difflib
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = "workspace_tool"
TOOL_DESCRIPTION = (
    "Open, create, edit, rename, delete, and search files inside approved "
    "directories. Returns verification data including absolute path, hashes, "
    "bytes written, timestamps, and diff previews so agents can prove changes."
)

BLOCKED_PATH_TERMS = ["cinder", "patent"]
DEFAULT_ENCODING = "utf-8"
MAX_READ_CHARS = 200000
MAX_DIFF_LINES = 200
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".csv", ".html", ".css", ".scss", ".xml", ".swift",
    ".java", ".kt", ".rb", ".go", ".rs", ".sh", ".zsh", ".bash", ".env", ".gitignore",
    ".sql", ".graphql", ".proto", ".dart", ".c", ".cpp", ".h", ".hpp"
}


class WorkspaceToolError(Exception):
    pass


# ----------------------------
# Rules parsing / access model
# ----------------------------

def parse_rules_content(rules_content: str) -> Dict[str, Any]:
    """
    Supports flexible keys so you don't have to perfectly refactor your platform:
      workspace_tool: enabled
      document_tool: enabled
      file_tool: enabled
      allowed_directories: /path/one, /path/two

    If none of the explicit tool flags are present but allowed_directories exists,
    the tool assumes access is enabled.
    """
    enabled  = True

    for key in ("workspace_tool", "document_tool", "file_tool"):
        m = re.search(rf"{re.escape(key)}\s*:\s*(enabled|disabled)", rules_content, re.IGNORECASE)
        if m:
            enabled = m.group(1).strip().lower() == "enabled"
            break

    dir_match = re.search(r"allowed_directories\s*:\s*(.+)", rules_content, re.IGNORECASE)
    scope: Any = "none"
    if dir_match:
        raw = dir_match.group(1).strip()
        if raw.lower() == "all":
            scope = "all"
        elif raw.lower() == "none":
            scope = "none"
        else:
            scope = [item.strip() for item in raw.split(",") if item.strip()]
            if scope and not re.search(r"(workspace_tool|document_tool|file_tool)\s*:\s*(enabled|disabled)", rules_content, re.IGNORECASE):
                enabled = True

    return {"enabled": enabled, "scope": scope}


def load_rules(agent_dir: str) -> Dict[str, Any]:
    rules_path = Path(agent_dir) / "rules.md"
    if not rules_path.exists():
        raise WorkspaceToolError(
            "rules.md not found for this agent. Add rules.md with allowed_directories and enable workspace_tool."
        )
    rules_content = rules_path.read_text(encoding=DEFAULT_ENCODING)
    config = parse_rules_content(rules_content)
    if not config["enabled"]:
        raise WorkspaceToolError(
            "workspace_tool is enabled for this agent. Add 'workspace_tool: enabled' to rules.md."
        )
    return config


# ----------------------------
# Path safety and verification
# ----------------------------

def contains_blocked_term(path_str: str) -> Optional[str]:
    lower = path_str.lower()
    for term in BLOCKED_PATH_TERMS:
        if term in lower:
            return term
    return None


def normalize_root(path_str: str) -> Path:
    return Path(os.path.expanduser(path_str)).resolve()


def ensure_allowed(path_str: str, scope: Any, agent_dir: str) -> Path:
    if contains_blocked_term(path_str):
        term = contains_blocked_term(path_str)
        raise WorkspaceToolError(
            f"KERNEL BLOCK: path contains blocked term '{term}'. This tool refuses access."
        )

    candidate = Path(os.path.expanduser(path_str))
    if not candidate.is_absolute():
        candidate = (Path(agent_dir) / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if scope == "all":
        return candidate
    if scope == "none":
        raise WorkspaceToolError(
            "SCOPE BLOCK: this agent has no directory access. Set allowed_directories in rules.md."
        )

    allowed_roots = [normalize_root(p) for p in scope]
    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue

    allowed = ", ".join(str(p) for p in allowed_roots)
    raise WorkspaceToolError(
        f"SCOPE BLOCK: '{candidate}' is outside allowed_directories. Permitted roots: {allowed}"
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode(DEFAULT_ENCODING)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        data = path.read_bytes()[:4096]
    except Exception:
        return False
    if b"\x00" in data:
        return False
    return True


def read_text_file(path: Path) -> str:
    if not path.exists():
        raise WorkspaceToolError(f"File not found: {path}")
    if not path.is_file():
        raise WorkspaceToolError(f"Not a file: {path}")
    if not is_probably_text(path):
        raise WorkspaceToolError(f"Binary or unsupported file type: {path}")
    text = path.read_text(encoding=DEFAULT_ENCODING)
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + "\n\n[truncated]"
    return text


def build_diff(before: str, after: str, path_label: str) -> str:
    diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"before:{path_label}",
            tofile=f"after:{path_label}",
            lineterm="",
        )
    )
    if not diff:
        return ""
    if len(diff) > MAX_DIFF_LINES:
        diff = diff[:MAX_DIFF_LINES] + ["...[diff truncated]..."]
    return "\n".join(diff)


def verification_payload(path: Path, before: Optional[str], after: Optional[str], existed_before: bool) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "absolute_path": str(path),
        "exists_now": path.exists(),
        "existed_before": existed_before,
        "timestamp_utc": now_iso(),
    }
    if path.exists():
        stat = path.stat()
        info["bytes_on_disk"] = stat.st_size
        info["modified_time_epoch"] = stat.st_mtime
    if before is not None:
        info["sha256_before"] = sha256_text(before)
    if after is not None:
        info["sha256_after"] = sha256_text(after)
        info["bytes_written"] = len(after.encode(DEFAULT_ENCODING))
    if before is not None and after is not None:
        info["changed"] = before != after
        info["diff_preview"] = build_diff(before, after, str(path))
    return info


# ----------------------------
# File operations
# ----------------------------

def create_file(path: Path, content: str = "") -> Dict[str, Any]:
    existed_before = path.exists()
    before = None
    if existed_before:
        raise WorkspaceToolError(f"Refusing to create because file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=DEFAULT_ENCODING)
    return {
        "status": "created",
        **verification_payload(path, before, content, existed_before),
    }


def write_file(path: Path, content: str) -> Dict[str, Any]:
    existed_before = path.exists()
    before = read_text_file(path) if existed_before else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=DEFAULT_ENCODING)
    return {
        "status": "written",
        **verification_payload(path, before, content, existed_before),
    }


def append_file(path: Path, content: str) -> Dict[str, Any]:
    existed_before = path.exists()
    before = read_text_file(path) if existed_before else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=DEFAULT_ENCODING) as f:
        f.write(content)
    after = read_text_file(path)
    return {
        "status": "appended",
        **verification_payload(path, before, after, existed_before),
    }


def replace_in_file(path: Path, old_text: str, new_text: str, count: Optional[int] = None) -> Dict[str, Any]:
    before = read_text_file(path)
    if old_text not in before:
        raise WorkspaceToolError("Target text not found; nothing replaced.")
    replacement_count = before.count(old_text) if count in (None, 0) else count
    after = before.replace(old_text, new_text, replacement_count)
    path.write_text(after, encoding=DEFAULT_ENCODING)
    return {
        "status": "replaced",
        "replacements_requested": replacement_count,
        **verification_payload(path, before, after, True),
    }


def insert_at_line(path: Path, line: int, content: str) -> Dict[str, Any]:
    if line < 1:
        raise WorkspaceToolError("line must be >= 1")
    before = read_text_file(path)
    lines = before.splitlines(keepends=True)
    insertion = content
    if insertion and not insertion.endswith("\n"):
        insertion += "\n"
    idx = min(line - 1, len(lines))
    lines.insert(idx, insertion)
    after = "".join(lines)
    path.write_text(after, encoding=DEFAULT_ENCODING)
    return {
        "status": "inserted",
        "line": line,
        **verification_payload(path, before, after, True),
    }


def delete_lines(path: Path, start_line: int, end_line: int) -> Dict[str, Any]:
    if start_line < 1 or end_line < start_line:
        raise WorkspaceToolError("Invalid line range.")
    before = read_text_file(path)
    lines = before.splitlines(keepends=True)
    start_idx = start_line - 1
    end_idx = min(end_line, len(lines))
    deleted = "".join(lines[start_idx:end_idx])
    after = "".join(lines[:start_idx] + lines[end_idx:])
    path.write_text(after, encoding=DEFAULT_ENCODING)
    return {
        "status": "deleted_lines",
        "start_line": start_line,
        "end_line": end_line,
        "deleted_preview": deleted[:2000],
        **verification_payload(path, before, after, True),
    }


def rename_path(old_path: Path, new_path: Path) -> Dict[str, Any]:
    if not old_path.exists():
        raise WorkspaceToolError(f"Source path does not exist: {old_path}")
    if new_path.exists():
        raise WorkspaceToolError(f"Destination already exists: {new_path}")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
    return {
        "status": "renamed",
        "old_absolute_path": str(old_path),
        "new_absolute_path": str(new_path),
        "timestamp_utc": now_iso(),
    }


def delete_path(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise WorkspaceToolError(f"Path does not exist: {path}")
    if path.is_dir():
        shutil.rmtree(path)
        kind = "directory"
    else:
        path.unlink()
        kind = "file"
    return {
        "status": "deleted",
        "deleted_type": kind,
        "absolute_path": str(path),
        "timestamp_utc": now_iso(),
    }


def mkdir(path: Path) -> Dict[str, Any]:
    path.mkdir(parents=True, exist_ok=True)
    return {
        "status": "directory_ready",
        "absolute_path": str(path),
        "timestamp_utc": now_iso(),
    }


def list_dir(path: Path, recursive: bool = False) -> Dict[str, Any]:
    if not path.exists():
        raise WorkspaceToolError(f"Directory does not exist: {path}")
    if not path.is_dir():
        raise WorkspaceToolError(f"Not a directory: {path}")
    items: List[Dict[str, Any]] = []
    iterator = path.rglob("*") if recursive else path.iterdir()
    for item in iterator:
        try:
            stat = item.stat()
        except FileNotFoundError:
            continue
        items.append({
            "path": str(item),
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": stat.st_size,
            "modified_time_epoch": stat.st_mtime,
        })
    return {
        "status": "listed",
        "absolute_path": str(path),
        "recursive": recursive,
        "count": len(items),
        "items": items,
    }


def search_files(path: Path, query: str, recursive: bool = True, case_sensitive: bool = False) -> Dict[str, Any]:
    if not path.exists():
        raise WorkspaceToolError(f"Search root does not exist: {path}")
    files = path.rglob("*") if recursive else path.iterdir()
    matches: List[Dict[str, Any]] = []
    needle = query if case_sensitive else query.lower()
    for item in files:
        if not item.is_file() or not is_probably_text(item):
            continue
        try:
            text = item.read_text(encoding=DEFAULT_ENCODING)
        except Exception:
            continue
        haystack = text if case_sensitive else text.lower()
        if needle in haystack:
            excerpts = []
            for i, line in enumerate(text.splitlines(), start=1):
                compare = line if case_sensitive else line.lower()
                if needle in compare:
                    excerpts.append({"line": i, "text": line[:500]})
                    if len(excerpts) >= 5:
                        break
            matches.append({"path": str(item), "matches": excerpts})
    return {
        "status": "searched",
        "absolute_path": str(path),
        "query": query,
        "count": len(matches),
        "results": matches,
    }


def read_file(path: Path) -> Dict[str, Any]:
    text = read_text_file(path)
    payload = verification_payload(path, text, text, path.exists())
    payload.pop("diff_preview", None)
    payload["status"] = "read"
    payload["content"] = text
    return payload


# ----------------------------
# Public tool entry point
# ----------------------------

def dispatch(action: str, args: Dict[str, Any], agent_dir: str, scope: Any) -> Dict[str, Any]:
    if action == "create_file":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return create_file(path, args.get("content", ""))
    if action == "write_file":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return write_file(path, args.get("content", ""))
    if action == "append_file":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return append_file(path, args.get("content", ""))
    if action == "read_file":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return read_file(path)
    if action == "replace_in_file":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return replace_in_file(path, args["old_text"], args["new_text"], args.get("count"))
    if action == "insert_at_line":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return insert_at_line(path, int(args["line"]), args.get("content", ""))
    if action == "delete_lines":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return delete_lines(path, int(args["start_line"]), int(args["end_line"]))
    if action == "rename_path":
        old_path = ensure_allowed(args["old_path"], scope, agent_dir)
        new_path = ensure_allowed(args["new_path"], scope, agent_dir)
        return rename_path(old_path, new_path)
    if action == "delete_path":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return delete_path(path)
    if action == "mkdir":
        path = ensure_allowed(args["path"], scope, agent_dir)
        return mkdir(path)
    if action == "list_dir":
        path = ensure_allowed(args.get("path", "."), scope, agent_dir)
        return list_dir(path, bool(args.get("recursive", False)))
    if action == "search_files":
        path = ensure_allowed(args.get("path", "."), scope, agent_dir)
        return search_files(path, args["query"], bool(args.get("recursive", True)), bool(args.get("case_sensitive", False)))

    raise WorkspaceToolError(
        "Unknown action. Supported actions: create_file, write_file, append_file, read_file, "
        "replace_in_file, insert_at_line, delete_lines, rename_path, delete_path, mkdir, list_dir, search_files"
    )


def run(args: Dict[str, Any], agent_dir: str) -> str:
    try:
        if not isinstance(args, dict):
            raise WorkspaceToolError("Args must be a JSON object / Python dict.")
        action = str(args.get("action", "")).strip()
        if not action:
            raise WorkspaceToolError("No action provided.")

        config = load_rules(agent_dir)
        result = dispatch(action, args, agent_dir, config["scope"])
        return json.dumps(result, ensure_ascii=False, indent=2)
    except KeyError as e:
        return json.dumps({"status": "error", "error": f"Missing required argument: {e}"}, ensure_ascii=False, indent=2)
    except WorkspaceToolError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Unhandled workspace_tool error: {str(e)}"}, ensure_ascii=False, indent=2)
