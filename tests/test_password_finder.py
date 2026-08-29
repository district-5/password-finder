"""Unit tests for :class:`password_finder.PasswordFinder`.

Ported from the PHP ``PasswordFinderTest`` suite. All example passwords here
are freshly invented test data -- they are not real credentials.
"""

from __future__ import annotations

import pytest

import password_finder
from password_finder import (
    DEFAULT_REJECT_TOKENS,
    Candidate,
    FinderConfig,
    PasswordFinder,
    Weights,
)


@pytest.fixture()
def finder() -> PasswordFinder:
    return PasswordFinder()


def best(finder: PasswordFinder, text: str) -> str | None:
    """Best (top-ranked) password string, or None when nothing was found."""
    candidates = finder.find_all(text)
    return candidates[0].password if candidates else None


EXTRACTION_CASES = [
    ("colon", "Password: Sunshine42", "Sunshine42"),
    ("is", "The password is Hunter2!", "Hunter2!"),
    ("equals", "pwd=Zx9$kLm", "Zx9$kLm"),
    ("quoted double", 'Your password is "Blue-Sky-88".', "Blue-Sky-88"),
    ("quoted single", "The password is 'p@ssW0rd'", "p@ssW0rd"),
    ("markdown bold", "Password: **Tr0ub4dour**", "Tr0ub4dour"),
    (
        "filler words",
        "The password to open the attached document is Q7wE9rT2.",
        "Q7wE9rT2",
    ),
    ("passcode", "Passcode for the zip: 4417-AB", "4417-AB"),
    ("passphrase", "Use passphrase: correct-horse-battery", "correct-horse-battery"),
    ("trailing sentence", "The password is aB3dEf.", "aB3dEf"),
    (
        "on next line",
        "Please find attached.\n\nPassword:\nSecretPass99\n\nRegards",
        "SecretPass99",
    ),
    ("is colon combo", "Password is: MyKey2024", "MyKey2024"),
    ("parenthesised", "The password (Zap!123) unlocks the file.", "Zap!123"),
    ("pin", "Your PIN is 8842", "8842"),
    ("case insensitive keyword", "PASSWORD: LoudPass1", "LoudPass1"),
]


@pytest.mark.parametrize(
    "text,expected",
    [(text, expected) for _name, text, expected in EXTRACTION_CASES],
    ids=[name for name, _text, _expected in EXTRACTION_CASES],
)
def test_extracts_expected_password(finder: PasswordFinder, text: str, expected: str) -> None:
    assert best(finder, text) == expected, f"Failed to extract from: {text}"


def test_returns_empty_list_when_no_password(finder: PasswordFinder) -> None:
    assert finder.find_all("Hello, please see the attached invoice. Thanks.") == []


def test_rejects_non_password_following_keyword(finder: PasswordFinder) -> None:
    assert finder.find_all("The password is attached in a separate email.") == []


def test_ranks_higher_confidence_first(finder: PasswordFinder) -> None:
    # A weak "secret word" mention plus a strong explicit password line.
    text = "Secret santa word: elf\nThe password for the file is: Vault#2024x"
    all_ = finder.find_all(text)

    assert all_
    assert all_[0].password == "Vault#2024x"


def test_find_all_returns_ranked_candidates(finder: PasswordFinder) -> None:
    text = "Password: FirstOne99\nAlso the pin is 1234"
    all_ = finder.find_all(text)

    assert len(all_) >= 2
    # Explicit "password:" should outrank a bare pin.
    assert all_[0].password == "FirstOne99"
    assert all_[0].confidence > all_[1].confidence


def test_deduplicates_identical_passwords(finder: PasswordFinder) -> None:
    text = "Password: SamePass1. Reminder — the password is SamePass1."
    all_ = finder.find_all(text)

    passwords = [c.password for c in all_]
    assert list(dict.fromkeys(passwords)) == ["SamePass1"]
    assert len(all_) == 1


def test_candidate_exposes_context_and_confidence(finder: PasswordFinder) -> None:
    all_ = finder.find_all("The password is Kestrel#7 for the report.")
    c = all_[0] if all_ else None

    assert c is not None
    assert c.password == "Kestrel#7"
    assert c.confidence > 0.7
    assert "password" in c.context.lower()


def test_respects_min_length() -> None:
    finder = PasswordFinder(min_length=6)
    assert finder.find_all("Password: ab12") == []

    all_ = finder.find_all("Password: abc123")
    assert (all_[0].password if all_ else None) == "abc123"


def test_find_passwords_returns_ranked_strings(finder: PasswordFinder) -> None:
    passwords = finder.find_passwords("Password: FirstOne99\nAlso the pin is 1234")

    assert isinstance(passwords, list)
    assert passwords[0] == "FirstOne99"


