"""Typed runtime configuration with explicit secret redaction."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when runtime configuration is incomplete or malformed."""


def _normalize_base_url(value: str, *, with_v1: bool = False) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"invalid HTTP base URL: {value!r}")
    if with_v1 and not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def read_dotenv(path: Path) -> dict[str, str]:
    """Read a strict KEY=value file without mutating process environment."""

    if not path.exists():
        return {}
    values: dict[str, str] = {}
    invalid_lines: list[int] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            invalid_lines.append(line_number)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier() or not key.isupper():
            invalid_lines.append(line_number)
            continue
        values[key] = value.strip().strip('"').strip("'")
    if invalid_lines:
        joined = ", ".join(str(number) for number in invalid_lines)
        raise ConfigurationError(
            f"{path} contains non KEY=value lines ({joined}); run `contract-bid-infra config-migrate`"
        )
    return values


def _as_float(values: Mapping[str, str], key: str, default: float) -> float:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a number") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be positive")
    return value


def _as_int(values: Mapping[str, str], key: str, default: int) -> int:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{key} must be positive")
    return value


@dataclass(frozen=True)
class MinerUSettings:
    base_url: str
    token: str | None
    ca_bundle: Path | None
    connect_timeout_s: float
    read_timeout_s: float
    task_timeout_s: float
    poll_interval_s: float

    @property
    def verify(self) -> bool | str:
        return str(self.ca_bundle) if self.ca_bundle else True


@dataclass(frozen=True)
class ModelAPISettings:
    base_url: str
    api_key: str
    timeout_s: float
    embedding_model: str
    embedding_dimensions: int
    rerank_model: str
    chat_model: str


@dataclass(frozen=True)
class StorageSettings:
    data_root: Path
    artifacts_root: Path
    knowledge_db: Path
    gbrain_repository: Path
    gbrain_home: Path


