"""Command-line helpers for trying the finder against real messages.

Two entry points are exposed (see ``pyproject.toml``):

    find-password email.txt        # from a file
    pbpaste | find-password        # pipe from the clipboard (macOS)
    cat message.eml | find-password

    scan-emails                    # run over every file in tests/emails/
    scan-emails path/to/dir        # ...or a directory of your choosing
"""

from __future__ import annotations

import sys
from pathlib import Path

from .email_body import extract_body
from .finder import PasswordFinder


def find_password(argv: list[str] | None = None) -> int:
    """Read text from a file argument or STDIN and print ranked candidates."""
    argv = sys.argv[1:] if argv is None else argv

    if argv:
        text = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.read()

    # A raw message is decoded first; a plain body passes through untouched.
    candidates = PasswordFinder().find_all(extract_body(text))

    if not candidates:
        print("No password found.", file=sys.stderr)
        return 1

    for i, c in enumerate(candidates):
        marker = "→" if i == 0 else " "
        print(f"{marker} {c.password:<32}  {c.confidence:.2f}  [{c.keyword}]  {c.context}")

    return 0


def scan_emails(argv: list[str] | None = None) -> int:
    """Run the finder against every file in a directory and print candidates."""
    argv = sys.argv[1:] if argv is None else argv

    directory = Path(argv[0]) if argv else Path(__file__).resolve().parents[2] / "tests" / "emails"

    finder = PasswordFinder()
    found = 0
    missed = 0

    for file in sorted(directory.iterdir()):
        if not file.is_file() or file.suffix == ".md" or file.name == ".gitkeep":
            continue

        text = file.read_text(encoding="utf-8", errors="replace")
        candidates = finder.find_all(extract_body(text))

        print(f"\n=== {file.name} ===")

        if not candidates:
            print("  (no password found)")
            missed += 1
            continue

        found += 1
        for i, c in enumerate(candidates):
            marker = "→" if i == 0 else " "
            print(f"  {marker} {c.password:<32} conf={c.confidence:.2f}  keyword={c.keyword}")

    print("\n" + "-" * 40)
    print(f"{found} file(s) with a match, {missed} without.")

    return 0


if __name__ == "__main__":
    raise SystemExit(find_password())
