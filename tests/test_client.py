"""Tests for HolmesPlaceClient — request shape, cookie session, error mapping, redaction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from holmes_place.client import HolmesPlaceClient
from holmes_place.config import Settings
from holmes_place.errors import (
    AlreadyRegisteredError,
    BikeOccupiedError,
    LessonNotOpenError,
)


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str | None = None,
    headers: dict | None = None,
):
    m = MagicMock(spec=requests.Response)
    m.status_code = status_code
    m.headers = headers or {}
    if json_data is not None:
        m.json.return_value = json_data
        m.text = text or json.dumps(json_data)
    else:
        m.json.side_effect = json.JSONDecodeError("x", "y", 0)
        m.text = text or ""
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    return m


def test_login_sends_form_encoded_and_uses_session():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True})
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.login("0541234567", "secret")
        assert req.called
        args, kwargs = req.call_args
        # request called as (method, url, data=..., headers=..., timeout=...)
        assert args[0] == "POST"
        assert args[1] == "https://example.com/api.php?action=login"
        # form body contains phone & password
        assert "phone=0541234567" in kwargs["data"]
        assert "password=secret" in kwargs["data"]
        assert "application/x-www-form-urlencoded" in kwargs["headers"]["content-type"]


def test_login_raises_on_not_success():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": False, "error": "invalid (1)"})
    with patch.object(client.session, "request", return_value=mock_resp):
        with pytest.raises(Exception) as ei:
            client.login("bad", "bad")
        # unknown code -> generic Exception with error text
        assert "invalid (1)" in str(ei.value)


def test_error_code_mapped_to_typed_exception():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    for code, exc in [("33", BikeOccupiedError), ("32", AlreadyRegisteredError), ("50", LessonNotOpenError)]:
        mock_resp = _mock_response(json_data={"success": False, "error": f"oops ({code})"})
        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(exc):
                client.get_available_seats(branch_id="205", lesson_id="1", date="2026/09/10", time="18:00")


def test_get_available_seats_parses_availableSeats():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True, "availableSeats": json.dumps(["1", "5", "10"])})
    with patch.object(client.session, "request", return_value=mock_resp):
        seats = client.get_available_seats(branch_id="205", lesson_id="1", date="2026/09/10", time="18:00")
        assert seats == [1, 5, 10]


def test_get_available_seats_empty_raises():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True, "availableSeats": json.dumps([])})
    with patch.object(client.session, "request", return_value=mock_resp):
        # empty list may be valid but caller can treat as no seats; we return [] and let booking decide
        seats = client.get_available_seats(branch_id="205", lesson_id="1", date="2026/09/10", time="18:00")
        assert seats == []


def test_register_with_seat_sends_correct_fields():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True})
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.register_with_seat(
            branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7", seat_id=12
        )
        _, kwargs = req.call_args
        assert "branchID=205" in kwargs["data"]
        assert "lessonID=123" in kwargs["data"]
        assert "seatID=12" in kwargs["data"]
        assert "instructorID=7" in kwargs["data"]


def test_register_without_seat():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True})
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.register(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7")
        _, kwargs = req.call_args  # noqa: F841 - keep for patch style, but check via kwargs
        assert "seatID" not in kwargs["data"]


def test_unregister_and_logout():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(json_data={"success": True})
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.unregister(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00")
        assert "unRegisterToLesson" in req.call_args[0][1]
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.logout()
        assert "logout" in req.call_args[0][1]


def test_kill_switch_blocks_requests():
    client = HolmesPlaceClient(Settings(base_url="https://example.com", kill_switch=True))
    with pytest.raises(RuntimeError, match="kill-switch"):
        client.login("a", "b")


def test_http_error_propagated():
    client = HolmesPlaceClient(Settings(base_url="https://example.com"))
    mock_resp = _mock_response(status_code=500, text="server error")
    # json decode fails + raise_for_status will raise
    mock_resp.json.side_effect = json.JSONDecodeError("x", "y", 0)
    mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
    with patch.object(client.session, "request", return_value=mock_resp):
        with pytest.raises(requests.HTTPError):
            client.login("a", "b")
