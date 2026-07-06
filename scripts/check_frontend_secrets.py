#!/usr/bin/env python3
"""CI-safe secret-boundary check for the frontend (Task 9/14).

Scans frontend source (never `node_modules`/`.next`/lockfiles) for two
concerning patterns:

  1. A `NEXT_PUBLIC_`-prefixed env var name whose own name contains a
     secret-shaped keyword (SECRET, API_KEY, PRIVATE_KEY, PASSWORD,
     CLIENT_SECRET, AUTH_SECRET, ...) — anything `NEXT_PUBLIC_` is bundled
     into client-side JS, so a name like that is very likely a real
     backend credential about to leak into the browser. `NEXT_PUBLIC_API_BASE_URL`
     is the one explicitly allowed exception (a public backend address,
     not a secret) — see `frontend/lib/api/config.ts`.
  2. A hardcoded literal that looks like a real credential (an Anthropic-
     style `sk-...` key, or a long literal string assigned to a variable
     named `apiKey`/`secret`/`password`/`token`).

Exits non-zero and prints file:line + which rule matched on any hit —
deliberately never the matched substring itself, so running this (or its
output landing in CI logs) can never itself leak the secret it found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FRONTEND_ROOT = Path(__file__).resolve().parent.parent / "frontend"

SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".json"}
EXCLUDED_DIRS = {"node_modules", ".next", "out", "coverage", ".git"}

# NEXT_PUBLIC_ names allowed to exist — public, non-secret configuration.
ALLOWED_NEXT_PUBLIC = {"NEXT_PUBLIC_API_BASE_URL"}

SECRET_NAME_KEYWORDS = (
    "SECRET",
    "API_KEY",
    "APIKEY",
    "PRIVATE_KEY",
    "PASSWORD",
    "CLIENT_SECRET",
    "AUTH_SECRET",
    "DATABASE_URL",
    "ACCESS_TOKEN",
)

NEXT_PUBLIC_NAME_RE = re.compile(r"\bNEXT_PUBLIC_[A-Z0-9_]+\b")
LITERAL_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")
ASSIGNED_LITERAL_RE = re.compile(
    r"\b(api[_-]?key|secret|password|access[_-]?token)\b\s*[:=]\s*[\"'][^\"']{12,}[\"']",
    re.IGNORECASE,
)


def iter_source_files():
    for path in FRONTEND_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def scan_file(path: Path) -> list[tuple[int, str]]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        for name in NEXT_PUBLIC_NAME_RE.findall(line):
            if name in ALLOWED_NEXT_PUBLIC:
                continue
            if any(keyword in name for keyword in SECRET_NAME_KEYWORDS):
                findings.append((lineno, f"disallowed NEXT_PUBLIC_ secret-shaped name ({name})"))

        if LITERAL_KEY_RE.search(line):
            findings.append((lineno, "literal key-shaped string (sk-...)"))

        if ASSIGNED_LITERAL_RE.search(line):
            findings.append((lineno, "literal value assigned to a secret-shaped variable name"))

    return findings


def main() -> int:
    all_findings: list[tuple[Path, int, str]] = []
    for path in iter_source_files():
        for lineno, reason in scan_file(path):
            all_findings.append((path, lineno, reason))

    if not all_findings:
        print("check_frontend_secrets: no secret-shaped patterns found in frontend source.")
        return 0

    print("check_frontend_secrets: FAILED — possible secret exposure in frontend source:\n")
    for path, lineno, reason in all_findings:
        rel = path.relative_to(FRONTEND_ROOT.parent)
        print(f"  {rel}:{lineno} — {reason}")
    print("\nValues are never printed above. Move any real secret server-side "
          "(no NEXT_PUBLIC_ prefix) before committing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
