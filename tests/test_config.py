from pathlib import Path

import pytest

from contract_bid_research.config import AppSettings, ConfigurationError, migrate_legacy_env


def test_migrate_legacy_env_preserves_secret_without_exposing_it(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("https://model-api.example/\nsk-secret-value", encoding="utf-8")

    assert migrate_legacy_env(env_file) is True

    content = env_file.read_text(encoding="utf-8")
    assert "MODEL_API_BASE_URL=https://model-api.example/v1" in content
    assert "MODEL_API_KEY=sk-secret-value" in content
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_settings_snapshot_redacts_secret(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MODEL_API_BASE_URL=https://model-api.example/v1\n"
        "MODEL_API_KEY=sk-never-print\n"
        "EMBEDDING_DIMENSIONS=1024\n",
        encoding="utf-8",
    )

    settings = AppSettings.load(env_file, environ={})
    snapshot = settings.redacted_snapshot()

    assert snapshot["model_api"]["api_key"] == "<set>"
    assert "sk-never-print" not in str(snapshot)


def test_invalid_dotenv_fails_with_migration_hint(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("https://example.test\nsk-token", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="config-migrate"):
        AppSettings.load(env_file, environ={})
