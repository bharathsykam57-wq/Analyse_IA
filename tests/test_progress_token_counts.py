"""Progress payload token count regression checks."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.celery.tasks import _normalize_progress_payload


def main() -> int:
    payload = _normalize_progress_payload(
        "tok-1",
        {
            "status": "processing",
            "input_text": "hello world",
            "output_text": "this is a generated response",
        },
    )

    if payload.get("token_count_input", 0) <= 0:
        print("FAIL: token_count_input not populated")
        return 1

    if payload.get("token_count_output", 0) <= 0:
        print("FAIL: token_count_output not populated")
        return 1

    expected_total = int(payload.get("token_count_input", 0)) + int(payload.get("token_count_output", 0))
    if payload.get("token_count_total") != expected_total:
        print("FAIL: token_count_total mismatch")
        return 1

    print("PASS: progress token count checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
