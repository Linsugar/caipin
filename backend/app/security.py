import secrets
import time
from dataclasses import dataclass, field

from fastapi import Header, HTTPException, Request

from app.config import SecurityConfig


@dataclass
class InMemoryRateStore:
    counters: dict[str, tuple[int, int]] = field(default_factory=dict)

    def increment(self, key: str, window_seconds: int) -> int:
        now = int(time.time())
        window_start = now - (now % window_seconds)
        current_window, count = self.counters.get(key, (window_start, 0))
        if current_window != window_start:
            count = 0
            current_window = window_start
        count += 1
        self.counters[key] = (current_window, count)
        return count


class SecurityService:
    def __init__(self, config: SecurityConfig, redis_client=None, memory_store: InMemoryRateStore | None = None) -> None:
        self.config = config
        self.redis_client = redis_client
        self.memory_store = memory_store or InMemoryRateStore()

    def require_api_key(self, client_key: str | None) -> str:
        if not self.config.enabled:
            return client_key or "security-disabled"
        if not client_key:
            raise HTTPException(status_code=401, detail="missing api key")
        if not any(secrets.compare_digest(client_key, allowed) for allowed in self.config.client_keys):
            raise HTTPException(status_code=403, detail="invalid api key")
        return client_key

    def check_minute_limit(self, client_key: str, route_name: str) -> None:
        key = f"rate:{route_name}:{client_key}"
        count = self._increment(key, 60)
        if count > self.config.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="rate limit exceeded")

    def check_daily_analysis_limit(self, client_key: str) -> None:
        key = f"daily:analysis:{client_key}"
        count = self._increment(key, 24 * 60 * 60)
        if count > self.config.analysis_limit_per_day:
            raise HTTPException(status_code=429, detail="daily analysis limit exceeded")

    def _increment(self, key: str, window_seconds: int) -> int:
        if self.redis_client is not None:
            count = self.redis_client.incr(key)
            if count == 1:
                self.redis_client.expire(key, window_seconds)
            return int(count)
        return self.memory_store.increment(key, window_seconds)


def get_client_identity(request: Request, client_key: str) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    ip = forwarded_for.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return f"{client_key}:{ip}"
