"""Extract passwords from free-form text such as email bodies.

The motivating case: an encrypted attachment arrives in one email, and the
password to open it arrives in another (or in the body of the same message)
phrased in plain English -- *"the password for the attached document is
Q3Report2026z"*. This library pulls that password back out.
"""

from importlib.metadata import PackageNotFoundError, version as _version

from .candidate import Candidate
from .config import (
    DEFAULT_FILLER_WORDS,
    DEFAULT_KEYWORDS,
    DEFAULT_REJECT_TOKENS,
    FinderConfig,
    Weights,
)
from .email_body import extract_body, looks_like_email
from .finder import PasswordFinder, find_all, find_passwords

__all__ = [
    "Candidate",
    "PasswordFinder",
    "FinderConfig",
    "Weights",
    "DEFAULT_KEYWORDS",
    "DEFAULT_FILLER_WORDS",
    "DEFAULT_REJECT_TOKENS",
    "find_passwords",
    "find_all",
    "extract_body",
    "looks_like_email",
]

# Single source of truth is the "version" field in pyproject.toml, read back
# from the installed package metadata so the two can never drift apart.
try:
    __version__ = _version("password-finder")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0.dev0"
