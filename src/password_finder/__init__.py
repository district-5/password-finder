"""Extract passwords from free-form text such as email bodies.

The motivating case: an encrypted attachment arrives in one email, and the
password to open it arrives in another (or in the body of the same message)
phrased in plain English -- *"the password for the attached document is
Q3Report2026z"*. This library pulls that password back out.
"""

from .candidate import Candidate
from .config import DEFAULT_KEYWORDS, FinderConfig, Weights
from .finder import PasswordFinder, find_all, find_passwords

__all__ = [
    "Candidate",
    "PasswordFinder",
    "FinderConfig",
    "Weights",
    "DEFAULT_KEYWORDS",
    "find_passwords",
    "find_all",
]
__version__ = "2.1.0"
