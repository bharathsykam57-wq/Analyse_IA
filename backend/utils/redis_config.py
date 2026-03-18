import os
from urllib.parse import urlparse, urlunparse


def get_redis_url() -> str:
    """Return Redis URL with safe defaults for Upstash.

    If REDIS_URL points to Upstash using `redis://`, upgrade to `rediss://`
    because Upstash requires TLS.
    """
    raw_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(raw_url)

    if parsed.scheme == "redis" and parsed.hostname and parsed.hostname.endswith("upstash.io"):
        return urlunparse(("rediss", parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    return raw_url
