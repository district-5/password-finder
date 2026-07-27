<!--
Thanks for contributing! Before you write anything below, one rule matters more
than the rest:

  NEVER paste a real password, or anyone's personal information, into this pull
  request — not in the description, not in a test fixture, not in a commit
  message. Everything here is public and permanent, and it stays in the git
  history even if you edit or force-push later.

See "Sample data" below for how to anonymise an email safely.
-->

## Summary

<!-- What does this change do, and why? One or two paragraphs is plenty. -->

## Type of change

<!-- Tick everything that applies. -->

- [ ] Bug fix — the finder returned the wrong thing, or crashed
- [ ] Detection improvement — new keyword, pattern, or scoring tweak
- [ ] New test fixtures only (no engine changes)
- [ ] New feature or configuration option
- [ ] Documentation
- [ ] Build, CI, or packaging
- [ ] Breaking change (existing behaviour or public API changes)

## Related issues

<!-- e.g. "Fixes #12", "Part of #34". Delete if not applicable. -->

## What changed

<!--
Which parts of the library did you touch? Anything that changes matching or
scoring is worth calling out explicitly, since it can shift results for inputs
you never saw:

- keywords / filler / reject word lists (`config.py`)
- scoring weights (`Weights`)
- the match patterns (strict / loose / wrapped / nextline)
- rejection rules (URLs, emails, phone numbers, dates, times, currency)
-->

## Sample data

<!--
Most changes here are best justified with an example message. If you are adding
one — either in the description below or as a file under `tests/` — it MUST be
anonymised first.

Replace the real password with an invented one of the SAME SHAPE: same length,
same mix of upper/lower/digits/symbols, same separators. Shape drives the
scoring (entropy, character-class diversity, length), so `Kf7-Qm2x` is a
faithful stand-in for a real `Ab3-Xy9p`, while `mypassword` is not — it would
be rejected as a plain word and prove nothing.

Also replace, in both the body and any headers you include:

- people's names, signatures, and job titles
- email addresses -> `someone@example.com`
- phone numbers -> an obviously fake number
- company and product names -> "Example"
- links and domains -> `example.com`
- account, invoice, reference, and case numbers -> invented digits of the same length
- postal addresses, dates of birth, and anything else that identifies a person

If the message came from a real mailbox, strip the `Received:`,
`Message-ID:`, `DKIM-Signature:`, and `X-*` headers too — they carry internal
hostnames and routing details.
-->

<!-- Paste an anonymised excerpt here if it helps explain the change. -->

## Test fixtures added

<!--
Delete this section if you did not add any.

Positive fixtures live in `tests/emails/`, named after the password(s) they
contain, with `-OR-` between them when a message holds more than one:

    Kf7Qm2x.txt
    Kf7Qm2x.html
    Kf7Qm2x-OR-Rd4Gh7n.html

The test asserts those passwords come back as the top-ranked candidates, so the
file name is the assertion — no test code needed.

Emails that must NOT yield a convincing password go in
`tests/emails_negative/` instead (marketing, statements, keywords sitting next
to URLs, dates, or phone numbers). Those are checked against a confidence
threshold and guard against precision regressions.

See tests/emails/README.md for the full convention.
-->

- Positive fixtures: <!-- file names, or "none" -->
- Negative fixtures: <!-- file names, or "none" -->

## Testing

<!-- How did you verify this? -->

```
$ pytest
```

- [ ] `pytest` passes locally
- [ ] I checked the change against the existing corpus (`scan-emails`) and no
      previously-correct message regressed
- [ ] The change works on Python 3.9 (the minimum supported version)

## Checklist

- [ ] **No real passwords appear anywhere in this PR** — description, fixtures,
      code comments, or commit messages
- [ ] **No personal or identifying information appears anywhere in this PR** —
      names, email addresses, phone numbers, addresses, account or reference
      numbers, real company names, real domains, or mail headers
- [ ] Any sample data is invented, or anonymised as described above
- [ ] New behaviour is covered by a test (a fixture counts)
- [ ] Documentation is updated if I changed public behaviour or configuration
- [ ] I am happy for this contribution to be released under the repository's
      licence

## Anything else

<!-- Trade-offs, follow-up work, things you were unsure about. -->
