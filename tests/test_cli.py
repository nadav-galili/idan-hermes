from unittest.mock import MagicMock, patch
import json
import pytest

from holmes_place.cli import main


def test_cli_kill_switch_blocks(capsys):
    with patch("holmes_place.cli.Settings.from_env", return_value=MagicMock(base_url="https://x", kill_switch=True)):
        rc = main(["check-clock"])
        assert rc == 2


def test_cli_discover(capsys, monkeypatch):
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    # mock client
    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient:
        inst = MockClient.return_value
        inst.get_available_seats.return_value = [1, 2]
        inst.login.return_value = MagicMock()
        inst.logout.return_value = MagicMock()
        rc = main(["discover", "--branch", "205", "--lesson", "1", "--date", "2026/09/10", "--time", "18:00"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["available_seats"] == [1, 2]


def test_cli_book_dry_run_by_default(capsys, monkeypatch):
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient, patch("holmes_place.cli.book") as mock_book:
        inst = MockClient.return_value
        inst.get_available_seats.return_value = [1]
        mock_book.return_value = MagicMock(status="dry_run", seat=None, message="dry")
        rc = main(
            [
                "book",
                "--branch",
                "205",
                "--lesson",
                "1",
                "--date",
                "2026/09/10",
                "--time",
                "18:00",
                "--instructor",
                "7",
                "--seat",
                "12",
            ]
        )
        assert rc == 0
        # dry_run should be True by default (no --execute)
        assert mock_book.call_args[1]["dry_run"] is True


def test_cli_book_execute_requires_yes_or_abort(monkeypatch):
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    monkeypatch.setenv("HOLMES_I_HAVE_PERMISSION", "1")
    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient, patch("holmes_place.cli.book") as mock_book, patch(
        "builtins.input", return_value="n"
    ):
        inst = MockClient.return_value
        mock_book.return_value = MagicMock(status="booked", seat=12, message="ok")
        rc = main(
            [
                "book",
                "--branch",
                "205",
                "--lesson",
                "1",
                "--date",
                "2026/09/10",
                "--time",
                "18:00",
                "--instructor",
                "7",
                "--seat",
                "12",
                "--execute",
            ]
        )
        assert rc == 0  # aborted gracefully
        mock_book.assert_not_called()
