"""Minimal per-client sliding-window rate limit for the expensive /v2 endpoints (in memory, single process).

Why a dependency and not middleware: HTTPException raised from a route dependency passes through the app's CORS middleware, so a browser can read
the 429 message. Limits are per client IP; X-Forwarded-For is IGNORED unless PHYLLO_TRUST_PROXY=1 (otherwise a client could spoof its way around it).
Settings (read at call time): PHYLLO_RATE_LIMIT = requests per window (default 30; 0 disables), PHYLLO_RATE_WINDOW_S (default 60).
This does not replace a reverse-proxy limit: it is per process, resets on restart, and shared NAT users share one client IP.
"""
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

DEFAULT_LIMIT, DEFAULT_WINDOW = 30, 60
MAX_CLIENTS = 10000


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class RateLimiter:
    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self._hits.clear()

    def check(self, key, limit, window, now=None):
        """Return (allowed, retry_after_seconds). limit <= 0 disables the limiter."""
        if limit <= 0:
            return True, 0
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(q[0] + window - now) + 1)
            q.append(now)
            if len(self._hits) > MAX_CLIENTS:      # bound memory: drop clients with no recent hits
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - window]:
                    del self._hits[k]
            return True, 0


limiter = RateLimiter()


def client_key(request: Request):
    if os.environ.get("PHYLLO_TRUST_PROXY") == "1":
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request):
    limit = _int_env("PHYLLO_RATE_LIMIT", DEFAULT_LIMIT)
    window = max(1, _int_env("PHYLLO_RATE_WINDOW_S", DEFAULT_WINDOW))
    ok, retry = limiter.check(client_key(request), limit, window)
    if not ok:
        raise HTTPException(429, f"Rate limit exceeded: at most {limit} requests per {window} s per client. Try again in {retry} s.",
                            headers={"Retry-After": str(retry)})
