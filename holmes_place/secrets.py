"""Secret loading — env + local .env, never committed.

Priority: env vars > .env file. .env is optional.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Credentials:
    phone: str
    password: str


def load_dotenv(dotenv_path: str | Path = ".env") -> None:
    """Load KEY=VALUE from .env into os.environ (does not overwrite existing)."""
    p = Path(dotenv_path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def get_credentials() -> Credentials:
    load_dotenv()
    phone = os.getenv("HOLMES_PHONE", "").strip()
    password = os.getenv("HOLMES_PASSWORD", "").strip()
    if not phone or not password:
        raise ValueError("Missing HOLMES_PHONE / HOLMES_PASSWORD (env or .env)")
    return Credentials(phone=phone, password=password)