def test_html_body_is_decoded(finder: PasswordFinder) -> None:
    html = "<p>Please use this password for opening the file: <b>Zx9&amp;kLm</b></p>"
    all_ = finder.find_all(html)

    assert all_
    assert all_[0].password == "Zx9&kLm"


def test_candidate_to_dict_and_str(finder: PasswordFinder) -> None:
    c = finder.find_all("Password: Sunshine42")[0]

    assert str(c) == "Sunshine42"
    data = c.to_dict()
    assert data["password"] == "Sunshine42"
    assert set(data) == {"password", "confidence", "keyword", "context", "offset", "pattern", "span"}
    assert data["pattern"] in {"strict", "loose", "wrapped", "nextline"}
    assert data["span"] == (c.offset, c.offset + len("Sunshine42"))
    assert isinstance(c, Candidate)


def test_extra_keywords_are_honoured() -> None:
    # "sésame" is not a built-in trigger; it should be picked up when added.
    plain = PasswordFinder()
    assert plain.find_all("Sésame: Geheim99") == []

    extended = PasswordFinder(extra_keywords=["sésame"])
    assert extended.find_all("Sésame: Geheim99")[0].password == "Geheim99"


# --------------------------------------------------------------------------- #
# Coverage improvements: new phrasings and layouts that used to be missed.     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Your one-time code is Jw5Kd9r", "Jw5Kd9r"),
        ("authentication code: Vb9Tz2r", "Vb9Tz2r"),
        ("temporary password: Rk9Tm4w", "Rk9Tm4w"),
        ("login credentials: Fp2Ns7Lb", "Fp2Ns7Lb"),
        ("security code = Zx6Lb3q", "Zx6Lb3q"),
        # Localised keywords now built in.
        ("Mot de passe : Cq8Vn3Xt", "Cq8Vn3Xt"),
        ("Kennwort: Wn7Kq2Jd", "Wn7Kq2Jd"),
        ("Contraseña: Mv3Rt6Zx", "Mv3Rt6Zx"),
    ],
)
def test_new_and_localised_keywords(finder: PasswordFinder, text: str, expected: str) -> None:
    assert finder.find_all(text)[0].password == expected


def test_keyword_alone_then_value_on_next_line(finder: PasswordFinder) -> None:
    # Keyword on its own line, no connector, value on a following line.
    text = "Please open the attached file.\n\nPassword\n\nKp7mXq2\n\nRegards"
    result = finder.find_all(text)
    assert result[0].password == "Kp7mXq2"
    assert result[0].pattern == "nextline"


def test_adjacent_html_table_cells(finder: PasswordFinder) -> None:
    html = "<table><tr><td>Password</td><td>Zx9kLm2</td></tr></table>"
    assert finder.find_passwords(html) == ["Zx9kLm2"]


def test_hyphen_and_space_keyword_variants(finder: PasswordFinder) -> None:
    for spelling in ("one-time code", "one time code", "onetime code"):
        assert finder.find_all(f"Your {spelling} is Jw5Kd9r")[0].password == "Jw5Kd9r"


# --------------------------------------------------------------------------- #
# Precision improvements: non-password shapes are rejected.                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        "The password is https://example.com/reset",
        "The password is www.example.com/reset",
        "For your access code, email: support@example.com",
        "Your appointment code is: 12/03/2026",
        "Meeting passcode: 14:30",
        "Secret sale price: $1,299.00",
        "Access code line: 0800-123-4567",
    ],
)
def test_rejects_non_password_shapes(finder: PasswordFinder, text: str) -> None:
    assert finder.find_all(text) == []


def test_reference_number_is_downranked(finder: PasswordFinder) -> None:
    # A generated-looking password should outrank a long pure-digit reference.
    text = "Your password is Ab3$kLm9. Reference code: 123456789012"
    result = finder.find_all(text)
    assert result[0].password == "Ab3$kLm9"
    ref = next((c for c in result if c.password == "123456789012"), None)
    if ref is not None:
        assert ref.confidence < result[0].confidence


def test_entropy_and_class_diversity_outranks_plain_word(finder: PasswordFinder) -> None:
    # Two equally-triggered candidates; the mixed-class one should win.
    text = "First password: sunshine\nSecond password: X7#kR2mQ"
    result = finder.find_all(text)
    assert result[0].password == "X7#kR2mQ"


def test_quoted_value_beats_bare_value(finder: PasswordFinder) -> None:
    # Same weak keyword/value (kept below the score cap); the deliberately
    # quoted value should score higher than the bare one.
    quoted = finder.find_all('secret: "banana"')[0].confidence
    bare = finder.find_all("secret: banana")[0].confidence
    assert quoted > bare


