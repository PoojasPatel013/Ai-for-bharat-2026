"""Sandboxed code execution with resource limits.

Executes code snippets in isolated subprocess environments with:
- Timeout enforcement (default 5s)
- Memory limits via ulimit on Linux
- No network access (restricted imports)
- Captured stdout/stderr for error analysis
"""

import subprocess
import sys
import tempfile
import os
import logging
import platform
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Maximum execution time in seconds
DEFAULT_TIMEOUT = 5

# Maximum memory in bytes (50MB)
MAX_MEMORY_BYTES = 50 * 1024 * 1024

# Dangerous modules that should be blocked in sandbox
BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket", "http",
    "urllib", "requests", "pathlib", "glob", "importlib",
    "ctypes", "signal", "multiprocessing", "threading",
}


def _check_for_dangerous_imports(code: str) -> Optional[str]:
    """Pre-screen code for dangerous imports before execution."""
    import re
    for line in code.split("\n"):
        stripped = line.strip()
        # Match: import os, from os import ..., __import__("os")
        for mod in BLOCKED_IMPORTS:
            if re.search(rf'\bimport\s+{mod}\b', stripped):
                return f"Blocked import: '{mod}' is not allowed in sandbox"
            if re.search(rf'\bfrom\s+{mod}\b', stripped):
                return f"Blocked import: 'from {mod}' is not allowed in sandbox"
    if "__import__" in code:
        return "Blocked: __import__() is not allowed in sandbox"
    if "eval(" in code or "exec(" in code:
        return "Blocked: eval()/exec() is not allowed in sandbox"
    return None


def execute_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Execute Python code in an isolated subprocess with resource limits.

    Returns:
        Dict with keys:
        - success: bool — True if code ran without errors
        - stdout: str — captured standard output
        - stderr: str — captured standard error
        - exit_code: int — process exit code
        - error_type: str | None — e.g. 'SyntaxError', 'NameError', 'TimeoutError'
        - error_message: str | None — human readable error description
        - timed_out: bool — True if execution exceeded timeout
    """
    # Pre-screen for dangerous operations
    danger = _check_for_dangerous_imports(code)
    if danger:
        return {
            "success": False,
            "stdout": "",
            "stderr": danger,
            "exit_code": 1,
            "error_type": "SecurityError",
            "error_message": danger,
            "timed_out": False,
        }

    # Write code to a temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="oasis_sandbox_"
        ) as f:
            f.write(code)
            script_path = f.name
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "error_type": "InternalError",
            "error_message": f"Failed to create sandbox script: {e}",
            "timed_out": False,
        }

    try:
        # Build command with resource limits
        is_linux = platform.system() == "Linux"

        if is_linux:
            # Use ulimit for memory restriction + nice for CPU priority
            cmd = [
                "bash", "-c",
                f"ulimit -v {MAX_MEMORY_BYTES // 1024} 2>/dev/null; "
                f"nice -n 19 {sys.executable} -u {script_path}"
            ]
        else:
            cmd = [sys.executable, "-u", script_path]

        # Execute with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        stdout = result.stdout[:5000]  # Cap output size
        stderr = result.stderr[:5000]

        # Parse error type from stderr
        error_type = None
        error_message = None
        if result.returncode != 0 and stderr:
            # Extract Python error class from traceback
            for line in reversed(stderr.strip().split("\n")):
                line = line.strip()
                if ":" in line and not line.startswith("File "):
                    parts = line.split(":", 1)
                    if parts[0] in (
                        "SyntaxError", "NameError", "TypeError", "ValueError",
                        "AttributeError", "IndexError", "KeyError", "ZeroDivisionError",
                        "ImportError", "ModuleNotFoundError", "RuntimeError",
                        "RecursionError", "OverflowError", "IndentationError",
                        "TabError", "FileNotFoundError", "PermissionError",
                    ):
                        error_type = parts[0]
                        error_message = parts[1].strip()
                        break
            if not error_type:
                error_type = "RuntimeError"
                error_message = stderr.strip().split("\n")[-1][:200]

        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
            "error_type": error_type,
            "error_message": error_message,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "exit_code": -1,
            "error_type": "TimeoutError",
            "error_message": f"Code execution exceeded the {timeout}s time limit",
            "timed_out": True,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "error_type": "InternalError",
            "error_message": f"Sandbox execution failed: {e}",
            "timed_out": False,
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(script_path)
        except OSError:
            pass


def execute_code(code: str, language: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Execute code in a sandbox, dispatching by language.

    Currently supports:
    - Python: full subprocess execution with resource limits

    Other languages return a 'not supported' result — they still get
    analyzed by the static analyzer and Bedrock AI.
    """
    lang = language.lower()

    if lang in ("python", "py"):
        return execute_python(code, timeout=timeout)

    # For non-Python languages, we can't execute but we signal that
    # static analysis + LLM should be used instead
    return {
        "success": None,  # None = "not executed, unknown"
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "error_type": None,
        "error_message": f"Sandbox execution not available for {language} — using static analysis + AI",
        "timed_out": False,
        "skipped": True,
    }
