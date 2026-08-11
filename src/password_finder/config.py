"""Tunable configuration for :class:`password_finder.PasswordFinder`.

Everything the finder uses to make decisions -- the trigger keywords and their
base scores, the filler/reject word lists, and every numeric weight in the
scoring function -- lives here so it can be adjusted (per customer, per corpus)
without editing the engine. Pass a customised :class:`FinderConfig` to the
finder's ``config=`` argument.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

__all__ = ["Weights", "FinderConfig", "DEFAULT_KEYWORDS", "DEFAULT_FILLER_WORDS", "DEFAULT_REJECT_TOKENS"]


#: Keyword => base confidence (0.0 - 1.0).
#:
#: Longer / more specific spellings score higher than vague ones such as
#: "pin", "code" or "secret" which produce many false positives. A single space
#: in a keyword also matches a hyphen or nothing ("pass phrase" == "pass-phrase"
#: == "passphrase"); the same applies to hyphens ("one-time" == "one time").
DEFAULT_KEYWORDS: dict[str, float] = {
    # Strongest, most explicit spellings.
    "passphrase": 0.78,
    "pass phrase": 0.78,
    "passcode": 0.76,
    "pass code": 0.76,
    "password": 0.75,
    "temporary password": 0.75,
    "one-time password": 0.75,
    "pass word": 0.72,
    # Credential-style phrasings.
    "login credentials": 0.66,
    "credentials": 0.60,
    "access code": 0.64,
    "unlock code": 0.64,
    "authentication code": 0.64,
    "auth code": 0.60,
    "security code": 0.60,
    "one-time code": 0.62,
    "one-time pin": 0.60,
    "otp": 0.60,
    "memorable word": 0.55,
    "pwd": 0.55,
    "p/w": 0.55,
    # Localised spellings (German, French, Spanish).
    "kennwort": 0.72,
    "passwort": 0.72,
    "mot de passe": 0.75,
    "code d'accès": 0.64,
    "code d'acces": 0.64,
    "contraseña": 0.75,
    "contrasena": 0.75,
    "clave": 0.60,
    # Weak / ambiguous -- kept last, low base score.
    "code": 0.50,
    "pin": 0.45,
    "secret": 0.40,
}


#: Words allowed to appear between the keyword and the password value in the
#: "strict" pattern, e.g. "the password >>for opening the protected mail
#: content<< is ...". Curated so the matcher does not greedily swallow the
#: password itself.
DEFAULT_FILLER_WORDS: tuple[str, ...] = (
    "to", "the", "your", "this", "that", "a", "an", "of", "for", "on",
    "in", "and", "you", "it", "we", "i", "will", "shall", "would", "can",
    "need", "needed", "require", "required", "use", "using", "used",
    "open", "opening", "unlock", "unlocking", "view", "read", "access",
    "accessing", "decrypt", "attached", "attachment", "attachments",
    "file", "files", "document", "documents", "doc", "zip", "pdf",
    "archive", "folder", "below", "following", "above", "here", "as",
    "be", "been", "set", "each", "both", "them", "these", "those",
    "protected", "secure", "secured", "encrypt", "encrypted", "mail",
    "e-mail", "email", "content", "contents", "message", "information",
    "info", "policy", "link", "item", "portal", "sent", "via", "is",
    # Common connective words seen ahead of a value in real messages.
    "temporary", "memorable", "login", "new", "one", "two", "three", "four",
    "first", "second", "third", "fourth", "same",
)


#: Tokens that are never a password even when they follow a keyword. Guards
#: against phrases like "password is attached" or "password: reset".
DEFAULT_REJECT_TOKENS: frozenset[str] = frozenset({
    # Grammatical / structural noise.
    "is", "are", "be", "the", "a", "an", "to", "as", "below", "above",
    "attached", "attachment", "here", "follows", "following", "same",
    "provided", "sent", "separately", "separate", "and", "or", "will",
    "protected", "required", "needed", "blank", "empty", "none", "n/a",
    "na", "tbc", "tba", "if", "in", "on", "of", "for", "this", "that",
    # UI / call-to-action words that follow "password" in web/app emails.
    "reset", "change", "changed", "forgotten", "forgot", "click", "login",
    "logon", "help", "settings", "manage", "manager", "update", "updated",
    "expired", "expires", "invalid", "incorrect", "unavailable", "enter",
    "download", "regards", "sincerely", "thanks", "copyright", "enquiries",
    "team", "support", "www", "http", "https",
    # Boilerplate around the password in delivery emails: "the password is
    # CASE SENSITIVE", "password below", etc.
    "case", "sensitive",
})


@dataclass(frozen=True)
class Weights:
    """Every numeric knob in the scoring function.

    Defaults reproduce the original heuristic; adjust to re-tune ranking.
    """

    # Per-pattern base modifier (applied on top of the keyword score).
    strict_mod: float = 0.0
    loose_mod: float = -0.15
    wrapped_mod: float = 0.02
    nextline_mod: float = -0.22
    delimited_mod: float = -0.05  # value set off in quotes/emphasis, no connector

    # Connector signals.
    colon_bonus: float = 0.15          # an explicit ":" or "=" ("value follows")
    soft_connector_bonus: float = 0.06  # a word connector such as "is"
    no_connector_penalty: float = 0.05

    # Filler between keyword and value (word count).
    filler_word_penalty: float = 0.03
    filler_penalty_cap: float = 0.12

    # Proximity: raw character distance between keyword and value.
    distance_free_chars: int = 12
    distance_penalty_per_char: float = 0.004
    distance_penalty_cap: float = 0.12

    # Token shape.
    good_length_bonus: float = 0.08     # 6-40 chars looks like a real secret
    short_penalty: float = 0.15         # < 4 chars
    class_bonus_per_class: float = 0.045  # per character class beyond the first
    entropy_scale: float = 0.02         # * Shannon entropy (bits), capped
    entropy_cap: float = 4.0
    lowercase_word_penalty: float = 0.08  # looks like a plain dictionary word
    wrapped_value_bonus: float = 0.08   # value was quoted/bracketed (deliberate)
    reference_number_penalty: float = 0.25  # long pure-digit run (ref/policy no.)
    reference_number_min_digits: int = 11

    # Score bounds and fallback.
    default_keyword_score: float = 0.6
    min_score: float = 0.05
    max_score: float = 0.99


@dataclass(frozen=True)
class FinderConfig:
    """Bundle of everything the finder needs. All fields have sensible defaults."""

    keywords: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_KEYWORDS))
    filler_words: tuple[str, ...] = DEFAULT_FILLER_WORDS
    reject_tokens: frozenset[str] = DEFAULT_REJECT_TOKENS
    weights: Weights = field(default_factory=Weights)

    def with_extra_keywords(self, extra: list[str], score: float = 0.6) -> "FinderConfig":
        """Return a copy with additional trigger keywords merged in."""
        merged = dict(self.keywords)
        for kw in extra:
            kw = str(kw).strip()
            if kw:
                merged.setdefault(kw, score)
        return replace(self, keywords=merged)
