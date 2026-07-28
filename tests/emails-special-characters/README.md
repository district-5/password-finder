# Special-character email fixtures

The corpus for `test_special_character_fixtures.py`: passwords built from
punctuation and symbols, which is where trimming, HTML entity decoding, and the
"never a password" rejection rules are most likely to go wrong.

## Convention — first line is the expected password

Unlike `tests/emails/`, these fixtures do **not** encode the password in the
file name. Several of these passwords contain characters a file name cannot hold
(`/`, `\`, `|`, `:`), so the first line of the file carries the expectation
instead:

```
a&f$!(

Hi Joe,

Please find the encrypted quote attached...

The password is: a&f$!(
```

The test reads the first line, strips it from the content, and hands only the
remainder to the finder — so the header line can never be what the match is
made against. It then asserts the password is the **top-ranked** candidate.

Name the files after what they exercise, not after the password:
`escaped-ampersand.html`, `slash-and-backslash.txt`.

The first line is trimmed of surrounding whitespace, so a password with leading
or trailing spaces cannot be expressed in this corpus.

## What is worth adding here

Characters and shapes that interact with the engine's own rules:

- **Trimming** — wrappers and trailing punctuation are stripped from a matched
  value, so a password legitimately containing `(`, `)`, `*`, `` ` ``, or a
  trailing `.` is a genuine edge case. See `_trim_token` in `finder.py`.
- **HTML entities** — a password written `Bd7&amp;Tq2!` in an HTML body must come
  back as `Bd7&Tq2!`. Entities are decoded *after* tags are stripped, so
  `&lt;` and `&gt;` survive as literal `<` and `>`.
- **Rejection rules** — values that look like a URL, email address, date, time,
  currency amount, or phone number are refused outright. A password that flirts
  with one of those shapes without being one (`Kx4.Nq9!`, `£9tR#kw2`) is worth
  pinning down.
- **Connector characters** — `:` and `=` separate a keyword from its value, so a
  password containing them tests that the matcher splits in the right place.

Check a new fixture by hand — remember to drop the first line yourself, since
`find-password` reads the whole file:

```bash
tail -n +2 tests/emails-special-characters/escaped-ampersand.html | find-password
```

## Anonymisation

The same rules as everywhere else in this repository: **no real passwords, no
personal information.** Every credential here is freshly invented, company names
are "Example", and addresses point at `example.com`.
[../emails/README.md](../emails/README.md) explains how to anonymise a real
message properly, including why a substitute password needs the same *shape* as
the original.
