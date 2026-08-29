"""Extract likely passwords from free-form text (plain text or HTML bodies)."""

from __future__ import annotations

import html
import math
import re
from collections import Counter
from typing import Iterable, Match, Pattern

from .candidate import Candidate
from .config import FinderConfig

# --- Token shapes that are never a password (used to reject false positives) ---
_URL_RE = re.compile(r"(?i)^(?:https?://|ftp://|www\.)")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
_DATE_RE = re.compile(
    r"^(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2})$"
)
_CURRENCY_RE = re.compile(r"^[£$€¥]\d[\d,]*(?:\.\d+)?$")
_PHONE_RE = re.compile(r"^[+()\d.\-\s]+$")
# A domain-like "word.tld" optionally followed by a path -- catches whole URLs
# and the fragments the loose pattern can carve out of one at its internal ":".
_DOMAIN_RE = re.compile(r"(?i)[a-z0-9\-]{2,}\.[a-z]{2,}(?:/|$)")

_OPENERS = frozenset('"\'“‘*`([{<')

# Matching delimiter pairs for the "delimited" pattern: a value the sender set
# off in quotes / emphasis / brackets. Inner length >= 2 so junk like the "(s)"
# in "document(s)" is skipped in favour of the real value further along.
_DELIMITED_VALUE = (
    r'\*[^*\s]{2,160}\*'
    r'|"[^"\s]{2,160}"'
    r"|'[^'\s]{2,160}'"
    r'|`[^`\s]{2,160}`'
    r'|\([^)\s]{2,160}\)'
    r'|\[[^\]\s]{2,160}\]'
    r'|\{[^}\s]{2,160}\}'
    r'|“[^”\s]{2,160}”'
    r'|‘[^’\s]{2,160}’'
)

# Characters that render as nothing but survive into a captured token, giving a
# password that looks right on screen and pastes wrong: the soft hyphen, the
# zero-width space/joiner family, bidi controls, and the byte-order mark. Mail
# clients emit these routinely (often as "&shy;" or "&zwnj;"), and they are
# never part of a password, so they are removed before matching.
_INVISIBLE_RE = re.compile(
    "[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)
# Unicode line separators are line breaks, not token characters.
_LINE_SEPARATOR_RE = re.compile("[\u2028\u2029]")

# Used to decide, automatically, whether a string is HTML: a tag-shaped run, or
# an HTML entity (named, decimal, or hex).
_HTML_TAG_RE = re.compile(r"<\s*[a-z!/][^>]*>", re.IGNORECASE)
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);", re.IGNORECASE)


def _entropy(s: str) -> float:
    """Shannon entropy of a string in bits (higher == more random-looking)."""
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


