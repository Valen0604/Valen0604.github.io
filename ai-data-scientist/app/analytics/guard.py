"""
A static check on code the model writes, before it runs.

READ THIS BEFORE RELYING ON IT. This is a guard rail, not a security boundary. It stops
the obvious mistakes: shelling out, opening network connections, deleting files, reading
the environment. A determined attacker can get around a check like this. The code still
runs on your laptop with your permissions.

That is acceptable for the intended use, which is a student analysing their own data on
their own machine. It is not acceptable for a public deployment. There, run the worker in
a container with no network and a read-only file system. See LIMITATIONS.md.
"""
from __future__ import annotations

import ast

BLOCKED_MODULES = {
    "subprocess", "socket", "socketserver", "ssl", "requests", "urllib", "urllib3", "http",
    "httpx", "aiohttp", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "paramiko",
    "ctypes", "cffi", "multiprocessing", "threading", "concurrent", "asyncio", "signal",
    "shutil", "webbrowser", "winreg", "msvcrt", "pty", "importlib", "imp", "runpy",
    "code", "codeop", "pdb", "anthropic", "openai", "dotenv", "pickle", "marshal", "shelve",
    "tempfile", "glob", "pathlib", "sys", "builtins", "inspect", "gc",
}
BLOCKED_NAMES = {"eval", "exec", "compile", "__import__", "input", "breakpoint", "exit",
                 "quit", "globals", "locals", "vars", "getattr", "setattr", "delattr",
                 "memoryview", "help"}
# `os` is allowed for os.path, which analysis code uses. These members of it are not.
BLOCKED_OS = {"system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename",
              "renames", "replace", "kill", "abort", "startfile", "environ", "getenv",
              "putenv", "unsetenv", "chdir", "chmod", "chown", "link", "symlink", "mkfifo",
              "truncate", "walk", "scandir", "listdir", "fork", "execv", "execve", "execl",
              "spawnl", "spawnv", "spawnve", "open", "fdopen", "pipe", "dup", "dup2",
              "makedirs", "mkdir", "getcwd", "getlogin"}
ALLOWED_DUNDERS = {"__name__", "__len__", "__doc__", "__version__", "__init__"}


class Violation(str):
    pass


def check(code: str) -> list[str]:
    """Return a list of reasons the code is refused. Empty means it may run."""
    try:
        tree = ast.parse(code, filename="<analysis>")
    except SyntaxError as e:
        return [f"Syntax error on line {e.lineno}: {e.msg}"]

    found: list[str] = []

    def add(node: ast.AST, message: str) -> None:
        found.append(f"line {getattr(node, 'lineno', '?')}: {message}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    add(node, f"import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_MODULES:
                add(node, f"import from '{node.module}' is not allowed")
            if root == "os":
                for alias in node.names:
                    if alias.name in BLOCKED_OS or alias.name == "*":
                        add(node, f"'os.{alias.name}' is not allowed")
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES:
                add(node, f"'{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__") and attr not in ALLOWED_DUNDERS:
                add(node, f"access to '{attr}' is not allowed")
            if isinstance(node.value, ast.Name) and node.value.id == "os" and attr in BLOCKED_OS:
                add(node, f"'os.{attr}' is not allowed")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if len(v) < 300 and (".." in v.replace("\\", "/").split("/")
                                 or v.lower().endswith(".env")
                                 or "ANTHROPIC_API_KEY" in v):
                add(node, "paths outside the session folder, and secrets, are not allowed")

    # Report each problem once.
    return list(dict.fromkeys(found))
