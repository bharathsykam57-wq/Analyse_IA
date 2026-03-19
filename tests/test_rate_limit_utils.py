"""Rate limiting utility regression checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from starlette.requests import Request

import backend.api.security.rate_limit as rl


class _FakeRedis:
    def __init__(self):
        self.counters = {}

    def incr(self, key):
        self.counters[key] = int(self.counters.get(key, 0)) + 1
        return self.counters[key]

    def expire(self, key, window_sec):
        return True


def _request_with_ip(ip: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", ip.encode("utf-8"))],
        "client": (ip, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def main() -> int:
    original_from_url = rl.redis.from_url
    fake = _FakeRedis()

    try:
        rl.redis.from_url = lambda *_args, **_kwargs: fake

        req = _request_with_ip("10.0.0.1")
        rl.enforce_ip_rate_limit(request=req, scope="unit", limit=2, window_sec=60)
        rl.enforce_ip_rate_limit(request=req, scope="unit", limit=2, window_sec=60)

        try:
            rl.enforce_ip_rate_limit(request=req, scope="unit", limit=2, window_sec=60)
            print("FAIL: expected 429 not raised")
            return 1
        except HTTPException as exc:
            if exc.status_code != 429:
                print(f"FAIL: expected 429 got {exc.status_code}")
                return 1

        print("PASS: rate limit utility checks passed")
        return 0
    finally:
        rl.redis.from_url = original_from_url


if __name__ == "__main__":
    raise SystemExit(main())