# --------------------------------------------------------------------------- #
# Config-driven behaviour.                                                     #
# --------------------------------------------------------------------------- #


def test_custom_config_overrides_keywords_and_weights() -> None:
    config = FinderConfig(
        keywords={"magicword": 0.9},
        weights=Weights(colon_bonus=0.0, good_length_bonus=0.0),
    )
    finder = PasswordFinder(config=config)

    # The custom keyword works...
    assert finder.find_all("magicword: Hunter2")[0].password == "Hunter2"
    # ...and a default keyword no longer triggers (not in the custom set).
    assert finder.find_all("password: Hunter2") == []


def test_extra_keywords_merge_onto_custom_config() -> None:
    config = FinderConfig(keywords={"magicword": 0.9})
    finder = PasswordFinder(extra_keywords=["token"], config=config)
    assert finder.find_all("token: Hunter2")[0].password == "Hunter2"
    assert finder.find_all("magicword: Hunter2")[0].password == "Hunter2"


# --------------------------------------------------------------------------- #
# Blacklisting: words that must never be returned as a password.              #
# --------------------------------------------------------------------------- #


def test_extra_reject_tokens_blacklist_a_word() -> None:
    text = "The password is prompted"

    # Without the blacklist the word is happily returned...
    assert PasswordFinder().find_all(text)[0].password == "prompted"

    # ...and with it, nothing is found at all.
    assert PasswordFinder(extra_reject_tokens=["prompted"]).find_all(text) == []


def test_extra_reject_tokens_are_case_insensitive() -> None:
    # Blacklist entry and text differ in case, and the value carries trailing
    # sentence punctuation -- rejection happens after trimming, so it still bites.
    finder = PasswordFinder(extra_reject_tokens=["Accessible"])
    assert finder.find_all("The password is accessible.") == []
    assert finder.find_all("The password is ACCESSIBLE") == []


def test_extra_reject_tokens_keep_the_defaults() -> None:
    finder = PasswordFinder(extra_reject_tokens=["prompted"])
    # A default reject token still applies alongside the added one.
    assert finder.find_all("The password will be emailed") == []
    # ...and a real password is unaffected by either.
    assert finder.find_all("The password is Hunter2!")[0].password == "Hunter2!"


def test_extra_reject_tokens_merge_onto_custom_config() -> None:
    config = FinderConfig(reject_tokens=frozenset({"widget"}))
    finder = PasswordFinder(extra_reject_tokens=["prompted"], config=config)
    assert finder.find_all("The password is widget") == []
    assert finder.find_all("The password is prompted") == []


def test_with_extra_reject_tokens_returns_a_merged_copy() -> None:
    config = FinderConfig()
    merged = config.with_extra_reject_tokens(["Prompted", " accessible ", ""])

    assert {"prompted", "accessible"} <= merged.reject_tokens  # normalised
    assert DEFAULT_REJECT_TOKENS <= merged.reject_tokens       # defaults kept
    assert "" not in merged.reject_tokens                      # blanks dropped
    assert config.reject_tokens == DEFAULT_REJECT_TOKENS        # original intact


def test_reject_tokens_can_be_replaced_wholesale() -> None:
    # Passing reject_tokens= (rather than merging) drops the defaults.
    finder = PasswordFinder(config=FinderConfig(reject_tokens=frozenset({"prompted"})))
    assert finder.find_all("The password is prompted") == []
    assert finder.find_all("The password is emailed")[0].password == "emailed"


# --------------------------------------------------------------------------- #
# Word-shaped tokens: downranked so a real password outranks them.            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        "The password is prompted",       # lower case
        "The password is Prompted",       # capitalised, as a sentence starts
        "The password is PROMPTED",       # upper case
        "Your passcode is Accessible",
    ],
)
def test_ordinary_words_score_below_the_useful_threshold(text: str) -> None:
    # A capitalised word used to score the maximum, because the single-case
    # test missed title case. Nothing word-shaped should look convincing.
    candidates = PasswordFinder().find_all(text)
    assert all(c.confidence < 0.7 for c in candidates), [
        (c.password, c.confidence) for c in candidates
    ]


def test_real_password_outranks_a_word_in_the_same_message() -> None:
    text = "The password is Prompted. Sorry, the password is Kp7mXq2!"
    result = PasswordFinder().find_all(text)
    assert result[0].password == "Kp7mXq2!"
    assert result[0].confidence > result[1].confidence


def test_mixed_case_alpha_password_is_not_penalised() -> None:
    # "aTlKeiEa" does not read as a word, so neither penalty should apply.
    plain = PasswordFinder().find_all("Your pin is aTlKeiEa")[0]
    worded = PasswordFinder().find_all("Your pin is Prompted")[0]
    assert plain.confidence > worded.confidence


