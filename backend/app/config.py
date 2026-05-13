import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    url: str = "mysql+pymysql://food:foodpass@mysql:3306/food_analysis?charset=utf8mb4"


class RedisConfig(BaseModel):
    url: str = "redis://redis:6379/0"


class StorageConfig(BaseModel):
    root_dir: str = "storage/uploads"
    max_bytes: int = 10 * 1024 * 1024
    keep_days: int = 7


class ProviderConfig(BaseModel):
    use_mock_models: bool = True
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vision_model: str = "qwen-vl-plus"
    amap_key: str = ""
    request_timeout_seconds: int = 45


class SecurityConfig(BaseModel):
    enabled: bool = True
    client_keys: list[str] = Field(default_factory=lambda: ["dev-client-key"])
    header_name: str = "X-Client-Key"
    rate_limit_per_minute: int = 30
    analysis_limit_per_day: int = 200


class LoggingConfig(BaseModel):
    print_request_response: bool = True
    print_model_request_response: bool = True
    max_body_chars: int = 4000


class AppConfig(BaseModel):
    app_name: str = "food-analysis-backend"
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


ENV_MAP = {
    "QWEN_API_KEY": ("providers", "qwen_api_key"),
    "QWEN_BASE_URL": ("providers", "qwen_base_url"),
    "QWEN_VISION_MODEL": ("providers", "qwen_vision_model"),
    "DEEPSEEK_API_KEY": ("providers", "deepseek_api_key"),
    "DEEPSEEK_BASE_URL": ("providers", "deepseek_base_url"),
    "DEEPSEEK_MODEL": ("providers", "deepseek_model"),
    "AMAP_KEY": ("providers", "amap_key"),
    "USE_MOCK_MODELS": ("providers", "use_mock_models"),
    "CLIENT_KEYS": ("security", "client_keys"),
    "RATE_LIMIT_PER_MINUTE": ("security", "rate_limit_per_minute"),
    "DATABASE_URL": ("database", "url"),
    "REDIS_URL": ("redis", "url"),
}


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    for env_var, (section, key) in ENV_MAP.items():
        value = os.environ.get(env_var)
        if value is not None:
            data.setdefault(section, {})[key] = _coerce_env(value, type(data.get(section, {}).get(key)))
    return data


def _coerce_env(value: str, sample: object) -> Any:
    if isinstance(sample, bool):
        return value.lower() in ("1", "true", "yes")
    if isinstance(sample, int):
        return int(value)
    if isinstance(sample, list):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


@lru_cache(maxsize=1)
def load_config(config_path: str | None = None) -> AppConfig:
    path = Path(config_path or "config/app.yml")
    data: dict[str, Any] = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged = _deep_merge(AppConfig().model_dump(), data)
    merged = _apply_env_overrides(merged)
    return AppConfig.model_validate(merged)
