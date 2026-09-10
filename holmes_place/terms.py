"""Terms gate — require explicit permission before unattended automation.

Spec: \"verify Holmes Place/Fizikal terms and obtain permission before
unattended automation.\" We enforce it as an explicit flag/env:

- CLI: --i-have-permission
- Env: HOLMES_I_HAVE_PERMISSION=1 / true / yes

Applies to unattended paths: `book --execute` and `schedule` (without --dry-run).
Read-only paths (discover, check-clock, dry-run) do not require it.
"""

from __future__ import annotations

import os


def has_permission(cli_flag: bool | None = None) -> bool:
    if cli_flag:
        return True
    env = os.getenv("HOLMES_I_HAVE_PERMISSION", "").strip().lower()
    return env in ("1", "true", "yes")


def require_permission(cli_flag: bool | None = None) -> None:
    if not has_permission(cli_flag):
        raise PermissionError(
            "Terms gate: set HOLMES_I_HAVE_PERMISSION=1 or pass --i-have-permission "
            "after verifying Holmes Place/Fizikal terms and obtaining permission. "
            "See README Terms."
        )
