"""Local identity: where Lionstone keeps per-user files, and who works at this computer.

Studio-style team roles follow an email (env ``LIONSTONE_USER``, then ``lionstone whoami``).
There are no license keys: every feature is available to everyone.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IdentityError(ValueError):
    pass


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (
        os.environ.get("APPDATA") if os.name == "nt" else str(Path.home() / ".config"))
    return Path(base) / "lionstone"


def member_path() -> Path:
    return config_dir() / "member.txt"


def member_email() -> str | None:
    value = os.environ.get("LIONSTONE_USER", "").strip()
    if not value and member_path().exists():
        value = member_path().read_text(encoding="utf-8").strip()
    return value.lower() if EMAIL_RE.match(value) else None


def set_member_email(email: str | None) -> str | None:
    p = member_path()
    if email is None:
        p.unlink(missing_ok=True)
        return None
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise IdentityError(f"not an email address: {email!r}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(email + "\n", encoding="utf-8")
    return email
