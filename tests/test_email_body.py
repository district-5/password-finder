"""Tests for decoding a raw email message down to a matchable body.

A transport-encoded message is not a body: quoted-printable rewrites "=" and
breaks long lines, base64 hides the text entirely, and multipart messages carry
several bodies. Without decoding, the finder returns a confident wrong answer.

All addresses point at ``example.com`` and every password here is invented.
"""

from __future__ import annotations

import base64

import pytest

from password_finder import PasswordFinder, extract_body, looks_like_email

HEADERS = (
    "From: sender@example.com\r\n"
    "To: recipient@example.com\r\n"
    "Subject: Encrypted document\r\n"
    "MIME-Version: 1.0\r\n"
)


def _message(content_type: str, encoding: str, body: str) -> str:
    return (
        HEADERS
        + f"Content-Type: {content_type}\r\n"
        + f"Content-Transfer-Encoding: {encoding}\r\n"
        + "\r\n"
        + body
    )


# --------------------------------------------------------------------------- #
# Detection: only a real message is treated as one.                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        HEADERS + "\r\nThe password is Ab12Cd34\r\n",
        "Received: from mail.example.com\r\nSubject: Hi\r\n\r\nThe password is Ab12Cd34",
        "Content-Type: text/plain\r\n\r\nThe password is Ab12Cd34",
    ],
)
def test_recognises_a_message(raw: str) -> None:
    assert looks_like_email(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "Hi Joe,\n\nThe password is Hunter2!",
        "The password is Hunter2!",
        "",
        "Password: Hunter2!\n\nRegards",
        # A body that quotes a header further down is still a body.
        "Hi,\n\nsee below\n\nFrom: someone@example.com\n\nThe password is Hunter2!",
    ],
)
def test_does_not_mistake_a_body_for_a_message(raw: str) -> None:
    assert not looks_like_email(raw)


def test_a_plain_body_passes_through_untouched() -> None:
    body = "Hi Joe,\n\nThe password is Hunter2!\n"
    assert extract_body(body) == body


# --------------------------------------------------------------------------- #
# Decoding: the body comes back matchable.                                    #
# --------------------------------------------------------------------------- #


def test_quoted_printable_is_decoded() -> None:
    # "=3D" is an escaped "=", and a trailing "=" is a soft line break that
    # splits a word (and would split a password) mid-token.
    raw = _message(
        "text/plain; charset=utf-8",
        "quoted-printable",
        "The password is=3D Ab12Cd34 and this line is long enough to be wrapp=\r\ned.\r\n",
    )

    assert PasswordFinder().find_passwords(raw) == ["is=3D"]           # undecoded
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Ab12Cd34"]


def test_quoted_printable_soft_break_inside_a_password() -> None:
    raw = _message(
        "text/plain; charset=utf-8",
        "quoted-printable",
        "The password is Ab12C=\r\nd34\r\n",
    )
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Ab12Cd34"]


def test_base64_is_decoded() -> None:
    encoded = base64.b64encode(b"Hi,\r\n\r\nThe password is Xy98Zw76\r\n").decode()
    raw = _message("text/plain; charset=utf-8", "base64", encoded + "\r\n")

    assert PasswordFinder().find_passwords(raw) == []                  # undecoded
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Xy98Zw76"]


def test_declared_charset_is_applied() -> None:
    body = "Das Kennwort ist Grün42Ab".encode("iso-8859-1", errors="replace")
    raw = _message("text/plain; charset=iso-8859-1", "8bit", body.decode("iso-8859-1"))

    assert "Kennwort" in extract_body(raw)


# --------------------------------------------------------------------------- #
# Multipart: several bodies, one answer.                                      #
# --------------------------------------------------------------------------- #


def _multipart(plain: str, html: str) -> str:
    return (
        HEADERS
        + 'Content-Type: multipart/alternative; boundary="BOUND"\r\n\r\n'
        + "--BOUND\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
        + plain
        + "\r\n--BOUND\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        + html
        + "\r\n--BOUND--\r\n"
    )


def test_plain_part_is_preferred() -> None:
    raw = _multipart(
        "The password is Qq11Rr22\r\n",
        "<p>The password is <b>Zz33Ss44</b></p>",
    )
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Qq11Rr22"]


def test_empty_plain_stub_falls_back_to_html() -> None:
    # A blank plain part alongside a full HTML alternative is common, and the
    # stub is not the body.
    raw = _multipart("   \r\n", "<p>The password is <b>Zz33Ss44</b></p>")
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Zz33Ss44"]


def test_attachment_parts_are_ignored() -> None:
    raw = (
        HEADERS
        + 'Content-Type: multipart/mixed; boundary="BOUND"\r\n\r\n'
        + "--BOUND\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
        + "The password is Qq11Rr22\r\n"
        + "--BOUND\r\nContent-Type: text/plain; charset=utf-8\r\n"
        + 'Content-Disposition: attachment; filename="notes.txt"\r\n\r\n'
        + "The password is Ww55Tt66\r\n"
        + "--BOUND--\r\n"
    )
    assert PasswordFinder().find_passwords(extract_body(raw)) == ["Qq11Rr22"]


# --------------------------------------------------------------------------- #
# Robustness: never lose the input.                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        HEADERS + 'Content-Type: multipart/mixed; boundary="MISSING"\r\n\r\ntruncated',
        HEADERS + "Content-Type: text/plain; charset=no-such-charset\r\n\r\nThe password is Ab12Cd34",
        HEADERS + "\r\n",
    ],
)
def test_a_malformed_message_still_returns_something(raw: str) -> None:
    # Never raise and never return nothing: a body we cannot parse is still
    # worth matching against as plain text.
    result = extract_body(raw)
    assert isinstance(result, str)
    assert result


def test_unparseable_charset_keeps_the_password_reachable() -> None:
    raw = (
        HEADERS
        + "Content-Type: text/plain; charset=no-such-charset\r\n\r\n"
        + "The password is Ab12Cd34\r\n"
    )
    assert "Ab12Cd34" in extract_body(raw)
