"""Corpus-wide quality metrics, as a regression gate.

The per-file tests answer "is the right password on top?". They cannot see a
change that keeps every answer correct while eroding the margin between the
real password and the runners-up, or one that starts emitting extra candidates
alongside the right one. Both make the library worse for a caller applying a
confidence threshold, and both pass the per-file suite unchanged.

This module measures those properties across every corpus and holds them at
their current level. The floors are deliberately tight: they are meant to fail
when a scoring change costs accuracy, at which point the number is either
restored or moved deliberately, with the reason recorded in the commit.

Only aggregates are reported. No fixture password is ever printed, so this is
safe to run against the git-ignored private corpus too.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from password_finder import PasswordFinder

TESTS = Path(__file__).parent

# Separator between multiple expected passwords in a fixture file name.
SEPARATOR = "-OR-"

# A caller acting on a candidate at or above this would be misled by it.
THRESHOLD = 0.5

# Current measured levels, held as floors/ceilings. Raise a floor when the
# library improves; lower one only with a stated reason.
MIN_TOP_N_ACCURACY = 1.0        # expected passwords are exactly the top N
MIN_RECALL = 1.0                # expected passwords appear somewhere

# Worst gap between a real password and the best thing competing with it. The
# tightest case in the corpus is a reply-chain message that deliberately carries
# a superseded password below the current one; that gap is set by
# ``quoted_history_penalty`` and is a designed distance, not a precision
# problem, so the floor sits just under it.
MIN_SEPARATION = 0.14

# Share of positive files emitting a candidate that is not an expected password.
# A rate rather than a count: the corpus grows, and an absolute number would
# need raising on every addition, which turns the gate into noise. One of the
# files counted here is the reply-chain message, whose extra candidate is the
# superseded password and therefore correct.
MAX_NOISY_RATE = 0.05

# Headroom below the confidence at which a caller would act (``THRESHOLD``).
# Messages with no password may still produce a low-scoring candidate; what
# matters is that nothing in them comes close to looking convincing.
MAX_NEGATIVE_CONFIDENCE = 0.35


def _fixtures(directory: str) -> list[Path]:
    path = TESTS / directory
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*") if p.suffix in {".txt", ".html"})


def _expected_from_name(fixture: Path) -> list[str]:
    return fixture.stem.split(SEPARATOR)


def _expected_from_first_line(fixture: Path) -> tuple[list[str], str]:
    """The special-character corpus states its password on the first line."""
    raw = fixture.read_text(encoding="utf-8")
    expected, _, body = raw.partition("\n")
    return [expected.strip()], body


def _cases() -> list[tuple[list[str], str]]:
    """Every positive fixture as ``(expected_passwords, body)``."""
    cases = []

    for directory in ("emails", "emails-private"):
        for fixture in _fixtures(directory):
            cases.append(
                (_expected_from_name(fixture), fixture.read_text(encoding="utf-8"))
            )

    for fixture in _fixtures("emails-special-characters"):
        cases.append(_expected_from_first_line(fixture))

    return cases


class Metrics:
    """Aggregate scores over the positive corpora."""

    def __init__(self) -> None:
        finder = PasswordFinder()

        self.total = 0
        self.exact_top_n = 0
        self.recalled = 0
        self.noisy = 0
        self.separations: list[float] = []

        for expected, body in _cases():
            candidates = finder.find_all(body)
            found = [c.password for c in candidates]

            self.total += 1

            if set(found[: len(expected)]) == set(expected):
                self.exact_top_n += 1

            if all(e in found for e in expected):
                self.recalled += 1

            wanted = [c.confidence for c in candidates if c.password in expected]
            others = [c.confidence for c in candidates if c.password not in expected]

            if others:
                self.noisy += 1

            if wanted:
                self.separations.append(min(wanted) - (max(others) if others else 0.0))

    @property
    def top_n_accuracy(self) -> float:
        return self.exact_top_n / self.total

    @property
    def recall(self) -> float:
        return self.recalled / self.total

    @property
    def worst_separation(self) -> float:
        return min(self.separations)

    @property
    def noisy_rate(self) -> float:
        return self.noisy / self.total

    def report(self) -> str:
        return (
            f"{self.total} positive fixture(s): "
            f"top-N {self.top_n_accuracy:.1%}, recall {self.recall:.1%}, "
            f"separation min {self.worst_separation:.3f} "
            f"mean {statistics.mean(self.separations):.3f}, "
            f"{self.noisy} file(s) with a spurious candidate "
            f"({self.noisy_rate:.1%})"
        )


@pytest.fixture(scope="module")
def metrics() -> Metrics:
    return Metrics()


def test_corpus_is_not_empty(metrics: Metrics) -> None:
    assert metrics.total >= 90, f"Unexpectedly few fixtures: {metrics.report()}"


def test_top_n_accuracy_holds(metrics: Metrics) -> None:
    assert metrics.top_n_accuracy >= MIN_TOP_N_ACCURACY, metrics.report()


def test_recall_holds(metrics: Metrics) -> None:
    assert metrics.recall >= MIN_RECALL, metrics.report()


def test_separation_from_noise_holds(metrics: Metrics) -> None:
    # The real password must stay clearly ahead of the best runner-up, not
    # merely ahead of it.
    assert metrics.worst_separation >= MIN_SEPARATION, metrics.report()


def test_spurious_candidates_do_not_spread(metrics: Metrics) -> None:
    # Extra candidates alongside a correct answer cost the caller attempts.
    assert metrics.noisy_rate <= MAX_NOISY_RATE, metrics.report()


def test_negative_corpus_stays_silent() -> None:
    finder = PasswordFinder()
    highest = 0.0

    for fixture in _fixtures("emails_negative"):
        candidates = finder.find_all(fixture.read_text(encoding="utf-8"))
        if candidates:
            highest = max(highest, max(c.confidence for c in candidates))

    assert highest <= MAX_NEGATIVE_CONFIDENCE, (
        f"A message with no password scored {highest:.3f}, leaving too little "
        f"headroom below {THRESHOLD}, the point at which a caller would act."
    )


if __name__ == "__main__":  # pragma: no cover - on-demand report
    print(Metrics().report())
