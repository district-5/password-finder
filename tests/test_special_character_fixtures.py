"""Runs the finder against the special-character corpus in
``tests/emails-special-characters/``.

These passwords contain characters that cannot be encoded in a file name
(``/``, ``\\``, ``|``, ``:`` ...), so this corpus uses a different convention to
``tests/emails/``: **the first line of the file is the expected password**, and
the test strips that line before handing the rest of the file to the finder.

    a&f$!(
    <- blank line
    Hi Joe,

    Please find the encrypted quote attached...

    The password is: a&f$!(

The first line is trimmed of surrounding whitespace, so a password with leading
or trailing spaces cannot be expressed here; nothing else about it is touched.

All fixtures are anonymised test data -- company names are "Example", addresses
point at ``example.com``, and every password is freshly invented.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from password_finder import PasswordFinder

FIXTURE_DIR = Path(__file__).parent / "emails-special-characters"


def _fixtures() -> list[Path]:
    return sorted(
        p for p in FIXTURE_DIR.glob("*") if p.suffix in {".txt", ".html"}
    )


def _split(raw: str) -> tuple[str, str]:
    """Split a fixture into ``(expected_password, body)``.

    The first line carries the expected password and is removed so the finder
    never sees it -- otherwise the fixture would be trivially self-answering.
    """
    first, _, body = raw.partition("\n")
    return first.strip(), body


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda p: p.name)
def test_special_character_password_is_top_candidate(fixture: Path) -> None:
    expected, body = _split(fixture.read_text(encoding="utf-8"))

    assert expected, f"{fixture.name} has no password on its first line"

    finder = PasswordFinder()
    candidates = finder.find_all(body)

    assert candidates, (
        f"No password found in {fixture.name} (expected {expected!r})"
    )

    found = [f"{c.password!r} ({c.confidence:.2f})" for c in candidates]
    assert candidates[0].password == expected, (
        f"Top candidate for {fixture.name} was {candidates[0].password!r}; "
        f"expected {expected!r}. All: {', '.join(found)}"
    )


def test_first_line_is_stripped_before_matching() -> None:
    """The header line must not be what the finder is matching on."""
    fixtures = _fixtures()
    assert fixtures, "No special-character fixtures found to test against."

    for fixture in fixtures:
        raw = fixture.read_text(encoding="utf-8")
        expected, body = _split(raw)

        assert raw.startswith(expected), (
            f"{fixture.name} must begin with its expected password"
        )
        assert not body.startswith(expected), (
            f"{fixture.name}: header line was not removed from the body"
        )


def test_fixtures_directory_has_files() -> None:
    assert _fixtures(), "No special-character fixtures found to test against."
