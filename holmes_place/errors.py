"""Error codes and exceptions for Holmes Place api.php.

Maps the (N) error codes returned inside JSON `error` strings to typed
exceptions. Mirrors the reference impl's ApiHandler codes but as a single
authoritative table with redaction-safe messages.
"""

from __future__ import annotations


class HolmesPlaceError(Exception):
    """Base for all Holmes Place API errors."""


class NoMatchingSubscriptionError(HolmesPlaceError):
    pass


class LessonTimeNotFoundError(HolmesPlaceError):
    pass


class LessonCanceledError(HolmesPlaceError):
    pass


class AlreadyRegisteredError(HolmesPlaceError):
    """Idempotent success — caller should treat as booked."""

    pass


class BikeOccupiedError(HolmesPlaceError):
    pass


class LessonNotOpenError(HolmesPlaceError):
    pass


class LessonNotFoundError(HolmesPlaceError):
    pass


class NoAvailableSeatsError(HolmesPlaceError):
    pass


class MultipleDevicesError(HolmesPlaceError):
    pass


class RegistrationTimeoutError(HolmesPlaceError):
    pass


# api.php returns Hebrew/English strings with "(N)" codes embedded.
# Table derived from raviv-steinberg ApiHandler + live probe on 2026-09-10
# where login with bad creds returned "... (1)".
ERROR_CODE_MAP: dict[str, type[HolmesPlaceError]] = {
    "26": NoMatchingSubscriptionError,
    "30": LessonTimeNotFoundError,
    "31": LessonCanceledError,
    "32": AlreadyRegisteredError,
    "33": BikeOccupiedError,
    "50": LessonNotOpenError,
}

# Some errors surface without codes (legacy flows) — match by substring.
_SUBSTRING_MAP: dict[str, type[HolmesPlaceError]] = {
    "לא ניתן להתחבר עם אותו חשבון ממספר מכשירים": MultipleDevicesError,
    "multiple devices": MultipleDevicesError,
}


def error_from_response(error_text: str) -> HolmesPlaceError | None:
    """Return typed exception for an `error` string, or None if unknown.

    Checks (N) codes first, then Hebrew/English substring fallbacks.
    """
    if not error_text:
        return None
    # code match: "(N)" anywhere in string
    for code, exc_cls in ERROR_CODE_MAP.items():
        if f"({code})" in error_text:
            return exc_cls(error_text)
    lower = error_text.lower()
    for needle, exc_cls in _SUBSTRING_MAP.items():
        if needle.lower() in lower:
            return exc_cls(error_text)
    return None


def redact(text: str) -> str:
    """Redact phone/password/cookies for logging."""
    if not text:
        return text
    import re

    for key in ("phone", "password", "birthday"):
        text = re.sub(rf"{key}=[^&\s]*", f"{key}=***", text, flags=re.IGNORECASE)
    # cookie headers / Set-Cookie values — mask entire header value
    text = re.sub(r"(?i)(cookie:\s*)[^\r\n]+", r"\1***", text)
    text = re.sub(r"(?i)(set-cookie:\s*)[^\r\n]+", r"\1***", text)
    # also mask bare session cookie patterns that sometimes appear in body dumps
    text = re.sub(r"(?i)(PHPSESSID|sessionid)=[^&\s;]+", r"\1=***", text)
    return text
