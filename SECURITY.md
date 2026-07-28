# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting instead: go to the
[Security tab](https://github.com/district-5/py-password-extraction/security)
and choose **Report a vulnerability**. That channel is private to you and the
maintainers.

If you cannot use it, open a normal issue containing **only** the sentence
"I have a security report" — no details, no sample data — and a maintainer will
arrange a private channel. Do not describe the problem in the public issue.

We aim to acknowledge a report within 5 working days, and to agree a disclosure
timeline with you once we have confirmed it. Please give us a reasonable chance
to ship a fix before publishing.

<!-- Maintainers: if you set up a dedicated security mailbox, add it here as a
     second channel. Do not list an address that nobody monitors. -->

## Never send us a real password

This library exists to extract passwords, so reports naturally come with sample
messages attached. **Sanitise them before sending, even privately.**

Replace the real password with an invented one of the **same shape** — same
length, same mix of upper case, lower case, digits and symbols, same separators
— and strip names, email addresses, phone numbers, account and reference
numbers, real domains, and mail headers. `tests/emails/README.md` has worked
examples with measured confidence scores.

If a real password has already been committed, pasted into an issue, or emailed
anywhere: **rotate it first**, then tell us. Treat it as disclosed. Git objects
stay reachable in forks, caches, and existing clones long after a force-push,
so rewriting history is not a remedy on its own.

## Scope

The library takes untrusted text and runs regular expressions over it. It has no
runtime dependencies, opens no network connections, reads no files (the
`find-password` and `scan-emails` CLI entry points do), and never evaluates or
deserialises input. So the interesting attack surface is narrow, and it is
mostly about what a hostile *input string* can do to a process that parses it.

In scope:

- **Catastrophic backtracking / denial of service.** An input that makes
  matching take pathological time or memory. The matcher compiles patterns from
  a configurable keyword list and applies bounded-repetition groups to arbitrary
  text; an input that defeats those bounds is a valid report. Please include the
  input (sanitised), the wall-clock time, and your `min_length`/`max_length` and
  `FinderConfig` settings.
- **Unbounded memory growth** on large or adversarial bodies, including in HTML
  normalisation.
- **Crashes** that a caller cannot defend against — an uncaught exception on
  input that is merely unusual rather than invalid.
- **Leaks of extracted values** into places a caller did not choose: an
  exception message, a warning, `repr()` output, or a temporary file.
- **Supply-chain problems**: a compromised or typo-squatted `password-finder`
  release, or a tampered artefact.

Out of scope — real reports, but not security ones, so please use the
[issue templates](https://github.com/district-5/py-password-extraction/issues/new/choose):

- The finder **missing** a password, ranking the wrong candidate first, or
  returning a false positive. These are detection bugs. The library is
  explicitly heuristic and returns ranked candidates rather than one answer.
- A confidence score you disagree with.
- The library finding a password in a message you consider private — it only
  ever sees the string you pass it.

## Handling extracted passwords safely

Some hazards live in the calling code rather than in this library, and they are
easy to trip over. If you integrate it, note:

- **`str(candidate)` returns the bare password.** `Candidate.__str__` is the
  password itself, so `print(f"found {c}")`, `logging.info("%s", c)`, and any
  f-string interpolation write a real secret to your logs.
- **`candidate.context` contains the password plus roughly 40 characters either
  side.** It exists for debugging and review. Logging it leaks both the secret
  and the surrounding message text.
- **`candidate.to_dict()` serialises `password` and `context` in full.** Do not
  hand it to a JSON logger, an error tracker, or an analytics pipeline.
- **The CLI prints candidates to stdout.** Convenient for testing, but that
  means terminal scrollback, shell history, CI logs, and any redirect target.
  Do not run `scan-emails` over real mail in CI.
- Keep extracted passwords in memory only as long as you need them, and prefer
  passing them straight to the consumer (e.g. the archive being opened) over
  storing them.

## Supported versions

| Version | Supported |
| --- | --- |
| 2.1.x | Yes |
| < 2.1 | No — please upgrade |

Fixes land on `master` and go out in a new release; there are no long-term
support branches.
