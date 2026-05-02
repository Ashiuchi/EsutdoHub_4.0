from app.core.config import Settings


def test_settings_default_llm_strategy():
    s = Settings()
    assert s.llm_strategy in ("local_first", "local_only", "cloud_only")


def test_settings_default_cloud_fallback():
    s = Settings()
    assert isinstance(s.cloud_fallback, bool)


def test_parse_origins_from_comma_separated_string():
    s = Settings(allowed_origins="http://localhost:3000,http://localhost:8080")
    assert "http://localhost:3000" in s.allowed_origins
    assert "http://localhost:8080" in s.allowed_origins


def test_parse_origins_strips_whitespace():
    s = Settings(allowed_origins=" http://a.com , http://b.com ")
    assert "http://a.com" in s.allowed_origins
    assert "http://b.com" in s.allowed_origins


def test_parse_origins_from_list():
    s = Settings(allowed_origins=["http://localhost:3000"])
    assert s.allowed_origins == ["http://localhost:3000"]


def test_settings_loads_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-db/test")

    s = Settings()

    assert s.gemini_api_key == "env-gemini-key"
    assert s.database_url == "postgresql://env-db/test"


def test_settings_ignores_legacy_vault_values(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    monkeypatch.setenv("VAULT_TOKEN", "legacy-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-db/test")

    s = Settings()

    assert s.database_url == "postgresql://env-db/test"
    assert not hasattr(s, "vault_addr")