class PasswordFinder:
    """Extracts likely passwords from free-form text (plain text or HTML email
    bodies).

    Typical use case: an encrypted attachment arrives in one email and the
    password to open it arrives in another, phrased in plain English -- e.g.
    *"please use this password for opening the protected mail content:
    Kp7mXq2"*. This library pulls ``"Kp7mXq2"`` back out.

    The finder is deliberately non-committal: it ALWAYS returns a list of
    candidates ranked by a heuristic confidence score, never a single string.
    When a message contains several plausible passwords they are all returned,
    most-likely first, so the caller can decide what to do.

    Usage::

        finder = PasswordFinder()

        for c in finder.find_all(email_body):   # list[Candidate] (may be empty)
            print(f"{c.password} ({c.confidence:.2f})")

        passwords = finder.find_passwords(email_body)  # list[str] ranked
    """

    def __init__(
        self,
        min_length: int = 3,
        max_length: int = 128,
        extra_keywords: Iterable[str] | None = None,
        decode_html: bool = True,
        config: FinderConfig | None = None,
        extra_reject_tokens: Iterable[str] | None = None,
    ) -> None:
        """
        :param min_length:     Passwords shorter than this (after trimming) are ignored.
        :param max_length:     Passwords longer than this are ignored (avoids grabbing URLs etc.).
        :param extra_keywords: Additional trigger keywords, each scored at 0.6.
        :param decode_html:    When ``True`` (default), the finder automatically
                               decides whether each string is HTML and, if so,
                               strips tags / decodes entities before matching --
                               callers never need to say which they are passing.
                               Set ``False`` to force plain-text handling.
        :param config:         Full :class:`FinderConfig` override (keywords, weights, ...).
                               ``extra_keywords`` and ``extra_reject_tokens`` are
                               merged on top of it.
        :param extra_reject_tokens:
                               Words to blacklist: never return these as a
                               password, however well they score. Merged with
                               :data:`~password_finder.DEFAULT_REJECT_TOKENS` and
                               matched case-insensitively against the whole
                               trimmed token, e.g. ``["prompted", "accessible"]``.
        """
        cfg = config if config is not None else FinderConfig()
        if extra_keywords:
            cfg = cfg.with_extra_keywords(list(extra_keywords))
        if extra_reject_tokens:
            cfg = cfg.with_extra_reject_tokens(extra_reject_tokens)
        self._cfg = cfg

        self._min_length = min_length
        self._max_length = max_length
        self._decode_html = decode_html
        self._patterns = self._build_patterns()

    # ------------------------------------------------------------------ API ---

    def find_all(self, text: str) -> list[Candidate]:
        """Return every candidate found, de-duplicated and ranked by confidence
        (highest first). Candidates with an identical password string are
        merged, keeping the highest-scoring occurrence. Always a list; empty if
        nothing plausible was found.
        """
        text = self._normalise(text)
        if text == "":
            return []

        # Keyed by password; the value carries the raw (unclamped) score used
        # for ranking alongside the candidate that reports the clamped one.
        by_password: dict[str, tuple[float, Candidate]] = {}

        for name, regex, mod in self._patterns:
            for m in regex.finditer(text):
                raw_token = self._group(m, "pw")
                token = self._trim_token(raw_token)

                if not self._is_plausible(token):
                    continue

                keyword = self._group(m, "keyword").strip().lower()
                connector = self._group(m, "connector").strip()
                filler = self._group(m, "filler").strip()
                start = m.start("pw")
                gap = max(0, start - m.end("keyword"))
                wrapped = raw_token[:1] in _OPENERS and raw_token != token

                raw = self._raw_score(token, keyword, connector, filler, gap, wrapped, mod)

                existing = by_password.get(token)
                if existing is None or raw > existing[0]:
                    by_password[token] = (
                        raw,
                        Candidate(
                            password=token,
                            confidence=self._clamp(raw),
                            keyword=keyword,
                            context=self._context(text, start, len(raw_token)),
                            offset=start,
                            pattern=name,
                            span=(start, start + len(raw_token)),
                        ),
                    )

        # Rank on the raw score, not the reported one. Several candidates
        # routinely clamp to the same ceiling, and ordering them by the clamped
        # value would leave the winner decided by pattern iteration order.
        # Remaining ties break towards the earliest mention, then the password
        # itself, so the ranking is total and reproducible.
        ranked = sorted(
            by_password.values(),
            key=lambda item: (-item[0], item[1].offset, item[1].password),
        )

        return self._drop_fragments([candidate for _, candidate in ranked])

    @staticmethod
    def _drop_fragments(ranked: list[Candidate]) -> list[Candidate]:
        """Remove candidates that are a fragment of a better-ranked one.

        Two patterns reading the same text can yield "Hunter2!" and "Hunter2",
        which are not two passwords but one password and a truncation of it.
        A candidate is dropped when a stronger candidate covers its position
        and contains its text; anything at a different position survives,
        because a message really can carry two similar passwords.
        """
        kept: list[Candidate] = []

        for candidate in ranked:
            start, end = candidate.span
            fragment = any(
                other.span[0] <= start
                and end <= other.span[1]
                and candidate.password in other.password
                for other in kept
            )
            if not fragment:
                kept.append(candidate)

        return kept

    def find_passwords(self, text: str) -> list[str]:
        """Return just the password strings, ranked by confidence (highest
        first). Always a list; empty if nothing plausible was found.
        """
        return [c.password for c in self.find_all(text)]

    # -------------------------------------------------------------- internals ---

    @staticmethod
    def _group(m: Match[str], name: str) -> str:
        """Named group value, or ``""`` when the group is absent/unmatched."""
        try:
            value = m.group(name)
        except IndexError:
            # Group not present in the pattern that produced this match.
            return ""
        return value if value is not None else ""

    def _build_patterns(self) -> list[tuple[str, Pattern[str], float]]:
        keywords = sorted(self._cfg.keywords.keys(), key=len, reverse=True)

        # A single space OR hyphen in a keyword also matches the other, or
        # nothing: "pass phrase" == "pass-phrase" == "passphrase";
        # "one-time" == "one time" == "onetime".
        sep = r"[\s\-]?"

        def compile_keyword(k: str) -> str:
            escaped = re.escape(k)
            for token in ("\\ ", " ", "\\-", "-"):
                escaped = escaped.replace(token, sep)
            return escaped

        kw = "|".join(compile_keyword(k) for k in keywords)
        fill = "|".join(re.escape(w) for w in self._cfg.filler_words)
        conn = r"[:=]+|\bis\b|\bare\b|\bwas\b|will\s+be|shall\s+be|would\s+be|to\s+use|-+>|:-"

        def filler(budget: int) -> str:
            """The run the delimited/proximity patterns allow between keyword
            and value: ``budget`` characters of the keyword's own line, or that
            plus a line break -- one blank line included, since senders
            routinely set the value on a paragraph of its own -- and ``budget``
            characters of the line the value sits on.

            Crossing the break requires the keyword's line to carry at least one
            more visible character ("... the password to open it.\\n\\nAb12Cd34").
            A keyword that ends its line is a label, and belongs to the
            "nextline" pattern, which scores that weaker layout accordingly.
            """
            same_line = r"[^\r\n]{0,%d}?" % budget
            break_ = r"[^\s\r\n][ \t]*\r?\n(?:[ \t]*\r?\n)?[ \t]*"
            return r"(?P<filler>%s|%s%s%s)" % (same_line, same_line, break_, same_line)

        open_ = "[\"'“‘*`(\\[{<]"

        flags = re.IGNORECASE | re.UNICODE
        w = self._cfg.weights

        return [
            # 1. Strict: keyword + curated filler words + an explicit connector.
            (
                "strict",
                re.compile(
                    r"\b(?P<keyword>%s)\b(?P<filler>(?:\s+(?:%s)\b){0,8})?[ \t]*"
                    r"(?P<connector>%s)[\s:=]*(?P<pw>\S{2,160})" % (kw, fill, conn),
                    flags,
                ),
                w.strict_mod,
            ),
            # 2. Loose: keyword + arbitrary same-line text up to a ":" or "=".
            (
                "loose",
                re.compile(
                    r"\b(?P<keyword>%s)\b(?P<filler>[^\n\r:=]{0,60}?)[ \t]*"
                    r"(?P<connector>[:=]+)[ \t]*(?P<pw>\S{2,160})" % kw,
                    flags,
                ),
                w.loose_mod,
            ),
            # 3. Wrapped: keyword immediately followed by a delimited value with
            #    no connector, e.g. password (Zap!123) or password "abc".
            (
                "wrapped",
                re.compile(
                    r"\b(?P<keyword>%s)\b[ \t]*(?P<pw>%s\S{1,159})" % (kw, open_),
                    flags,
                ),
                w.wrapped_mod,
            ),
            # 4. Next line: keyword (optionally with a bare connector) at the end
            #    of a line, and the value alone on a following line. Catches
            #    label/value layouts, incl. adjacent HTML table cells once
            #    </td>/</th> have been turned into line breaks by _normalise().
            (
                "nextline",
                re.compile(
                    r"\b(?P<keyword>%s)\b[ \t]*(?P<connector>[:=]?)[ \t]*\r?\n"
                    r"[ \t\r\n]*(?P<pw>\S{2,160})(?=[ \t]*\r?\n|[ \t]*$)" % kw,
                    flags,
                ),
                w.nextline_mod,
            ),
            # 5. Delimited: keyword followed -- within a short window that may
            #    cross a line break (including one blank line, so a value set on
            #    a paragraph of its own still counts) -- by a value the sender
            #    set off in quotes/emphasis/brackets, with no explicit
            #    connector. Catches natural-language sentences where the value
            #    sits a few words (or a sentence) after the keyword, e.g.
            #    "please use the following password to access the document(s).
            #    *Ab12Cd34*".
            (
                "delimited",
                re.compile(
                    r"\b(?P<keyword>%s)\b%s(?P<pw>%s)"
                    % (kw, filler(48), _DELIMITED_VALUE),
                    flags,
                ),
                w.delimited_mod,
            ),
            # 6. Proximity: keyword followed -- within a short window that may
            #    cross a line break (including one blank line) -- by a bare,
            #    undelimited token that is strongly password-shaped (contains
            #    BOTH a letter and a digit). A last-resort fallback for
            #    natural-language sentences with no connector and no delimiter,
            #    e.g. "please use the following password to access the file(s).
            #
            #    KRVBs699gqp3xeaq
            #
            #    Please note ...". Requiring a letter AND a digit keeps prose
            #    words (which never mix the two) from matching.
            (
                "proximity",
                re.compile(
                    r"\b(?P<keyword>%s)\b%s"
                    r"(?P<pw>(?=\S*[A-Za-z])(?=\S*\d)\S{4,160})" % (kw, filler(40)),
                    flags,
                ),
                w.proximity_mod,
            ),
        ]

    @staticmethod
    def looks_like_html(text: str) -> bool:
        """Return ``True`` when the string appears to be HTML rather than plain
        text -- it contains a tag-shaped run or an HTML entity. Used internally
        to decide automatically how to treat each input; exposed so callers can
        make the same decision if they need to.
        """
        return bool(_HTML_TAG_RE.search(text) or _HTML_ENTITY_RE.search(text))

    def _normalise(self, text: str) -> str:
        """Prepare a body for matching.

        HTML is turned into plain text so keyword matching works (skipped when
        the text does not look like HTML, or when decoding is disabled).
        Invisible characters are then stripped from whatever remains, including
        plain text, since they are never part of a password and would otherwise
        be captured inside one.
        """
        if text == "":
            return text

        # Automatically decide whether this string is HTML; leave plain text be.
        if self._decode_html and self.looks_like_html(text):
            text = self._strip_html(text)

        return self._strip_invisible(text)

    @staticmethod
    def _strip_invisible(text: str) -> str:
        """Remove zero-width/bidi characters and normalise exotic whitespace.

        Runs after entity decoding so an escaped "&#8203;" is caught too. A
        non-breaking space becomes an ordinary one: it is a separator wherever
        it appears, and the patterns match plain spaces.
        """
        text = _INVISIBLE_RE.sub("", text)
        text = _LINE_SEPARATOR_RE.sub("\n", text)
        return text.replace("\u00a0", " ")

    @staticmethod
    def _strip_html(text: str) -> str:
        """Turn an HTML body into plain text, keeping layout as line breaks."""
        # Drop <script>/<style> blocks (and HTML comments) entirely -- their
        # content is never body text and would otherwise leak CSS/JS noise.
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
        text = re.sub(
            r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Block-level and table-cell tags become line breaks so words don't run
        # together and label/value cells land on separate lines.
        text = re.sub(
            r"<\s*(?:br|/p|/div|/li|/tr|/td|/th|/h[1-6])\b[^>]*>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )
        # Inline emphasis (bold/italic/underline/highlight) is the HTML
        # equivalent of wrapping a value in *asterisks*: senders routinely
        # emphasise the password. Turn the tags into "*" so that signal
        # survives tag-stripping and the "delimited" pattern can use it.
        text = re.sub(
            r"<\s*/?\s*(?:b|strong|i|em|mark|u)\b[^>]*>",
            "*",
            text,
            flags=re.IGNORECASE,
        )
        # Strip any remaining tags.
        text = re.sub(r"<[^>]*>", "", text)

        return html.unescape(text)

    def _trim_token(self, token: str) -> str:
        """Strip surrounding quotes/markers and trailing sentence punctuation."""
        pairs = {
            '"': '"', "'": "'", "“": "”", "‘": "’",
            "`": "`", "(": ")", "[": "]", "{": "}", "<": ">", "*": "*",
        }
        stray_closers = (")", "]", "}", ">", '"', "'", "”", "’", "*", "`")
        stray_openers = ("(", "[", "{", "<", '"', "'", "“", "‘", "*", "`")

        while True:
            before = token

            # Matched wrapper pair around the whole token.
            if len(token) >= 2 and token[0] in pairs and pairs[token[0]] == token[-1]:
                token = token[1:-1]

            # Trailing sentence punctuation that is rarely part of a password.
            # Note: "!" and "?" are kept -- they are common password characters.
            token = token.rstrip(".,;:…")

            # Stray closing wrapper with no matching opener in the token.
            if token and token[-1] in stray_closers and not self._token_has_opener_for(token, token[-1]):
                token = token[:-1]

            # Stray opening wrapper at the start.
            if token and token[0] in stray_openers:
                token = token[1:]

            if token == before or token == "":
                break

        return token

    @staticmethod
    def _token_has_opener_for(token: str, closer: str) -> bool:
        openers = {")": "(", "]": "[", "}": "{", ">": "<"}
        opener = openers.get(closer)
        return opener is not None and opener in token

    def _is_plausible(self, token: str) -> bool:
        length = len(token)
        if length < self._min_length or length > self._max_length:
            return False

        # Pure punctuation / no alphanumerics at all.
        if not any(ch.isalnum() for ch in token):
            return False

        if token.lower() in self._cfg.reject_tokens:
            return False

        # Shapes that are never a password (URL, email, date, time, ...).
        if self._looks_like_non_password(token):
            return False

        return True

    @staticmethod
    def _looks_like_non_password(token: str) -> bool:
        if "://" in token or token.startswith("//") or _URL_RE.match(token):
            return True
        if _EMAIL_RE.match(token):
            return True
        # Bare domain or domain/path (incl. a URL fragment split off at its ":").
        if "." in token and _DOMAIN_RE.search(token):
            return True
        if _TIME_RE.match(token):
            return True
        if _DATE_RE.match(token):
            return True
        if _CURRENCY_RE.match(token):
            return True
        # Telephone-shaped: mostly digits with separators, no letters.
        digits = sum(ch.isdigit() for ch in token)
        if digits >= 7 and _PHONE_RE.match(token):
            return True
        return False

    def _base_score(self, keyword: str) -> float:
        kws = self._cfg.keywords
        if keyword in kws:
            return kws[keyword]
        # Normalise spelling ("pass-word", "one time code" ...) back to a base.
        collapsed = keyword.replace(" ", "").replace("-", "")
        for k, v in kws.items():
            if k.replace(" ", "").replace("-", "") == collapsed:
                return v
        return self._cfg.weights.default_keyword_score

    def _clamp(self, raw: float) -> float:
        """Reported confidence: the raw score held inside the score bounds."""
        w = self._cfg.weights
        return max(w.min_score, min(w.max_score, round(raw, 3)))

    def _raw_score(
        self,
        token: str,
        keyword: str,
        connector: str,
        filler: str,
        gap: int,
        wrapped: bool,
        modifier: float,
    ) -> float:
        """Heuristic score before clamping.

        Left unclamped so ranking can still separate two candidates that both
        sit above the reported ceiling; :meth:`_clamp` produces the number the
        caller sees.
        """
        w = self._cfg.weights
        score = self._base_score(keyword) + modifier

        # Connector strength: ":"/"=" beats a word connector beats nothing.
        if connector and (":" in connector or "=" in connector):
            score += w.colon_bonus
        elif connector:
            score += w.soft_connector_bonus
        else:
            score -= w.no_connector_penalty

        # Filler words between keyword and value add ambiguity.
        if filler:
            filler_words = len(re.findall(r"\S+", filler))
            score -= min(w.filler_penalty_cap, filler_words * w.filler_word_penalty)

        # Proximity: raw character distance between keyword and value.
        if gap > w.distance_free_chars:
            score -= min(
                w.distance_penalty_cap,
                (gap - w.distance_free_chars) * w.distance_penalty_per_char,
            )

        # Token length.
        length = len(token)
        if 6 <= length <= 40:
            score += w.good_length_bonus
        if length < 4:
            score -= w.short_penalty

        # Character-class diversity (lower/upper/digit/symbol).
        has_lower = any(ch.islower() for ch in token)
        has_upper = any(ch.isupper() for ch in token)
        has_digit = any(ch.isdigit() for ch in token)
        has_symbol = any(not ch.isalnum() for ch in token)
        classes = has_lower + has_upper + has_digit + has_symbol
        score += w.class_bonus_per_class * max(0, classes - 1)

        # Randomness: a high-entropy token looks generated, not typed.
        score += w.entropy_scale * min(w.entropy_cap, _entropy(token))

        # Looks like a plain dictionary word: all letters in a single case
        # ("password", "CASE") or capitalised as a sentence starts ("Prompted").
        # Title case matters because that is exactly how an ordinary word
        # appears just after a keyword: "The password is Prompted". Mixed-case
        # alpha (e.g. "aTlKeiEa") is left alone -- it does not read as a word.
        if length > 3 and token.isalpha() and (
            token.islower() or token.isupper() or token.istitle()
        ):
            score -= w.lowercase_word_penalty

        # A known ordinary word from this genre of message. Downranked rather
        # than rejected, since any of them could genuinely be a password, but
        # a real one in the same message should outrank it.
        if token.lower() in self._cfg.dictionary_words:
            score -= w.dictionary_word_penalty

        # A deliberately quoted/bracketed value is a strong "this exact string"
        # signal from the sender.
        if wrapped:
            score += w.wrapped_value_bonus

        # A long pure-digit run is much more likely a reference/policy number.
        if token.isdigit() and length >= w.reference_number_min_digits:
            score -= w.reference_number_penalty

        return round(score, 3)

    def _context(self, text: str, offset: int, token_len: int) -> str:
        if offset < 0:
            return ""

        start = max(0, offset - 40)
        length = (offset - start) + token_len + 40
        snippet = text[start:start + length]

        # Collapse whitespace/newlines for a tidy one-line context.
        snippet = re.sub(r"\s+", " ", snippet).strip()

        return ("…" if start > 0 else "") + snippet + "…"


# --------------------------------------------------------------------------- #
# Module-level convenience: string in -> passwords/candidates out, no object   #
# to construct. HTML vs plain text is detected automatically.                  #
# --------------------------------------------------------------------------- #


def find_passwords(text: str, **options) -> list[str]:
    """Extract passwords from a string, ranked by confidence (highest first).

    A one-shot convenience wrapper around :class:`PasswordFinder`. HTML and
    plain text are both accepted and told apart automatically. ``**options`` are
    forwarded to the :class:`PasswordFinder` constructor (``min_length``,
    ``config``, ...).

    >>> find_passwords("The password is Hunter2!")
    ['Hunter2!']
    """
    return PasswordFinder(**options).find_passwords(text)


def find_all(text: str, **options) -> list[Candidate]:
    """Like :func:`find_passwords`, but returns full :class:`Candidate` objects."""
    return PasswordFinder(**options).find_all(text)
