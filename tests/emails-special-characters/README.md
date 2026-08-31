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

## Known boundaries

Some shapes cannot be expressed in this corpus at all, because the finder will
never return them. They are listed here so nobody spends an afternoon writing a
fixture that cannot pass.

**By design.** Trimming runs on every match, so these come back shortened:

| Written in the message | Returned | Why |
| --- | --- | --- |
| `Kp7Rn2Wq.` | `Kp7Rn2Wq` | trailing `.` `,` `;` `:` is sentence punctuation. `!` and `?` are kept, so `Nx6Bt2Kq?` is fine |
| `"Kp7Rn2Wq"` | `Kp7Rn2Wq` | a matched wrapper pair is unwrapped |
| `*Kp7Rn2Wq*` | `Kp7Rn2Wq` | same, and this is how HTML emphasis arrives |

A password that genuinely ends in `.` or is genuinely wrapped in quotes is
therefore out of reach. Put the character inside the value instead, as
`internal-full-stop.txt` and `apostrophe-inside.txt` do.

**Rejected outright.** These are read as a different kind of thing:

- **Ends in a dot and two or more letters** (`Kp7.Rnx`, `Vq8.co`) reads as a
  domain. Note the boundary: `Kp7.Rn9` survives, because it ends in a digit.
- **Email shaped** (`Kp7@Rn2.co`) reads as an address. An at sign on its own is
  fine, which is what `at-sign-not-an-email.txt` pins down.
- **All digits and separators with seven or more digits** reads as a telephone
  number. One letter anywhere is enough to save it, per `phone-like-digits.txt`.

**Angle brackets need an HTML fixture.** In a plain-text body, `<Mk4>` makes the
whole message look like HTML, and the "tag" is stripped before matching. Write
that case as HTML using `&lt;` and `&gt;`, as `escaped-angle-brackets.html`
does.

## Anonymisation

The same rules as everywhere else in this repository: **no real passwords, no
personal information.** Every credential here is freshly invented, company names
are "Example", and addresses point at `example.com`.
[../emails/README.md](../emails/README.md) explains how to anonymise a real
message properly, including why a substitute password needs the same *shape* as
the original.
