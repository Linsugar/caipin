import json
import logging
from copy import deepcopy
from typing import Any


logger = logging.getLogger("food_analysis")


SECRET_KEYS = {"authorization", "api_key", "deepseek_api_key", "qwen_api_key", "amap_key", "client_key"}


def truncate_for_log(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"


def redact_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if key_lower in SECRET_KEYS or "authorization" in key_lower:
                result[key] = "***"
            else:
                result[key] = redact_for_log(item)
        return result
    if isinstance(value, list):
        return [redact_for_log(item) for item in value]
    if isinstance(value, str):
        if value.startswith("Bearer sk-") or value.startswith("sk-"):
            return "***"
        if value.startswith("data:image/") and "base64," in value:
            prefix = value.split("base64,", 1)[0] + "base64,"
            return f"{prefix}<redacted:{len(value)} chars>"
    return value


def log_json(label: str, payload: Any, max_chars: int = 4000) -> None:
    safe_payload = redact_for_log(deepcopy(payload))
    try:
        text = json.dumps(safe_payload, ensure_ascii=False, default=str)
    except TypeError:
        text = str(safe_payload)
    logger.info("%s %s", label, truncate_for_log(text, max_chars=max_chars))
