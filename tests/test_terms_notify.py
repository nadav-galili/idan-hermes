"""Terms gate + notification."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_terms_has_permission_flag(monkeypatch):
    from holmes_place.terms import has_permission, require_permission

    monkeypatch.delenv("HOLMES_I_HAVE_PERMISSION", raising=False)
    assert not has_permission(False)
    assert has_permission(True)
    monkeypatch.setenv("HOLMES_I_HAVE_PERMISSION", "1")
    assert has_permission(False)
    monkeypatch.setenv("HOLMES_I_HAVE_PERMISSION", "true")
    assert has_permission(False)
    monkeypatch.setenv("HOLMES_I_HAVE_PERMISSION", "0")
    assert not has_permission(False)
    with pytest.raises(PermissionError):
        require_permission(False)


def test_notify_webhook_and_log(tmp_path: Path, monkeypatch):
    from holmes_place.notify import notify

    log = tmp_path / "notify.jsonl"
    monkeypatch.delenv("HOLMES_NOTIFY_URL", raising=False)
    monkeypatch.delenv("HOLMES_NOTIFY_LOG", raising=False)
    with patch("holmes_place.notify.requests.post") as mock_post:
        notify(status="booked", lesson={"branch_id": "205"}, seat=12, message="ok", notify_url="https://example.com/hook", notify_log=str(log))
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://example.com/hook"
        assert log.exists()
        data = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
        assert data["status"] == "booked"
        assert data["seat"] == 12


def test_cli_book_execute_requires_permission(monkeypatch, capsys):
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    monkeypatch.delenv("HOLMES_I_HAVE_PERMISSION", raising=False)
    from holmes_place.cli import main

    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient:
        inst = MockClient.return_value
        inst.login.return_value = MagicMock()
        inst.logout.return_value = MagicMock()
        rc = main(
            [
                "book",
                "--branch",
                "205",
                "--lesson",
                "123",
                "--date",
                "2026/09/10",
                "--time",
                "18:00",
                "--instructor",
                "7",
                "--execute",
                "--yes",
            ]
        )
        assert rc == 2
        assert "Terms gate" in capsys.readouterr().err


def test_cli_book_execute_with_permission(monkeypatch):
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    monkeypatch.setenv("HOLMES_I_HAVE_PERMISSION", "1")
    from holmes_place.cli import main

    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient, patch("holmes_place.cli.book") as mock_book:
        inst = MockClient.return_value
        inst.login.return_value = MagicMock()
        inst.logout.return_value = MagicMock()
        mock_book.return_value = MagicMock(status="booked", seat=12, message="ok")
        rc = main(
            [
                "book",
                "--branch",
                "205",
                "--lesson",
                "123",
                "--date",
                "2026/09/10",
                "--time",
                "18:00",
                "--instructor",
                "7",
                "--execute",
                "--yes",
            ]
        )
        assert rc == 0
        mock_book.assert_called_once()


def test_cli_schedule_requires_permission(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("HOLMES_I_HAVE_PERMISSION", raising=False)
    yaml_text = """
clubs:
  205:
    pilates:
      - day: monday
        type: pilates
        start_time: '8:30'
        registration_day: sunday
        registration_start_time: '8:30'
        lesson_id: '10440'
        instructor_id: '27'
"""
    p = tmp_path / "holmes_lessons.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    from holmes_place.cli import main

    rc = main(["schedule", "--config", str(p), "--output", str(tmp_path / "out")])
    assert rc == 2
    assert "Terms gate" in capsys.readouterr().err

    # dry-run does not require permission
    capsys.readouterr()
    rc2 = main(["schedule", "--config", str(p), "--dry-run"])
    assert rc2 == 0

    # with permission flag passes
    rc3 = main(["schedule", "--config", str(p), "--output", str(tmp_path / "out2"), "--i-have-permission"])
    assert rc3 == 0
