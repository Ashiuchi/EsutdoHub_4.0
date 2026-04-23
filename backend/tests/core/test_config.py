import pytest
from unittest.mock import patch, MagicMock
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


def test_vault_skipped_when_addr_not_set():
    s = Settings(vault_addr=None, vault_token=None)
    # Should not attempt Vault connection
    assert s.vault_addr is None


def test_vault_loads_gemini_key():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"GEMINI_API_KEY": "vault-gemini-key"}}
    }
    with patch('hvac.Client', return_value=mock_client):
        s = Settings(vault_addr="http://vault:8200", vault_token="test-token")
        assert s.gemini_api_key == "vault-gemini-key"


def test_vault_loads_database_url():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"DATABASE_URL": "postgresql://vault-db/test"}}
    }
    with patch('hvac.Client', return_value=mock_client):
        s = Settings(vault_addr="http://vault:8200", vault_token="test-token")
        assert s.database_url == "postgresql://vault-db/test"


def test_vault_auth_failure_falls_back_gracefully():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = False
    with patch('hvac.Client', return_value=mock_client):
        # Should not raise, just skip Vault
        s = Settings(vault_addr="http://vault:8200", vault_token="bad-token")
        assert s is not None


def test_vault_connection_error_falls_back_gracefully():
    with patch('hvac.Client', side_effect=Exception("Connection refused")):
        s = Settings(vault_addr="http://vault:8200", vault_token="test-token")
        assert s is not None
