import pytest

from app.config import Settings


def prepare_env(monkeypatch):
    # Never load the real .env or user credentials in tests.
    monkeypatch.setattr("app.config.load_dotenv", lambda path: None)
    monkeypatch.setenv("TG_API_ID", "1")
    monkeypatch.setenv("TG_API_HASH", "test")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8080")


def test_catalog_settings(monkeypatch):
    prepare_env(monkeypatch)
    monkeypatch.setenv("CATALOG_SHEET_ID", "test-sheet")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "data/test-key.json")
    monkeypatch.setenv("CATALOG_CACHE_SECONDS", "0")
    cfg = Settings.from_env()
    assert cfg.catalog_sheet_id == "test-sheet"
    assert cfg.catalog_credentials.name == "test-key.json"
    assert cfg.catalog_credentials.is_absolute()
    assert cfg.catalog_cache_seconds == 0
    assert cfg.llm_url.endswith("/v1/chat/completions")


@pytest.mark.parametrize("key,value", [("CATALOG_CACHE_SECONDS", "-1"),
                                       ("CATALOG_TIMEOUT_SECONDS", "0")])
def test_invalid_catalog_settings(monkeypatch, key, value):
    prepare_env(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()


def test_public_csv_configuration_without_credentials(monkeypatch):
    prepare_env(monkeypatch)
    url = "https://docs.google.com/spreadsheets/d/e/test/pub?output=csv"
    monkeypatch.setenv("CATALOG_CSV_URL", url)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    cfg = Settings.from_env()
    assert cfg.catalog_csv_url == url and cfg.catalog_credentials is None


@pytest.mark.parametrize("url", ["http://docs.google.com/spreadsheets/test", "https://example.com/menu.csv"])
def test_invalid_csv_url(monkeypatch, url):
    prepare_env(monkeypatch)
    monkeypatch.setenv("CATALOG_CSV_URL", url)
    with pytest.raises(ValueError, match="CATALOG_CSV_URL"):
        Settings.from_env()
