"""TEMPORARY debug helper -- delete this file when you're done.

Adds a dump to the end of every ``pytest`` run listing every password the
library extracts from each fixture in ``tests/emails/``. It runs in
``pytest_terminal_summary`` so it prints unconditionally (no ``-s`` needed) and
does not affect any test outcome.
"""

from __future__ import annotations

from pathlib import Path

from password_finder import PasswordFinder

_EMAILS_DIR = Path(__file__).parent / "emails"


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    write = terminalreporter.write_line
    finder = PasswordFinder()

    terminalreporter.section("password dump (temporary)")

    fixtures = sorted(
        p for p in _EMAILS_DIR.glob("*") if p.suffix in {".txt", ".html"}
    )

    total = 0
    for fixture in fixtures:
        candidates = finder.find_all(fixture.read_text(encoding="utf-8"))
        total += len(candidates)

        if not candidates:
            write(f"{fixture.name}: (none found)")
            continue

        found = ", ".join(f"{c.password} [{c.keyword} {c.confidence:.2f}]" for c in candidates)
        write(f"{fixture.name}: {found}")

    write(f"\n{total} password(s) found across {len(fixtures)} fixture file(s).")
