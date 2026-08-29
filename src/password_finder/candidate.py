"""Value object representing a single extracted password candidate."""

from __future__ import annotations

from dataclasses import dataclass


def _mask(secret: str) -> str:
    """Render a secret as its length only, revealing nothing about the value."""
    return f"<{len(secret)} chars>"


@dataclass(frozen=True, repr=False)
class Candidate:
    """A single password candidate extracted from a body of text.

    Immutable value object. :attr:`confidence` is a heuristic score in the
    range ``0.0`` - ``1.0`` describing how likely this string is to be the
    intended password. It is used to rank candidates when a text contains more
    than one.

    :param password:   The extracted password.
    :param confidence: Heuristic score, ``0.0`` (unlikely) - ``1.0`` (very likely).
    :param keyword:    The keyword that triggered the match (e.g. ``"password"``).
    :param context:    A short snippet of surrounding text for debugging/review.
    :param offset:     Character offset of the password within the normalised text.
    :param pattern:    Which match strategy fired: ``strict``/``loose``/``wrapped``/``nextline``.
    :param span:       ``(start, end)`` character span of the password in the normalised text.
    """

    password: str
    confidence: float
    keyword: str
    context: str
    offset: int
    pattern: str = ""
    span: tuple[int, int] = (-1, -1)

    def __repr__(self) -> str:
        """Masked representation.

        A candidate holds a live secret, and ``repr`` is what ends up in log
        lines, tracebacks and test failure output, none of which should carry
        it. ``context`` is masked too: it quotes the surrounding message. Reach
        for :attr:`password` or :meth:`to_dict` to get the real values.
        """
        return (
            f"Candidate(password={_mask(self.password)}, "
            f"confidence={self.confidence!r}, keyword={self.keyword!r}, "
            f"context={_mask(self.context)}, offset={self.offset!r}, "
            f"pattern={self.pattern!r}, span={self.span!r})"
        )

    def __str__(self) -> str:
        return self.password

    def to_dict(self) -> dict:
        """Return the candidate as a plain dictionary."""
        return {
            "password": self.password,
            "confidence": self.confidence,
            "keyword": self.keyword,
            "context": self.context,
            "offset": self.offset,
            "pattern": self.pattern,
            "span": self.span,
        }
