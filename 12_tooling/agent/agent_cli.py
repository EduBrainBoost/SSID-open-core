#!/usr/bin/env python3
"""SSID Local LLM Agent CLI — tool interface for autonomous agents.

Subcommands: fs-read, fs-write, sh, http-get, llm
Enforces ROOT-24-LOCK and SAFE-FIX policies.
"""

import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

DEFAULT_MODEL = os.environ.get("SSID_LLM_MODEL", "qwen2.5-coder:7b")

LITELLM_URL = os.environ.get("SSID_LITELLM_URL", "http://localhost:4000/v1/chat/completions")

DENY_GLOBS = [".git/**", "**/.env", "**/secrets/**"]

SHELL_WHITELIST = [
    "ls", "cat", "grep", "find", "python", "pip",
    "git status", "git diff", "git log",
]

HTTP_WHITELIST = [
    "api.github.com",
    "registry.npmjs.org",
    "pypi.org",
]

VALID_ROOTS = [
    "01_ai_layer", "02_audit_logging", "03_core", "04_deployment",
    "05_documentation", "06_data_pipeline", "07_governance_legal",
    "08_identity_score", "09_meta_identity", "10_interoperability",
    "11_test_simulation", "12_tooling", "13_ui_layer",
    "14_zero_time_auth", "15_infra", "16_codex", "17_observability",
    "18_data_layer", "19_adapters", "20_foundation",
    "21_post_quantum_crypto", "22_datasets", "23_compliance",
    "24_meta_orchestration",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_path(raw: str) -> pathlib.Path:
    """Resolve *raw* relative to REPO_ROOT and validate ROOT-24-LOCK."""
    p = (REPO_ROOT / raw).resolve()
    try:
        rel = p.relative_to(REPO_ROOT)
    except ValueError:
        sys.exit(f"ERROR: path outside repo root: {p}")

    # Deny-glob check (simple fnmatch)
    import fnmatch
    rel_str = rel.as_posix()
    for g in DENY_GLOBS:
        if fnmatch.fnmatch(rel_str, g):
            sys.exit(f"ERROR: path matches deny-glob {g}: {rel_str}")

    # Must be inside a valid root
    top = rel.parts[0] if rel.parts else ""
    if top not in VALID_ROOTS:
        sys.exit(f"ERROR: path not inside a valid ROOT-24 folder: {top}")

    return p


def _is_cmd_whitelisted(cmd: str) -> bool:
    cmd_stripped = cmd.strip()
    for allowed in SHELL_WHITELIST:
        if cmd_stripped == allowed or cmd_stripped.startswith(allowed + " "):
            return True
    return False


def _is_domain_whitelisted(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host in HTTP_WHITELIST


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_fs_read(args):
    p = _resolve_path(args.path)
    if not p.exists():
        sys.exit(f"ERROR: file not found: {p}")
    print(p.read_text(encoding="utf-8", errors="ignore"))


def cmd_fs_write(args):
    p = _resolve_path(args.path)

    # SAFE-FIX: hash before
    sha_before = None
    if p.exists():
        sha_before = _sha256(p.read_bytes())

    content = args.content
    if content == "-":
        content = sys.stdin.read()

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    sha_after = _sha256(p.read_bytes())

    evidence = {
        "operation": "fs_write",
        "file": str(p),
        "sha256_before": sha_before,
        "sha256_after": sha_after,
        "safe_fix_confirmed": True,
    }
    print(f"SAFE-FIX evidence: {evidence}")


def cmd_sh(args):
    cmd = " ".join(args.command)
    if not _is_cmd_whitelisted(cmd):
        sys.exit(f"ERROR: command not whitelisted: {cmd}")

    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=str(REPO_ROOT), encoding="utf-8", errors="ignore",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    sys.exit(result.returncode)


def cmd_http_get(args):
    url = args.url
    if not _is_domain_whitelisted(url):
        sys.exit(f"ERROR: domain not whitelisted for URL: {url}")

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(resp.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        sys.exit(f"ERROR: HTTP GET failed: {exc}")


def cmd_llm(args):
    prompt = args.prompt
    model = args.model or DEFAULT_MODEL

    # Try LiteLLM first
    try:
        import json
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            LITELLM_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(data["choices"][0]["message"]["content"])
            return
    except Exception:
        pass  # fallback to ollama

    # Fallback: ollama run
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, encoding="utf-8", errors="ignore",
            timeout=120,
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            sys.exit(f"ERROR: ollama failed: {result.stderr}")
    except FileNotFoundError:
        sys.exit("ERROR: neither LiteLLM nor ollama available")
    except subprocess.TimeoutExpired:
        sys.exit("ERROR: ollama timed out")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="agent_cli",
        description="SSID Local LLM Agent CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # fs-read
    p_fsr = sub.add_parser("fs-read", help="Read a file")
    p_fsr.add_argument("path", help="Relative path inside repo")
    p_fsr.set_defaults(func=cmd_fs_read)

    # fs-write
    p_fsw = sub.add_parser("fs-write", help="Write content to a file (SAFE-FIX)")
    p_fsw.add_argument("path", help="Relative path inside repo")
    p_fsw.add_argument("content", help="Content to write (use '-' for stdin)")
    p_fsw.set_defaults(func=cmd_fs_write)

    # sh
    p_sh = sub.add_parser("sh", help="Run a whitelisted shell command")
    p_sh.add_argument("command", nargs=argparse.REMAINDER, help="Command and arguments")
    p_sh.set_defaults(func=cmd_sh)

    # http-get
    p_http = sub.add_parser("http-get", help="HTTP GET (whitelisted domains)")
    p_http.add_argument("url", help="URL to GET")
    p_http.set_defaults(func=cmd_http_get)

    # llm
    p_llm = sub.add_parser("llm", help="Send prompt to local LLM")
    p_llm.add_argument("prompt", help="Prompt text")
    p_llm.add_argument("--model", default=None, help=f"Model (default: {DEFAULT_MODEL})")
    p_llm.set_defaults(func=cmd_llm)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
