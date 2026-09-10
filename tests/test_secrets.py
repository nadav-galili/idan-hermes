import os
from holmes_place.secrets import Credentials, get_credentials
from holmes_place.config import Settings, JERUSALEM_TZ


def test_get_credentials_from_env(monkeypatch):
    monkeypatch.setenv("HOLMES_PHONE", "0541234567")
    monkeypatch.setenv("HOLMES_PASSWORD", "secret")
    # ensure .env not interfering — point to non-existent
    import holmes_place.secrets as s

    orig = s.load_dotenv
    s.load_dotenv = lambda *a, **kw: None  # type: ignore[assignment]
    try:
        creds = get_credentials()
        assert creds.phone == "0541234567"
        assert creds.password == "secret"
    finally:
        s.load_dotenv = orig  # type: ignore[assignment]


def test_settings_kill_switch(monkeypatch):
    monkeypatch.setenv("HOLMES_KILL_SWITCH", "1")
    settings = Settings.from_env()
    assert settings.kill_switch is True
    monkeypatch.setenv("HOLMES_KILL_SWITCH", "0")
    assert Settings.from_env().kill_switch is False


def test_jerusalem_tz_is_asia_jerusalem():
    assert str(JERUSALEM_TZ) == "Asia/Jerusalem"
