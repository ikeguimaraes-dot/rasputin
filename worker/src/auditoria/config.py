"""Configuração do worker, lida do ambiente e validada na inicialização."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_JOB_MAX_ATTEMPTS = 3
DEFAULT_ANTHROPIC_MODEL = ""
DEFAULT_LOG_LEVEL = "INFO"


class ConfigError(ValueError):
    """Variável de ambiente ausente ou inválida."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def _number(env: Mapping[str, str], name: str, default: float, cast: type) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = cast(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Valor deve ser positivo e finito")
        return value
    except ValueError as exc:
        raise ConfigError(f"Valor inválido para {name}: {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    supabase_url: str
    supabase_service_role_key: str = field(repr=False)
    anthropic_api_key: str = field(default="", repr=False)
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    storage_bucket_uploads: str = "uploads"
    storage_bucket_reports: str = "reports"
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    job_max_attempts: int = DEFAULT_JOB_MAX_ATTEMPTS
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        return cls(
            database_url=_required(source, "DATABASE_URL"),
            supabase_url=_required(source, "SUPABASE_URL"),
            supabase_service_role_key=_required(source, "SUPABASE_SERVICE_ROLE_KEY"),
            anthropic_api_key=source.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=source.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
            storage_bucket_uploads=source.get("STORAGE_BUCKET_UPLOADS", "uploads"),
            storage_bucket_reports=source.get("STORAGE_BUCKET_REPORTS", "reports"),
            poll_interval_seconds=_number(
                source, "WORKER_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS, float
            ),
            job_max_attempts=int(
                _number(source, "WORKER_JOB_MAX_ATTEMPTS", DEFAULT_JOB_MAX_ATTEMPTS, int)
            ),
            log_level=source.get("LOG_LEVEL", DEFAULT_LOG_LEVEL),
        )
