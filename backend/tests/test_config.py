from pathlib import Path

from yomi.config import Settings


def test_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("DB_CONTENT_PATH", "/tmp/yomi-content.db")
    monkeypatch.setenv("DB_USER_PATH", "/tmp/yomi-user.db")
    monkeypatch.setenv("YOMI_BEHIND_HTTPS", "true")
    monkeypatch.setenv("YOMI_BASE_URL", "https://yomi.example.test")
    monkeypatch.setenv("YOMI_LOG_LEVEL", "debug")

    settings = Settings.from_env()

    assert settings.content_db_path == Path("/tmp/yomi-content.db")
    assert settings.user_db_path == Path("/tmp/yomi-user.db")
    assert settings.behind_https is True
    assert settings.base_url == "https://yomi.example.test"
    assert settings.log_level == "DEBUG"


def test_settings_defaults(monkeypatch):
    for name in (
        "DB_CONTENT_PATH",
        "DB_USER_PATH",
        "YOMI_BEHIND_HTTPS",
        "YOMI_BASE_URL",
        "YOMI_LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.content_db_path == Path("/data/content.db")
    assert settings.user_db_path == Path("/data/user.db")
    assert settings.behind_https is False
    assert settings.base_url == "http://localhost:8888"
    assert settings.log_level == "INFO"

