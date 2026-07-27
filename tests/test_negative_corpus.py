"""Precision regression tests: emails that contain NO password.

Each file in ``tests/emails_negative/`` is a realistic message that must NOT
yield a convincing password -- marketing, statements, and messages where a
keyword sits next to a URL / email address / date / phone number / currency
amount that the finder should reject rather than extract.

The contract: the finder returns nothing at or above ``THRESHOLD``. Anything it
does surface must be low confidence, so a caller applying a sensible threshold
sees an empty result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from password_finder import PasswordFinder

NEGATIVE_DIR = Path(__file__).parent / "emails_negative"

# A caller acting on candidates at or above this confidence would be misled, so
# nothing in the negative corpus may reach it.
THRESHOLD = 0.5


def _negatives() -> list[Path]:
    return sorted(
        p for p in NEGATIVE_DIR.glob("*") if p.suffix in {".txt", ".html"}
    )


@pytest.mark.parametrize("fixture", _negatives(), ids=lambda p: p.name)
def test_no_convincing_password(fixture: Path) -> None:
    finder = PasswordFinder()
    candidates = finder.find_all(fixture.read_text(encoding="utf-8"))

    convincing = [c for c in candidates if c.confidence >= THRESHOLD]

    assert not convincing, (
        f"{fixture.name} produced a convincing false positive: "
        + ", ".join(f"{c.password!r} ({c.confidence:.2f}, {c.keyword})" for c in convincing)
    )


def test_negative_corpus_has_files() -> None:
    assert _negatives(), "No negative-corpus fixtures found."
