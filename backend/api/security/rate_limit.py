"""Simple Redis-backed fixed-window rate limiting utilities."""

from __future__ import annotations

import os
import logging

import redis
from fastapi import HTTPException, Request, status

from backend.utils.redis_config import get_redis_url

logger = logging.getLogger(__name__)

RATE_LIMIT_PREFIX = os.getenv("RATE_LIMIT_PREFIX", "rate_limit")
DEFAULT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _key(scope: str, identity: str, window_sec: int) -> str:
    return f"{RATE_LIMIT_PREFIX}:{scope}:{identity}:{window_sec}"


def build_rate_limit_headers(limit: int, remaining: int, reset_sec: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(max(limit, 0)),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
        "X-RateLimit-Reset": str(max(reset_sec, 0)),
    }


def get_rate_limit_state(*, scope: str, identity: str, window_sec: int = DEFAULT_WINDOW_SEC) -> dict[str, int | str]:
    """Inspect current fixed-window counter state for a scope/identity key."""
    try:
        r = redis.from_url(get_redis_url())
        k = _key(scope, identity, window_sec)
        current = r.get(k)
        ttl = int(r.ttl(k))
        count = int(current or 0)
        if ttl < 0:
            ttl = window_sec
        return {
            "key": k,
            "count": count,
            "ttl_sec": ttl,
            "window_sec": window_sec,
        }
    except Exception as err:
        logger.warning(f"Rate limit inspect unavailable for scope={scope}: {err}")
        return {
            "key": _key(scope, identity, window_sec),
            "count": 0,
            "ttl_sec": window_sec,
            "window_sec": window_sec,
        }


def enforce_rate_limit(
    *,
    request: Request,
    scope: str,
    identity: str,
    limit: int,
    window_sec: int = DEFAULT_WINDOW_SEC,
    message: str = "Rate limit exceeded. Please retry later.",
) -> dict[str, str]:
    """Raise HTTP 429 when fixed-window counter exceeds limit.

    Best effort: if Redis is down, request is allowed.
    """
    if limit <= 0 or window_sec <= 0:
        return

    try:
        r = redis.from_url(get_redis_url())
        k = _key(scope, identity, window_sec)
        count = int(r.incr(k))
        if count == 1:
            r.expire(k, window_sec)

        ttl = int(r.ttl(k))
        if ttl < 0:
            ttl = window_sec

        remaining = max(limit - count, 0)
        headers = build_rate_limit_headers(limit=limit, remaining=remaining, reset_sec=ttl)

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=message,
                headers={
                    "Retry-After": str(ttl),
                    **headers,
                },
            )
        return headers
    except HTTPException:
        raise
    except Exception as err:
        logger.warning(f"Rate limit backend unavailable for scope={scope}: {err}")
        return {}


def enforce_ip_rate_limit(
    *,
    request: Request,
    scope: str,
    limit: int,
    window_sec: int = DEFAULT_WINDOW_SEC,
    message: str = "Too many requests from this IP. Please retry later.",
) -> dict[str, str]:
    ip = _client_ip(request)
    return enforce_rate_limit(
        request=request,
        scope=f"{scope}:ip",
        identity=ip,
        limit=limit,
        window_sec=window_sec,
        message=message,
    )


def enforce_user_rate_limit(
    *,
    request: Request,
    scope: str,
    user_id: str,
    limit: int,
    window_sec: int = DEFAULT_WINDOW_SEC,
    message: str = "Too many requests for this account. Please retry later.",
) -> dict[str, str]:
    return enforce_rate_limit(
        request=request,
        scope=f"{scope}:user",
        identity=user_id,
        limit=limit,
        window_sec=window_sec,
        message=message,
    )
