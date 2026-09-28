import dataclasses

import pytest

from auditoria.config import ConfigError, Settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql://u:p@h/db",
    "SUPABASE_URL": "http://supabase.local",
    "SUPABASE_SERVICE_ROLE_KEY": "k",
}


def test_loads_required_values_and_applies_defaults():
    # Arrange / Act
    settings = Settings.from_env(REQUIRED_ENV)

    # Assert
    assert settings.database_url == "postgresql://u:p@h/db"
    assert settings.poll_interval_seconds == 2.0
    assert settings.job_max_attempts == 3
    assert settings.anthropic_model == ""


@pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
def test_raises_when_required_variable_is_missing(missing):
    env = {k: v for k, v in REQUIRED_ENV.items() if k != missing}

    with pytest.raises(ConfigError, match=missing):
        Settings.from_env(env)


def test_raises_when_numeric_variable_is_invalid():
    env = {**REQUIRED_ENV, "WORKER_POLL_INTERVAL_SECONDS": "abc"}

    with pytest.raises(ConfigError, match="WORKER_POLL_INTERVAL_SECONDS"):
        Settings.from_env(env)


def test_settings_are_immutable():
    settings = Settings.from_env(REQUIRED_ENV)

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.database_url = "outra"  # type: ignore[misc]


def test_repr_does_not_leak_secrets():
    env = {**REQUIRED_ENV, "SUPABASE_SERVICE_ROLE_KEY": "segredo-123"}

    assert "segredo-123" not in repr(Settings.from_env(env))
