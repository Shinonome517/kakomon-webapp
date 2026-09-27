#!/usr/bin/env python3
"""Check candidate Git files for common private material. Not a full secret scanner."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {
    ".private",
    "private",
    "_private",
    ".local",
    ".codex",
    ".agents",
    "runtime",
    "media",
    "imports",
    "backups",
    "logs",
    "source-pdfs",
    "data",
}
PRIVATE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
    ".jsonl",
    ".pdf",
    ".zip",
    ".bak",
}
PATTERNS = [
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    (
        "GitHub token",
        re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    ),
    ("AWS access key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style token", re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")),
    ("credential in URL", re.compile(rb"https?://[^/\s:@]+:[^/\s@]+@")),
]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def candidates(staged: bool) -> list[str]:
    if staged:
        raw = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    else:
        raw = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return sorted({p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged", action="store_true", help="Inspect added/modified index contents only"
    )
    args = parser.parse_args()
    try:
        actual_root = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        if actual_root != ROOT:
            print("ERROR: this directory must be the Git repository root.", file=sys.stderr)
            return 2
        names = candidates(args.staged)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(
            f"ERROR: initialize Git in the project root first ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    problems: list[tuple[str, str]] = []
    for name in names:
        path = Path(name)
        # Documentation examples are allowed; real runtime or personal files are not.
        bad_root = bool(path.parts and path.parts[0] in PRIVATE_DIRS)
        is_example = path.name.endswith(".example")
        bad_name = (
            "PRIVATE" in path.name.upper()
            or ".private." in path.name.lower()
            or path.name.endswith(".config.toml")
            or (path.name.startswith(".env") and not is_example)
            or path.name in {"auth.json", "credentials.json"}
            or path.name.startswith(("id_rsa", "id_ed25519"))
        )
        bad_suffix = path.suffix.lower() in PRIVATE_SUFFIXES and not is_example
        if bad_root or bad_name or bad_suffix:
            problems.append((name, "private/runtime/source-data filename"))
        disk_path = ROOT / path
        if disk_path.is_symlink():
            problems.append((name, "symlink requires manual review"))
            continue
        try:
            if args.staged:
                data = git("show", f":{name}")
            elif disk_path.is_file():
                data = disk_path.read_bytes()
            else:
                continue  # A deleted tracked file is not published from the working tree.
        except (OSError, subprocess.CalledProcessError):
            problems.append((name, "could not read candidate"))
            continue
        if len(data) > 5 * 1024 * 1024:
            problems.append((name, "file over 5 MiB requires manual review"))
            continue
        for label, pattern in PATTERNS:
            if pattern.search(data):
                problems.append((name, label))
    if problems:
        print("FAIL: inspect the following files. Matched secret values are not printed.")
        for name, why in problems:
            print(f"  {name!r}: {why}")
        return 1
    print(f"PASS: {len(names)} candidate files checked. Manual review is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
