"""Regression test for task webhook payload schema consistency.

Validates normalized webhook payloads contain expected fields and type mapping for:
- started
- retrying
- failed
- completed

Usage:
    python tests/test_task_webhook_schema.py
"""

from __future__ import annotations

import os
import sys
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.celery import tasks


class _CaptureHandler(BaseHTTPRequestHandler):
    payloads: list[dict] = []

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {"raw": raw_body}

        _CaptureHandler.payloads.append(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format, *_args):
        return


def _start_server() -> tuple[HTTPServer, int, threading.Thread]:
    server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def _assert_payload(payload: dict, expected_status: str, expected_type: str) -> list[str]:
    errors: list[str] = []

    if payload.get("task_id") != "schema-task-1":
        errors.append("task_id mismatch")
    if payload.get("status") != expected_status:
        errors.append(f"status mismatch (expected {expected_status}, got {payload.get('status')})")
    if payload.get("type") != expected_type:
        errors.append(f"type mismatch (expected {expected_type}, got {payload.get('type')})")

    return errors


def main() -> int:
    server, port, thread = _start_server()

    original_webhook_url = tasks.TASK_STATUS_WEBHOOK_URL
    original_webhook_token = tasks.TASK_WEBHOOK_TOKEN
    original_redis_from_url = tasks.redis.from_url

    # Avoid Redis dependency in this test.
    class _FakeRedis:
        def publish(self, *_args, **_kwargs):
            return 1

    tasks.redis.from_url = lambda *_args, **_kwargs: _FakeRedis()
    tasks.TASK_STATUS_WEBHOOK_URL = f"http://127.0.0.1:{port}/webhook"
    tasks.TASK_WEBHOOK_TOKEN = "schema-test-token"

    try:
        events = [
            {"status": "started", "message": "Task started"},
            {
                "status": "retrying",
                "message": "Task retry scheduled",
                "error": "temporary timeout",
                "error_code": "task_retry",
                "retry": {"attempt": 1, "max_retries": 2, "will_retry": True},
            },
            {
                "status": "failed",
                "message": "Task failed",
                "error": "final failure",
                "error_code": "task_failed",
                "retry": {"attempt": 2, "max_retries": 2, "will_retry": False},
            },
            {"status": "completed", "result": {"ok": True}},
        ]

        for event in events:
            tasks.publish_progress("schema-task-1", event)

        time.sleep(0.7)

        if len(_CaptureHandler.payloads) != 4:
            print(f"FAIL: expected 4 webhook payloads, got {len(_CaptureHandler.payloads)}")
            return 1

        expected = [
            ("started", "started"),
            ("retrying", "progress"),
            ("failed", "error"),
            ("completed", "result"),
        ]

        all_errors: list[str] = []
        for payload, (status_value, type_value) in zip(_CaptureHandler.payloads, expected):
            all_errors.extend(_assert_payload(payload, status_value, type_value))

        retry_payload = _CaptureHandler.payloads[1]
        if retry_payload.get("error_code") != "task_retry":
            all_errors.append("retry payload missing task_retry error_code")
        retry_block = retry_payload.get("retry") or {}
        if retry_block.get("attempt") != 1 or retry_block.get("will_retry") is not True:
            all_errors.append("retry payload has invalid retry metadata")

        failed_payload = _CaptureHandler.payloads[2]
        if failed_payload.get("error_code") != "task_failed":
            all_errors.append("failed payload missing task_failed error_code")

        completed_payload = _CaptureHandler.payloads[3]
        if not isinstance(completed_payload.get("result"), dict):
            all_errors.append("completed payload missing result object")

        if all_errors:
            print("FAIL:")
            for err in all_errors:
                print(f" - {err}")
            return 1

        print("PASS: webhook schema payload regression checks passed")
        return 0
    finally:
        tasks.TASK_STATUS_WEBHOOK_URL = original_webhook_url
        tasks.TASK_WEBHOOK_TOKEN = original_webhook_token
        tasks.redis.from_url = original_redis_from_url
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


if __name__ == "__main__":
    raise SystemExit(main())
