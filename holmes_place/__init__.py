"""Holmes Place Israel booking client."""

from holmes_place.errors import (
    AlreadyRegisteredError,
    BikeOccupiedError,
    HolmesPlaceError,
    LessonCanceledError,
    LessonNotFoundError,
    LessonNotOpenError,
    LessonTimeNotFoundError,
    MultipleDevicesError,
    NoAvailableSeatsError,
    NoMatchingSubscriptionError,
    RegistrationTimeoutError,
)

__all__ = [
    "AlreadyRegisteredError",
    "BikeOccupiedError",
    "HolmesPlaceError",
    "LessonCanceledError",
    "LessonNotFoundError",
    "LessonNotOpenError",
    "LessonTimeNotFoundError",
    "MultipleDevicesError",
    "NoAvailableSeatsError",
    "NoMatchingSubscriptionError",
    "RegistrationTimeoutError",
]
