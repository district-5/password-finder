"""Property-based tests: invariants that must hold for any input at all.

The example-based suite checks messages we thought of. These check the things
that must be true regardless: the finder never raises on arbitrary text, never
invents a password that is not in the input, never reports a confidence outside
its own bounds, and never takes superlinear time on hostile input.

Hypothesis is a development dependency (``pip install -e ".[dev]"``). The
module skips rather than fails when it is absent, so the rest of the suite
still runs in a bare environment.
"""

from __future__ import annotations

import time

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from password_finder import PasswordFinder, Weights  # noqa: E402
from password_finder.config import DEFAULT_KEYWORDS  # noqa: E402

FINDER = PasswordFinder()

# Printable ASCII keeps the "password came from the input" property meaningful:
# stripping invisible characters legitimately rewrites the text, so a token can
# be absent from the raw input without anything being wrong.
PRINTABLE = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    max_size=400,
)

KEYWORDS = sorted(DEFAULT_KEYWORDS)

# Text built to actually trigger matches, rather than relying on a random
# string happening to contain a keyword.
MESSAGES = st.builds(
    lambda before, keyword, connector, value, after: (
        f"{before} {keyword}{connector} {value} {after}"
    ),
    before=PRINTABLE,
    keyword=st.sampled_from(KEYWORDS),
    connector=st.sampled_from([":", " is", " =", "", " -->"]),
    value=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=40,
    ),
    after=PRINTABLE,
)

SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@SETTINGS
@given(st.text(max_size=2000))
def test_never_raises_on_arbitrary_text(text: str) -> None:
    FINDER.find_all(text)


@SETTINGS
@given(MESSAGES)
def test_never_raises_on_message_shaped_text(text: str) -> None:
    FINDER.find_all(text)


@SETTINGS
@given(MESSAGES)
def test_confidence_stays_within_bounds(text: str) -> None:
    weights = Weights()
    for candidate in FINDER.find_all(text):
        assert weights.min_score <= candidate.confidence <= weights.max_score


@SETTINGS
@given(PRINTABLE)
def test_password_always_comes_from_the_input(text: str) -> None:
    # Nothing may be invented. Printable ASCII only, so normalisation does not
    # legitimately rewrite the text underneath us.
    for candidate in FINDER.find_all(text):
        assert candidate.password in text


@SETTINGS
@given(MESSAGES)
def test_span_locates_the_password_in_the_input(text: str) -> None:
    normalised = FINDER._normalise(text)
    for candidate in FINDER.find_all(text):
        start, end = candidate.span
        assert 0 <= start < end <= len(normalised)
        # The span covers the raw token, which trimming may have shortened.
        assert candidate.password in normalised[start:end]


@SETTINGS
@given(MESSAGES)
def test_results_are_ranked_and_unique(text: str) -> None:
    candidates = FINDER.find_all(text)

    passwords = [c.password for c in candidates]
    assert len(passwords) == len(set(passwords)), "duplicate candidate"

    confidences = [c.confidence for c in candidates]
    assert confidences == sorted(confidences, reverse=True), "not ranked"


@SETTINGS
@given(st.text(max_size=2000))
def test_repr_never_leaks_a_password(text: str) -> None:
    for candidate in FINDER.find_all(text):
        assert candidate.password not in repr(candidate)


@SETTINGS
@given(MESSAGES)
def test_finding_is_repeatable(text: str) -> None:
    assert FINDER.find_passwords(text) == PasswordFinder().find_passwords(text)


@pytest.mark.parametrize(
    "label,text",
    [
        # Shapes that stress the nested quantifiers in the match patterns.
        ("filler repetition", "password" + " the" * 2000),
        ("keyword repetition", "password: " * 2000),
        ("long unbroken run", "password " + "Aa1" * 20_000),
        ("quote storm", 'password ' + '"a b' * 5_000),
        ("newline storm", "password\n" * 5_000),
        ("bracket nesting", "password " + "(" * 5_000 + "x"),
        ("colon storm", "password" + ":" * 20_000 + "x"),
    ],
)
def test_hostile_input_stays_fast(label: str, text: str) -> None:
    # Catastrophic backtracking would blow up here rather than degrade. The
    # bound is generous: the point is to catch exponential behaviour, not to
    # benchmark. Every pattern must keep its quantifiers bounded for this to
    # keep holding.
    start = time.perf_counter()
    FINDER.find_all(text)
    elapsed = time.perf_counter() - start

    assert elapsed < 5.0, f"{label} took {elapsed:.2f}s on {len(text)} chars"
