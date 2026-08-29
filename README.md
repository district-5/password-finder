# Password Finder

A small Python library that extracts a password out of free-form text.

The motivating case: an encrypted attachment arrives in one email, and the
password to open it arrives in another (or in the body of the same message)
phrased in plain English — *"the password for the attached document is
Q3Report2026z"*. This library pulls that password back out.

## Installation

```bash
pip install password-finder
```

Requires Python 3.9+. It has no runtime dependencies (standard library only).

## Usage

The finder **always returns a list of candidates**, ranked by confidence — it
never returns a single string, because there is often more than one plausible
password and the caller is best placed to decide (try each in turn, apply a
threshold, ask a human). The list is empty when nothing plausible was found.

Everything works on a **string** — read a file (or take an email body) and pass
its contents straight in:

```python
from password_finder import PasswordFinder

finder = PasswordFinder()

email_body = open("message.html", encoding="utf-8").read()

# Full candidate objects, ranked by confidence (highest first), de-duplicated
for c in finder.find_all(email_body):
    print(c.password)     # "Q3Report2026z"
    print(c.confidence)   # 0.96
    print(c.keyword)      # "password"
    print(c.context)      # "…the password to open the document is: Q3Report2026z…"

# Just the strings, same ranking
passwords = finder.find_passwords(email_body)   # ["Q3Report2026z", ...]

# The most likely one (guard for the empty case yourself)
candidates = finder.find_all(email_body)
best = candidates[0].password if candidates else None
```

If you don't need to hold on to a configured finder, call the module-level
helpers — string in, passwords out:

```python
import password_finder

password_finder.find_passwords(open("message.html").read())   # ["Q3Report2026z", ...]
password_finder.find_all("The password is Hunter2!")            # [Candidate(...)]
```

**HTML is detected automatically.** You never tell the library whether a string
is HTML or plain text — it decides per input. When a string looks like HTML
(tags or entities present), `<script>`/`<style>` blocks and comments are
dropped, tags are stripped and entities decoded before matching, so
`<b>Rb9TZ4W</b>` and `&amp;` come out correctly; plain text is left untouched.
You can ask the library directly with `PasswordFinder.looks_like_html(text)`,
or force plain-text handling with `PasswordFinder(decode_html=False)`.

## How it works

The finder scans for password-related keywords — `password`, `passphrase`,
`passcode`, `access code`, `unlock code`, `one-time code`, `authentication
code`, `login credentials`, `pwd`, `pin`, `code`, `secret`, localised spellings
(`kennwort`, `mot de passe`, `contraseña`, …) and more — optionally followed by
filler words (*"for opening the protected mail content"*) and, in most layouts, a
connector (`:`, `=`, or a word like `is` / `will be`), then captures the token
that follows. It matches six layouts:

1. **strict** — keyword + curated filler + connector,
2. **loose** — keyword + free text up to a `:`/`=`,
3. **wrapped** — keyword immediately followed by a quoted/bracketed value,
4. **nextline** — keyword alone on a line with the value on the next line
   (this also recovers label/value pairs in adjacent HTML table cells),
5. **delimited** — keyword followed, a few words (or a sentence) later, by a value
   the sender set off in quotes, `*emphasis*` or brackets, with no connector —
   this catches natural-language phrasings, and HTML emphasis such as `<b>…</b>`
   counts as a delimiter,
6. **proximity** — a last-resort fallback: a bare, undelimited token that mixes
   letters *and* digits sitting close to the keyword.

Values wrapped in quotes, `*markdown*`, `` `backticks` `` or `(brackets)` are
unwrapped automatically. The matching `pattern` and character `span` are exposed
on each `Candidate` for debugging.

Each hit is scored heuristically. Signals that raise confidence:

- an explicit `:` or `=` connector,
- a specific keyword (`password` beats `pin`),
- a value that is close to the keyword (short distance),
- high **Shannon entropy** and **character-class diversity** (looks generated),
- a sensible length (6–40 characters),
- a value the sender deliberately **quoted/bracketed**.

Signals that lower it, or reject the match outright:

- lots of filler words / large distance between the keyword and the value,
- the "password" being a plain word like `attached`, `below`, `reset`, or `is`,
- a passive-delivery phrase such as *"a password will be emailed to you"*, where
  no password is actually present (`emailed`, `issued`, `sent`, … are rejected),
- a long pure-digit run (looks like a reference/policy number),
- shapes that are **never** passwords: URLs, email addresses, phone numbers,
  dates, times, and currency amounts — these are rejected outright.

This means when a message contains several candidates, the most plausible one
sorts to the top. Because it is heuristic, always sanity-check
`.confidence` for your use case rather than trusting the top hit blindly.

## Configuration

Basic knobs, shown with their defaults:

