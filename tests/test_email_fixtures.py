"""Runs the finder against email bodies dropped into ``tests/emails/``.

Ported from the PHP ``EmailFixturesTest``.

Convention: each fixture file is named after the password(s) it contains, using
``-OR-`` as the separator between passwords::

    {password}.txt                       one password  e.g. Br5Tk9m.txt
    {password1}-OR-{password2}.html       two passwords e.g. Mk3Wp7q-OR-Vb9Tz2r.html
    {pw1}-OR-{pw2}-OR-{pw3}-OR-{pw4}.txt  four passwords

The separator is the literal string ``-OR-``, so passwords that themselves
contain a dash (e.g. ``Rd4-Gh7n``) are handled correctly.

The test asserts that the expected password(s) are exactly the top-ranked
candidates the finder returns for that body (order among them does not matter).

All fixtures are anonymised test data -- company names are replaced with
"Example", links point at ``example.com``, and the passwords are freshly
invented one-time codes, not real credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from password_finder import PasswordFinder

FIXTURE_DIR = Path(__file__).parent / "emails"

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


def test_fixtures_directory_has_files() -> None:
    assert _fixtures(), "No email fixtures found to test against."
