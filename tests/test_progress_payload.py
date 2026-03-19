"""Progress payload enrichment regression checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.celery.tasks import _normalize_progress_payload


def main() -> int:
    started = _normalize_progress_payload("t1", {"status": "started", "message": "x"})
    if started.get("progress_percent") != 5:
        print("FAIL: started progress percent")
        return 1
    if started.get("eta_seconds") is None:
        print("FAIL: started eta missing")
        return 1
    if started.get("can_cancel") is not True:
        print("FAIL: started can_cancel")
        return 1
    if started.get("reconnect_after_seconds") is None:
        print("FAIL: started reconnect_after_seconds missing")
        return 1

    canceled = _normalize_progress_payload("t2", {"status": "canceled"})
    if canceled.get("type") != "error":
        print("FAIL: canceled type mapping")
        return 1
    if canceled.get("can_cancel") is not False:
        print("FAIL: canceled can_cancel")
        return 1
    if canceled.get("progress_percent") != 100:
        print("FAIL: canceled progress percent")
        return 1
    if canceled.get("reconnect_after_seconds") is None:
        print("FAIL: canceled reconnect_after_seconds missing")
        return 1

    print("PASS: progress payload checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
