from holmes_place.errors import (
    AlreadyRegisteredError,
    BikeOccupiedError,
    LessonCanceledError,
    LessonNotOpenError,
    LessonTimeNotFoundError,
    MultipleDevicesError,
    NoMatchingSubscriptionError,
    error_from_response,
    redact,
)


def test_error_from_response_codes():
    assert isinstance(error_from_response("blah (26) foo"), NoMatchingSubscriptionError)
    assert isinstance(error_from_response("x (30)"), LessonTimeNotFoundError)
    assert isinstance(error_from_response("(31)"), LessonCanceledError)
    assert isinstance(error_from_response("err (32)"), AlreadyRegisteredError)
    assert isinstance(error_from_response("bike (33) taken"), BikeOccupiedError)
    assert isinstance(error_from_response("closed (50)"), LessonNotOpenError)


def test_error_from_response_hebrew_multiple_devices():
    assert isinstance(
        error_from_response("לא ניתן להתחבר עם אותו חשבון ממספר מכשירים"), MultipleDevicesError
    )
    assert isinstance(error_from_response("Multiple Devices connection"), MultipleDevicesError)


def test_error_from_response_unknown_returns_none():
    assert error_from_response("some random error (99)") is None
    assert error_from_response("") is None


def test_redact_masks_secrets():
    s = "phone=0541234567&password=s3cret&branchID=205"
    r = redact(s)
    assert "0541234567" not in r
    assert "s3cret" not in r
    assert "phone=***" in r
    assert "password=***" in r
    assert "branchID=205" in r  # non-secret stays


def test_redact_masks_cookies():
    s = "Cookie: PHPSESSID=abc123; other=1\nSet-Cookie: sessionid=xyz; Path=/"
    r = redact(s)
    assert "abc123" not in r
    assert "xyz" not in r
    assert "Cookie: ***" in r
    assert "Set-Cookie: ***" in r


def test_redact_masks_sessionid_in_body():
    s = "foo PHPSESSID=abcdef&bar=1"
    r = redact(s)
    assert "abcdef" not in r