```python
finder = PasswordFinder(
    min_length=3,                        # ignore very short tokens
    max_length=128,                      # ignore very long tokens (URLs etc.)
    extra_keywords=None,                 # add your own trigger words
    decode_html=True,                    # strip HTML before matching
    extra_reject_tokens=None,            # never return these as a password
)
```

Raising `min_length` and lowering `max_length` is the quickest way to trade
recall for precision — e.g. `PasswordFinder(min_length=6, max_length=64)` if you
know the passwords you care about are never shorter than six characters.

Everything the finder uses — keywords and their base scores, the filler/reject
word lists, and every scoring weight — lives in `FinderConfig` and can be
overridden without touching the engine:

```python
from password_finder import PasswordFinder, FinderConfig, Weights

config = FinderConfig(
    keywords={"password": 0.75, "kennwort": 0.72, "magicword": 0.9},
    weights=Weights(colon_bonus=0.20, entropy_scale=0.03),
)
finder = PasswordFinder(config=config)
```

`extra_keywords` still works alongside a custom `config` (it merges on top).

### Blacklisting words

Some corpora keep throwing up the same wrong answer: a word that sits right
after the keyword and reads like a password but never is. Pass those to
`extra_reject_tokens` and they are never returned, however well they score:

```python
finder = PasswordFinder(extra_reject_tokens=["prompted", "accessible"])

finder.find_passwords("The password is prompted")   # []
finder.find_passwords("The password is Hunter2!")   # ["Hunter2!"]
```

Matching is case-insensitive and happens after trimming, so one entry covers
`prompted`, `Prompted` and `prompted.` alike. These **merge with** the built-in
`DEFAULT_REJECT_TOKENS` (`emailed`, `attached`, `reset`, …), so you keep the
defaults; the equivalent on a config object is
`FinderConfig().with_extra_reject_tokens([...])`. To replace the built-in list
outright instead, set the field directly:
`FinderConfig(reject_tokens=frozenset({...}))`.

Note this only stops a word being returned *as a password*. It does not stop it
acting as filler between the keyword and the real value.

## Raw email messages

The finder expects a **body**. A raw `.eml` file is not one: quoted-printable
rewrites `=` as `=3D` and breaks long lines with a trailing `=`, base64 hides
the text completely, and a multipart message carries several bodies at once.
Matching against any of that produces a confidently wrong answer.

`extract_body` turns a message into something worth matching, and hands back
anything that is not a message untouched, so it is always safe to call:

```python
from password_finder import extract_body, find_passwords

find_passwords(open("message.eml").read())                 # ['is=3D'] - wrong
find_passwords(extract_body(open("message.eml").read()))   # ['Ab12Cd34']
```

Quoted-printable and base64 are decoded, the declared charset is applied, and
multipart messages give up their text part (falling back to the HTML one when
the plain part is an empty stub). The `find-password` CLI does this for you.

## Command-line testing

Two helpers are installed with the package for trying the library against real
messages. They print every candidate, best first:

```bash
find-password email.txt        # from a file
pbpaste | find-password        # pipe from the clipboard (macOS)
cat message.eml | find-password

scan-emails                    # run over every file in tests/emails/
scan-emails path/to/dir        # ...or a directory of your choosing
```

You can also invoke them without installing:

```bash
python -m password_finder.cli email.txt
```

## Tests

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Test emails live in `tests/emails/`, named after the password(s) they contain
using `-OR-` as the separator (e.g. `{pw1}-OR-{pw2}.html`). `test_email_fixtures.py`
runs the finder over each one and asserts those passwords are the top-ranked
candidates, so dropping a new email in there and naming it after its password(s)
is enough to add a regression test.

`tests/emails-special-characters/` holds passwords made of punctuation and
symbols — including characters a file name cannot contain — so it uses a
different convention: **the first line of the file is the expected password**,
and `test_special_character_fixtures.py` strips that line before matching. This
is where trimming, HTML entity decoding, and the rejection rules get exercised.

`tests/emails_negative/` holds the **negative corpus** — realistic emails that
must *not* yield a convincing password (marketing, statements, and keywords
sitting next to URLs / dates / phone numbers, or passive-delivery phrasings like
*"a password will be emailed to you"*). `test_negative_corpus.py` asserts nothing
crosses a confidence threshold, guarding against precision regressions.

`tests/emails-private/` is a **git-ignored** directory for real, un-anonymised
messages you don't want committed. Drop `.txt`/`.html` files in — named after
their password(s), exactly like `tests/emails/` — and
`test_email_private_fixtures.py` runs the same top-candidate assertion against
them locally. It ships empty (bar a `.gitkeep`), so in a clean checkout those
tests simply have nothing to run.

Each fixture directory has a `README.md` explaining its convention and how to
anonymise a real message before adding it.

## License

MIT — Copyright (c) 2026 District5. See [LICENSE](LICENSE) for the full text.
