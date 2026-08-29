"""Pull the readable body out of a raw email message.

The finder works on a body, not on a transport-encoded message. A raw ``.eml``
file is neither: quoted-printable turns "=" into "=3D" and breaks long lines
with a trailing "=", base64 hides the text completely, and a multipart message
carries several bodies at once. Feeding one straight in yields a confident
wrong answer, which is worse than no answer at all.

:func:`extract_body` takes whatever the caller has and returns text worth
matching against. Anything that is not a message is handed back untouched, so
it is safe to call on a plain body.
"""

from __future__ import annotations

import re
from email import message_from_string, policy
from email.message import EmailMessage

__all__ = ["extract_body", "looks_like_email"]

# A header line: "Name: value", allowing the folded continuations that follow.
_HEADER_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-]{1,48}:")

# Headers that mark a real message rather than a body that happens to open with
# a colon. Only one needs to be present.
_MESSAGE_HEADERS = frozenset({
    "content-type", "mime-version", "from", "to", "subject", "date",
    "received", "message-id", "return-path", "delivered-to", "sender",
})

# How far in to look for a recognisable header before giving up.
_HEADER_SCAN_LINES = 60


def looks_like_email(raw: str) -> bool:
    """Return ``True`` when the string looks like a raw email message.

    Deliberately strict: the first non-empty line must be a header, and at
    least one recognised message header must appear near the top. A body that
    merely contains a colon, or quotes a header further down, is not a message.
    """
    lines = raw.splitlines()

    first = next((line for line in lines if line.strip()), "")
    if not _HEADER_LINE_RE.match(first):
        return False

    for line in lines[:_HEADER_SCAN_LINES]:
        if not line.strip():
            # End of the header block; nothing recognisable turned up.
            break
        match = _HEADER_LINE_RE.match(line)
        if match and line[: match.end() - 1].lower() in _MESSAGE_HEADERS:
            return True

    return False


def extract_body(raw: str) -> str:
    """Return the readable body of ``raw``, decoding transport encodings.

    Quoted-printable and base64 are decoded, the declared charset is applied,
    and multipart messages give up their text: the plain part when it carries
    anything, otherwise the HTML one (which the finder strips itself).

    A string that is not a message, or one that cannot be parsed, is returned
    unchanged, so this is always safe to call.
    """
    if not looks_like_email(raw):
        return raw

    try:
        message = message_from_string(raw, policy=policy.default)
    except Exception:
        # A malformed message is still worth matching against as plain text.
        return raw

    parts = _text_parts(message)
    if not parts:
        return raw

    # Prefer a plain part with real content; an empty plain stub alongside a
    # full HTML alternative is common, and the stub is not the body.
    for content_type in ("text/plain", "text/html"):
        chosen = [text for kind, text in parts if kind == content_type and text.strip()]
        if chosen:
            return "\n\n".join(chosen)

    return raw


def _text_parts(message: EmailMessage) -> list[tuple[str, str]]:
    """Every decoded ``text/*`` part as ``(content_type, text)`` pairs."""
    parts: list[tuple[str, str]] = []

    for part in message.walk():
        if part.get_content_maintype() != "text":
            continue
        if part.get_content_disposition() == "attachment":
            continue

        try:
            content = part.get_content()
        except (LookupError, ValueError, TypeError):
            # Unknown charset or undecodable payload; skip this part rather
            # than losing the whole message.
            continue

        if isinstance(content, str):
            parts.append((part.get_content_type(), content))

    return parts
