"""Runs the finder against PRIVATE email bodies in ``tests/emails-private/``.

Same contract and file-naming convention as ``test_email_fixtures.py``: each
fixture is named after the password(s) it contains, ``-OR-`` separating
multiple passwords, and the expected password(s) must be exactly the top-ranked
candidates the finder returns.

Unlike ``tests/emails/``, this directory is git-ignored (see ``.gitignore``) so
it can hold real, un-anonymised messages that must not be committed. It is
normally empty in a clean checkout, so these tests are skipped when no private
fixtures are present -- drop ``.txt``/``.html`` files in to exercise them
locally.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from password_finder import PasswordFinder

FIXTURE_DIR = Path(__file__).parent / "emails-private"

# Separator between multiple expected passwords in a fixture file name.
SEPARATOR = "-OR-"


def _fixtures() -> list[Path]:
    return sorted(
        p for p in FIXTURE_DIR.glob("*") if p.suffix in {".txt", ".html"}
    )


def _expected_passwords(fixture: Path) -> list[str]:
    """Passwords a fixture is expected to contain, parsed from its file name."""
    return fixture.stem.split(SEPARATOR)


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda p: p.name)
def test_top_candidates_match_file_name(fixture: Path) -> None:
    expected = _expected_passwords(fixture)

    finder = PasswordFinder()
    candidates = finder.find_all(fixture.read_text(encoding="utf-8"))

    assert candidates, (
        f"No password found in {fixture.name} "
        f"(expected {', '.join(expected)})"
    )

    found = [c.password for c in candidates]

    # The expected passwords should be exactly the top N candidates (where N is
    # how many passwords the file name lists); order among them is irrelevant.
    top = found[: len(expected)]
    assert set(top) == set(expected), (
        f"Top {len(expected)} candidate(s) for {fixture.name} were "
        f"{', '.join(top)}; expected {', '.join(expected)}. "
        f"All: {', '.join(f'{c.password} ({c.confidence:.2f})' for c in candidates)}"
    )


def test_private_fixtures_dir_exists() -> None:
    # The directory ships (git-ignored, with a .gitkeep); its contents do not.
    assert FIXTURE_DIR.is_dir(), (
        f"Expected private fixtures directory at {FIXTURE_DIR}"
    )
