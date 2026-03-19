"""WebSocket heartbeat payload regression checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.websocket.manager import _heartbeat_payload


def main() -> int:
    payload = _heartbeat_payload("hb-1")

    if payload.get("task_id") != "hb-1":
        print("FAIL: heartbeat task_id mismatch")
        return 1
    if payload.get("type") != "heartbeat":
        print("FAIL: heartbeat type mismatch")
        return 1
    if payload.get("status") != "processing":
        print("FAIL: heartbeat status mismatch")
        return 1
    if payload.get("reconnect_after_seconds") is None:
        print("FAIL: heartbeat reconnect_after_seconds missing")
        return 1
    if payload.get("emitted_at") is None:
        print("FAIL: heartbeat emitted_at missing")
        return 1

    print("PASS: websocket heartbeat payload checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
