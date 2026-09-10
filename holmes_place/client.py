"""HolmesPlaceClient — thin wrapper over api.php with session, typed errors, redacted logging."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from holmes_place.config import Settings
from holmes_place.errors import error_from_response, redact

logger = logging.getLogger(__name__)


class HolmesPlaceClient:
    """Stateful client — holds a cookie session (requests.Session). One per member."""

    def __init__(self, settings: Settings | None = None, session: requests.Session | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.session = session or requests.Session()
        # consistent with reference impl, but trimming fake_useragent dep
        self.session.headers.update({"User-Agent": "holmes-place-booking/0.1"})

    # -- internal --

    def _check_kill_switch(self) -> None:
        if self.settings.kill_switch:
            raise RuntimeError("kill-switch active — refusing to send request (HOLMES_KILL_SWITCH=1)")

    def _request(self, endpoint: str, data: str) -> requests.Response:
        self._check_kill_switch()
        url = self.settings.endpoint(endpoint)
        headers = {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"}
        logger.debug("POST %s data=%s", url, redact(data))
        resp = self.session.request("POST", url, data=data, headers=headers, timeout=15)
        logger.debug("resp %s %s body=%s", resp.status_code, url, redact(resp.text[:2000]))
        # JSON error mapping before raise_for_status so typed errors surface
        try:
            body: Any = resp.json()
        except (json.JSONDecodeError, ValueError):
            body = None
        if isinstance(body, dict):
            success = body.get("success", False)
            error = body.get("error")
            if not success and error:
                typed = error_from_response(str(error))
                if typed is not None:
                    raise typed
                # unknown api error — still surface as generic Exception with api text
                raise Exception(str(error))
            if not success and body.get("success") is False and error is None:
                # e.g. login failure "(1)" sometimes without success true — treat as error
                # body may still have error key missing; just pass through
                pass
        resp.raise_for_status()
        # after HTTP OK, if body said success False but error was empty/unmapped, raise generic
        if isinstance(body, dict) and body.get("success") is False:
            err = body.get("error") or body.get("message") or "request failed"
            raise Exception(str(err))
        return resp

    # -- public API --

    def login(self, phone: str, password: str) -> requests.Response:
        return self._request("login", f"phone={phone}&password={password}")

    def logout(self) -> requests.Response:
        return self._request("logout", "action=logout")

    def get_available_seats(self, branch_id: str, lesson_id: str, date: str, time: str) -> list[int]:
        """date: YYYY/MM/DD, time: HH:MM"""
        resp = self._request(
            "available_seats", f"branchID={branch_id}&lessonID={lesson_id}&date={date}&time={time}"
        )
        data = resp.json()
        raw = data.get("availableSeats", "[]")
        # availableSeats is JSON-encoded string in reference impl: '["1","2"]'
        try:
            parsed: Any = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            parsed = []
        seats: list[int] = []
        for s in parsed or []:
            try:
                seats.append(int(s))
            except (TypeError, ValueError):
                continue
        return seats

    def register(self, branch_id: str, lesson_id: str, date: str, time: str, instructor_id: str) -> requests.Response:
        return self._request(
            "register_to_lesson",
            f"branchID={branch_id}&lessonID={lesson_id}&date={date}&time={time}&instructorID={instructor_id}",
        )

    def register_with_seat(
        self, branch_id: str, lesson_id: str, date: str, time: str, instructor_id: str, seat_id: int
    ) -> requests.Response:
        return self._request(
            "register_to_lesson_with_seat",
            f"branchID={branch_id}&lessonID={lesson_id}&date={date}&time={time}&instructorID={instructor_id}&seatID={seat_id}",
        )

    def unregister(self, branch_id: str, lesson_id: str, date: str, time: str) -> requests.Response:
        return self._request(
            "unregister", f"branchID={branch_id}&lessonID={lesson_id}&date={date}&time={time}"
        )
