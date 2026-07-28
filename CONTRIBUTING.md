# Contributing

Thanks for considering a contribution. This is a small, dependency-free library
with a heuristic core, which makes it unusually easy to help with: **adding a
test fixture is a genuinely valuable contribution**, and needs no Python at all.

By opening a pull request you agree that your contribution is licensed under the
[MIT License](LICENSE) that covers the project.

## The one rule that matters most

**Never put a real password, or anyone's personal information, into this
repository — or into an issue, or a pull request, or a commit message.**

Everything here is public and permanent. A force-push does not undo it: the
objects stay reachable in forks, caches, and anyone's existing clone. If you
believe something sensitive has already landed, read [SECURITY.md](SECURITY.md)
rather than quietly rewriting history.

[tests/emails/README.md](tests/emails/README.md) explains how to anonymise a
real message properly — including why the replacement password needs the same
*shape* as the original, with measured examples. Read it before you paste
anything anywhere.

## Getting set up

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Python 3.9 is the minimum supported version and CI runs 3.9 through 3.13, so
avoid syntax and standard-library features newer than 3.9. The codebase relies
on `from __future__ import annotations` for modern annotation syntax
(`list[Candidate]`, `str | None`) — keep that import at the top of any new
module.

## Reporting something

Use the [issue templates](https://github.com/district-5/py-password-extraction/issues/new/choose):

- **Detection issue** — the finder missed a password, ranked the wrong candidate
  first, or found something that isn't a password. Include an anonymised sample.
- **Bug report** — a crash, wrong types, packaging or CLI trouble.
- **Feature request** — a new keyword, pattern, or configuration knob.
- **Security** — do not open an issue. See [SECURITY.md](SECURITY.md).

## Adding a test fixture (the easiest contribution)

If you have an email shape the finder handles badly, an anonymised fixture is
often more useful than a code change — it pins the behaviour down permanently.

Positive cases go in `tests/emails/`, named after the password they contain:

```
Kf7Qm2x.txt
Kf7Qm2x.html                  # HTML bodies are supported
Kf7Qm2x-OR-Rd4Gh7n.html       # more than one password in one message
```

The file name *is* the assertion — `test_email_fixtures.py` asserts those
passwords come back as the top-ranked candidates, so no test code is needed.

Emails that must **not** yield a convincing password go in
`tests/emails_negative/` instead: marketing, statements, and keywords sitting
next to URLs, dates, or phone numbers. `test_negative_corpus.py` asserts nothing
crosses a confidence threshold, which is what guards precision.

Check your fixture by hand before committing:

```bash
find-password tests/emails/Kf7Qm2x.txt
scan-emails                        # every fixture at once
```

## Changing the engine

The matcher is deliberately layered, and it is worth knowing which layer you are
touching:

| Layer | Where | What it does |
| --- | --- | --- |
| Keywords, filler, reject words | `config.py` (`FinderConfig`) | which words trigger a match, and which values are refused |
| Scoring weights | `config.py` (`Weights`) | every bonus and penalty |
| Match patterns | `finder.py` (`_build_patterns`) | the strict / loose / wrapped / nextline layouts |
| Rejection shapes | `finder.py` (`_looks_like_non_password`) | URLs, emails, phone numbers, dates, times, currency |

Two conventions to follow:

- **Configuration over hard-coding.** Everything tunable belongs in
  `FinderConfig` or `Weights` so callers can override it without patching the
  engine. If you find yourself writing a literal threshold into `finder.py`,
  add a weight instead.
- **No runtime dependencies.** The package is standard library only, and should
  stay that way. Test-only dependencies go in the `dev` extra.

### Scoring changes need corpus evidence

A tweak that fixes your message can quietly break twenty others, because every
fixture is scored by the same weights. Before opening the PR:

```bash
pytest                  # both the positive and the negative corpus
scan-emails             # eyeball the confidence scores across all fixtures
```

Say in the PR what moved and what didn't. If a score changed but stayed
correctly ranked, mention it — reviewers would rather know.

Bear in mind that raising recall usually costs precision. A change that finds
one more password but starts matching reference numbers is a regression, which
is exactly what `tests/emails_negative/` exists to catch. Adding a negative
fixture alongside a recall improvement is the strongest possible case for it.

## Style

There is no linter configured; match the surrounding code. In practice that
means: type hints on public signatures, Sphinx-style `:param:` docstrings on
public methods, comments that explain *why* a heuristic exists rather than
restating it, and private helpers prefixed with `_`.

Keep commits focused, and write commit messages that say why. Do not add
co-author trailers.

## Pull requests

Open a branch, push, and fill in the
[pull request template](.github/pull_request_template.md) — it covers the
fixtures you added, how you tested, and the redaction confirmation.

CI runs the suite on Python 3.9–3.13 for every pull request and must pass. Pull
requests from forks run with a read-only token; no secrets are needed.

Small, single-purpose pull requests get reviewed fastest. If you are planning
something large — a new matching strategy, a restructure — open an issue or a
discussion first so we can agree the shape before you write it.
