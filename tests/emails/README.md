# Email fixtures

These files are the test corpus for `test_email_fixtures.py`. Drop email bodies
in here, one message per file, named after the password they contain:

```
{expected-password}.txt     e.g. Rb9TZ4W.txt
{expected-password}.html    e.g. Rb9TZ4W.html   (HTML bodies are supported)
```

When one message contains more than one password, join them with `-OR-`:

```
Rb9TZ4W-OR-Kf7Qm2x.html
```

The test runs the finder over each file and asserts the **file name** is the
top-ranked candidate returned, so naming a new email after its password is all
you need to add a regression test.

Try one by hand:

```bash
find-password tests/emails/Rb9TZ4W.txt
```

Or scan every file at once:

```bash
scan-emails
```

## Anonymising a real email

**Every fixture in this directory is invented or anonymised, and yours must be
too.** These files are committed to version control so the suite can run in CI —
they are public, and they stay in the git history even if a later commit removes
them. Nothing that is genuinely a secret, and nothing that identifies a real
person, may go in here.

The same rules apply to anything you paste into an issue or a pull request.

### Replace the password with one of the same *shape*

This is the part people get wrong. The scoring reacts to a value's **shape** —
its length, its mix of upper case, lower case, digits and symbols, its entropy,
and its separators — not to the value itself. So substitute a password that
looks structurally identical to the real one:

A good substitute scores the same as the value it replaces. Dropped into the
same sentence — *"The password to open the attached document is: …"* — these
come out identical:

| Real password | Substitute | Confidence |
| --- | --- | --- |
| `Ab3-Xy9p` | `Kf7-Qm2x` | 0.96 → 0.96 |
| `5521-QT` | `8834-RN` | 0.91 → 0.91 |
| `winter2026` | `summer2019` | 0.88 → 0.88 |

Whereas these all change what the fixture is testing:

| Substitute | Result | Why |
| --- | --- | --- |
| `mypassword` | 0.96 → **0.75** | all lower case, no digits or symbols — much lower entropy and character-class diversity. The test may still pass, but on a weaker signal than the message you captured, so it no longer guards the same behaviour |
| `ab3-xy9p` | 0.96 → **0.92** | even just flattening the mixed casing moves the score |
| `attached` | **no candidates** | on the reject word list — plain words that follow "password is" are treated as prose, not values |
| `12345678` | **no candidates** | a long pure-digit run is deliberately read as a reference number |
| `x` | **no candidates** | below `min_length`, so it never reaches the scorer |

(Confidences above are from the default configuration; check yours with
`find-password`.)

Invent it yourself, or generate one:

```bash
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8)))"
```

Never reuse a password you have used anywhere, even an expired one.

### Replace everything else that identifies someone

- **Names, signatures, job titles** — invent them.
- **Email addresses** — `someone@example.com`.
- **Links and domains** — `example.com` (reserved for exactly this purpose).
- **Company and product names** — "Example", "Example Membership", "Example GmbH".
- **Phone numbers, account, invoice, reference and case numbers** — invented
  digits of the **same length**. Length matters: a long pure-digit run is
  deliberately treated as a reference number rather than a password, so
  shortening it changes the behaviour you are trying to capture.
- **Postal addresses, dates of birth, customer IDs** — remove or invent.
- **Mail headers**, if you saved the message from a real mailbox — strip
  `Received:`, `Message-ID:`, `DKIM-Signature:`, `Authentication-Results:` and
  every `X-*` header. They carry internal hostnames, routing paths and
  infrastructure details.

Keep the *structure* intact while you do this — the wording, line breaks,
punctuation, and HTML tags around the password are what the patterns match on.
Rewriting the prose around the password defeats the purpose of the fixture.

### Then check it still reproduces

```bash
find-password tests/emails/Kf7-Qm2x.txt
```

The password in the file name should come back as the top candidate. If your
anonymised version no longer behaves like the original, adjust the substitute's
shape — don't reach for the real message.

> If a real password or any personal data does get committed here, treat it as
> disclosed: rotate the password, and raise it with the maintainers rather than
> quietly force-pushing over it — the object stays reachable in forks, caches,
> and anyone's existing clone.