def test_dictionary_words_are_configurable() -> None:
    # Downranking is a soft signal, so it can be turned off entirely.
    config = FinderConfig(dictionary_words=frozenset())
    relaxed = PasswordFinder(config=config).find_all("The password is prompted")[0]
    default = PasswordFinder().find_all("The password is prompted")[0]
    assert relaxed.confidence > default.confidence


# --------------------------------------------------------------------------- #
# Invisible characters: never part of a password, stripped before matching.   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "label,text",
    [
        ("zero width space", "The password is Ab12\u200bCd34"),
        ("zero width non-joiner", "The password is Ab12\u200cCd34"),
        ("soft hyphen", "The password is Ab12\u00adCd34"),
        ("left-to-right mark", "The password is Ab12\u200eCd34"),
        ("bidi override", "The password is Ab12\u202dCd34"),
        ("word joiner", "The password is Ab12\u2060Cd34"),
        ("byte order mark", "The password is Ab12\ufeffCd34"),
    ],
)
def test_invisible_characters_are_stripped(label: str, text: str) -> None:
    # Without stripping these survive into the token, giving a password that
    # looks correct on screen and fails when pasted.
    assert PasswordFinder().find_passwords(text) == ["Ab12Cd34"]


def test_invisible_html_entity_is_stripped() -> None:
    # Decoded to U+200B by html.unescape, so stripping has to run afterwards.
    html_body = "<p>The password is Ab12&#8203;Cd34</p>"
    assert PasswordFinder().find_passwords(html_body) == ["Ab12Cd34"]


def test_invisible_characters_are_stripped_from_plain_text_too() -> None:
    # Stripping is independent of HTML decoding, so it still applies when
    # decoding is turned off.
    finder = PasswordFinder(decode_html=False)
    assert finder.find_passwords("The password is Ab12\u200bCd34") == ["Ab12Cd34"]


def test_non_breaking_space_acts_as_a_separator() -> None:
    # A non-breaking space is layout, not password content: it separates the
    # connector from the value rather than being captured inside it.
    finder = PasswordFinder()
    assert finder.find_passwords("Password:\u00a0Ab12Cd34") == ["Ab12Cd34"]
    assert finder.find_passwords("The password is Ab12\u00a0Cd34") == ["Ab12"]


def test_unicode_line_separator_becomes_a_line_break() -> None:
    # U+2028 is a line break, so this is the "value on the next line" layout.
    assert PasswordFinder().find_passwords("Password\u2028Ab12Cd34") == ["Ab12Cd34"]


def test_module_level_helper_accepts_extra_reject_tokens() -> None:
    text = "The password is prompted"
    assert password_finder.find_passwords(text) == ["prompted"]
    assert password_finder.find_passwords(text, extra_reject_tokens=["prompted"]) == []


# --------------------------------------------------------------------------- #
# Automatic HTML detection + string-in API.                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,is_html",
    [
        ("<p>Password: <b>Secret1</b></p>", True),
        ("<!DOCTYPE html><html></html>", True),
        ("Password&nbsp;is&nbsp;Secret1", True),          # entities, no tags
        ("Total is 5 &lt; 10", True),
        ("The password is Secret1.", False),               # plain text
        ("Contact us at sales & marketing", False),        # bare & is not an entity
        ("", False),
    ],
)
def test_looks_like_html(text: str, is_html: bool) -> None:
    assert PasswordFinder.looks_like_html(text) is is_html


def test_same_finder_handles_html_and_text_automatically(finder: PasswordFinder) -> None:
    # No flag, no hint about the format -- the finder decides per input.
    html = "<p>Please use this password: <b>Zx9&amp;kLm</b></p>"
    plain = "Please use this password: Zx9&kLm"

    assert finder.find_passwords(html) == ["Zx9&kLm"]
    assert finder.find_passwords(plain) == ["Zx9&kLm"]


def test_module_level_helpers_take_a_string() -> None:
    # This mirrors how the fixture tests feed file contents: read -> string -> lib.
    assert password_finder.find_passwords("Password: Sunshine42") == ["Sunshine42"]

    candidates = password_finder.find_all("<p>passcode: <b>Kp7mXq2</b></p>")
    assert candidates[0].password == "Kp7mXq2"

    # Constructor options are forwarded through the helper.
    assert password_finder.find_passwords("Password: ab12", min_length=6) == []


def test_decode_html_can_be_disabled() -> None:
    finder = PasswordFinder(decode_html=False)
    html = "<p>password: <b>Secret1</b></p>"
    # With decoding off, the tag is glued to the value so it isn't a clean match.
    passwords = finder.find_passwords(html)
    assert "Secret1" not in passwords
