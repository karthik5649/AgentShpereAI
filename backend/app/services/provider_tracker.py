import threading
import time
from typing import Any


class ProviderTracker:
    """Thread-safe in-memory tracker for provider health, quota and request metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._providers: dict[str, dict[str, Any]] = {
            "serper": {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None},
            "crunchbase": {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None},
            "apollo": {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None},
            "hunter": {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None},
        }

    def record_request(self, provider: str) -> None:
        with self._lock:
            p = self._providers.setdefault(provider, {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None})
            p["requests"] += 1
            p["last_used"] = time.time()

    def record_success(self, provider: str) -> None:
        with self._lock:
            p = self._providers.setdefault(provider, {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None})
            p["available"] = True
            p["last_error"] = None

    def record_failure(self, provider: str, error: str) -> None:
        with self._lock:
            p = self._providers.setdefault(provider, {"available": True, "requests": 0, "errors": 0, "last_error": None, "last_used": None})
            p["errors"] += 1
            p["last_error"] = str(error)
            # If consecutive error count exceeds 5, mark as temporarily degraded
            if p["errors"] >= 5 and p["requests"] > 0 and (p["errors"] / p["requests"] > 0.8):
                p["available"] = False

    def is_available(self, provider: str) -> bool:
        with self._lock:
            return self._providers.get(provider, {}).get("available", True)

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                provider: {
                    "available": data["available"],
                    "requests": data["requests"],
                    "errors": data["errors"],
                    "last_error": data["last_error"],
                    "last_used_seconds_ago": round(time.time() - data["last_used"], 1) if data["last_used"] else None,
                }
                for provider, data in self._providers.items()
            }


# Singleton instance
provider_tracker = ProviderTracker()