@dataclass(frozen=True)
class AppSettings:
    mineru: MinerUSettings
    model_api: ModelAPISettings
    storage: StorageSettings

    @classmethod
    def load(
        cls,
        dotenv_path: str | Path = ".env",
        environ: Mapping[str, str] | None = None,
        *,
        require_model_key: bool = True,
    ) -> "AppSettings":
        file_values = read_dotenv(Path(dotenv_path))
        values = dict(file_values)
        values.update({key: value for key, value in (environ or os.environ).items() if value != ""})

        model_key = values.get("MODEL_API_KEY") or values.get("LLM_API_KEY", "")
        if require_model_key and not model_key:
            raise ConfigurationError("MODEL_API_KEY is required")

        ca_raw = values.get("MINERU_CA_BUNDLE", "").strip()
        ca_bundle = Path(ca_raw).expanduser().resolve() if ca_raw else None
        if ca_bundle and not ca_bundle.is_file():
            raise ConfigurationError(f"MINERU_CA_BUNDLE does not exist: {ca_bundle}")

        model_base = values.get("MODEL_API_BASE_URL") or values.get("LLM_BASE_URL")
        if not model_base:
            model_base = "https://model-api.example.invalid/v1"

        data_root = Path(values.get("CONTRACT_BID_DATA_ROOT", "./data")).expanduser().resolve()
        artifacts_root = Path(values.get("CONTRACT_BID_ARTIFACTS_ROOT", "./artifacts")).expanduser().resolve()
        knowledge_db = Path(
            values.get("CONTRACT_BID_KNOWLEDGE_DB", "./runtime/knowledge.sqlite3")
        ).expanduser().resolve()

        return cls(
            mineru=MinerUSettings(
                base_url=_normalize_base_url(
                    values.get("MINERU_BASE_URL", "https://mineru.example.invalid")
                ),
                token=values.get("MINERU_TOKEN") or None,
                ca_bundle=ca_bundle,
                connect_timeout_s=_as_float(values, "MINERU_CONNECT_TIMEOUT_S", 30),
                read_timeout_s=_as_float(values, "MINERU_READ_TIMEOUT_S", 120),
                task_timeout_s=_as_float(values, "MINERU_TASK_TIMEOUT_S", 1800),
                poll_interval_s=_as_float(values, "MINERU_POLL_INTERVAL_S", 2),
            ),
            model_api=ModelAPISettings(
                base_url=_normalize_base_url(model_base, with_v1=True),
                api_key=model_key,
                timeout_s=_as_float(values, "MODEL_API_TIMEOUT_S", 120),
                embedding_model=values.get("EMBEDDING_MODEL", "text-embedding-v3"),
                embedding_dimensions=_as_int(values, "EMBEDDING_DIMENSIONS", 1024),
                rerank_model=values.get("RERANK_MODEL", "qwen3-rerank"),
                chat_model=values.get("CHAT_MODEL") or values.get("LLM_MODEL", "qwen-plus"),
            ),
            storage=StorageSettings(
                data_root=data_root,
                artifacts_root=artifacts_root,
                knowledge_db=knowledge_db,
                gbrain_repository=Path(
                    values.get("GBRAIN_REPOSITORY", "./references/gbrain")
                ).expanduser().resolve(),
                gbrain_home=Path(values.get("GBRAIN_HOME", "./runtime/gbrain")).expanduser().resolve(),
            ),
        )

    def redacted_snapshot(self) -> dict[str, object]:
        """Return operational configuration without secret values."""

        return {
            "mineru": {
                "base_url": self.mineru.base_url,
                "token": "<set>" if self.mineru.token else "<missing>",
                "tls_verify": True,
                "ca_bundle": str(self.mineru.ca_bundle) if self.mineru.ca_bundle else "<system>",
            },
            "model_api": {
                "base_url": self.model_api.base_url,
                "api_key": "<set>" if self.model_api.api_key else "<missing>",
                "embedding_model": self.model_api.embedding_model,
                "embedding_dimensions": self.model_api.embedding_dimensions,
                "rerank_model": self.model_api.rerank_model,
                "chat_model": self.model_api.chat_model,
            },
            "storage": {
                "data_root": str(self.storage.data_root),
                "artifacts_root": str(self.storage.artifacts_root),
                "knowledge_db": str(self.storage.knowledge_db),
                "gbrain_repository": str(self.storage.gbrain_repository),
                "gbrain_home": str(self.storage.gbrain_home),
            },
        }


def migrate_legacy_env(path: str | Path = ".env") -> bool:
    """Convert the observed two-line URL/token file to a normal dotenv file.

    The token is never returned or logged. The rewrite is atomic and the result
    is owner-readable only.
    """

    target = Path(path)
    if not target.exists():
        raise ConfigurationError(f"missing env file: {target}")
    raw = target.read_text(encoding="utf-8")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if any("=" in line for line in lines):
        read_dotenv(target)
        return False
    if len(lines) != 2 or not lines[0].startswith(("http://", "https://")) or not lines[1].startswith("sk-"):
        raise ConfigurationError("legacy .env must contain exactly one URL line and one sk- token line")

    model_base = _normalize_base_url(lines[0], with_v1=True)
    secret = lines[1]
    content = "\n".join(
        [
            "MINERU_BASE_URL=https://mineru.example.invalid",
            "MINERU_TOKEN=",
            "MINERU_CA_BUNDLE=",
            f"MODEL_API_BASE_URL={model_base}",
            f"MODEL_API_KEY={secret}",
            "EMBEDDING_MODEL=text-embedding-v3",
            "EMBEDDING_DIMENSIONS=1024",
            "RERANK_MODEL=qwen3-rerank",
            "CHAT_MODEL=qwen-plus",
            "MODEL_API_TIMEOUT_S=120",
            "CONTRACT_BID_DATA_ROOT=./data",
            "CONTRACT_BID_ARTIFACTS_ROOT=./artifacts",
            "CONTRACT_BID_KNOWLEDGE_DB=./runtime/knowledge.sqlite3",
            "GBRAIN_REPOSITORY=./references/gbrain",
            "GBRAIN_HOME=./runtime/gbrain",
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
    temporary.replace(target)
    return True
