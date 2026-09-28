#!/usr/bin/env python3
"""Flag track-specific vocabulary leaking into mandates/*.md.

Mandates must stay generic (no restaurant/reservation domain words, no
endpoint paths, no snake_case field names, no error-code-like strings).
Run this alongside `python -m harness check` — that has its own scan, this
is a second, independent check.

Usage: python3 factory-tools/mandate_scanner.py [mandates_dir]
Exit code 1 if any hit is found.
"""
import re
import sys
from pathlib import Path

TRACK_WORDS = [
    "reservation", "reservations", "booking", "bookings", "table", "tables",
    "diner", "diners", "restaurant", "restaurants", "slot", "slots",
    "timezone", "time zone", "dst", "cancel", "cancellation", "availability",
    "available", "party size", "waitlist", "seating", "tablekeeper",
]

PATTERNS = {
    "endpoint path": re.compile(r"(?:GET|POST|PUT|PATCH|DELETE)\s+/\S+|(?<![\w.])/(?:api|v\d+)/[\w/{}-]+"),
    "snake_case field": re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){1,}\b"),
    "error-code-like string": re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,}\b"),
}

WORD_RE_CACHE = {w: re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in TRACK_WORDS}


def scan_file(path: Path):
    hits = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for word, rx in WORD_RE_CACHE.items():
            if rx.search(line):
                hits.append((lineno, "track word", word, line.strip()))
        for label, rx in PATTERNS.items():
            for m in rx.finditer(line):
                hits.append((lineno, label, m.group(0), line.strip()))
    return hits


def main():
    mandates_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mandates")
    files = sorted(mandates_dir.glob("*.md"))
    if not files:
        print(f"no mandate files found under {mandates_dir}/")
        return 0

    total_hits = 0
    for path in files:
        hits = scan_file(path)
        if not hits:
            continue
        total_hits += len(hits)
        print(f"\n{path}:")
        for lineno, label, match, line in hits:
            print(f"  line {lineno} [{label}] '{match}': {line}")

    if total_hits:
        print(f"\n{total_hits} hit(s) across {len(files)} file(s). Fix before submitting.")
        return 1

    print(f"clean: {len(files)} mandate file(s), no track vocabulary found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
