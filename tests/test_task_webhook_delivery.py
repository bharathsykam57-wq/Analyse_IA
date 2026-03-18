"""Webhook delivery smoke test for Celery task status events.

Validates that webhook notifications are sent even when Redis publish fails.
This test runs locally and does not require external services.

Usage:
    python tests/test_task_webhook_delivery.py
"""

from __future__ import annotations

import json
import threading
import time
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.celery import tasks


class _WebhookHandler(BaseHTTPRequestHandler):
    payloads: list[dict] = []
    headers_seen: list[dict] = []

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}

        _WebhookHandler.payloads.append(parsed)
        _WebhookHandler.headers_seen.append(dict(self.headers))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        return


def _start_server() -> tuple[HTTPServer, int, threading.Thread]:
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def main() -> int:
    server, port, thread = _start_server()

    original_webhook_url = tasks.TASK_STATUS_WEBHOOK_URL
    original_webhook_token = tasks.TASK_WEBHOOK_TOKEN
    original_redis_from_url = tasks.redis.from_url

    # Force Redis publish to fail quickly.
    def _redis_fail(*_args, **_kwargs):
        raise RuntimeError("mock redis unavailable")

    tasks.redis.from_url = _redis_fail
    tasks.TASK_STATUS_WEBHOOK_URL = f"http://127.0.0.1:{port}/task-status"
    tasks.TASK_WEBHOOK_TOKEN = "webhook-test-token"

    try:
        tasks.publish_progress(
            "task-webhook-test-1",
            {
                "status": "started",
                "message": "Task started",
            },
        )

        time.sleep(0.5)

        if not _WebhookHandler.payloads:
            print("FAIL: no webhook payload received")
            return 1

        payload = _WebhookHandler.payloads[0]
        auth_header = _WebhookHandler.headers_seen[0].get("Authorization")

        checks = {
            "task_id": payload.get("task_id") == "task-webhook-test-1",
            "status": payload.get("status") == "started",
            "type": payload.get("type") == "started",
            "auth_header": auth_header == "Bearer webhook-test-token",
        }

        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            print(f"FAIL: checks failed -> {failed}")
            print(f"Payload: {payload}")
            print(f"Authorization: {auth_header}")
            return 1

        print("PASS: webhook received normalized payload despite Redis failure")
        return 0
    finally:
        tasks.redis.from_url = original_redis_from_url
        tasks.TASK_STATUS_WEBHOOK_URL = original_webhook_url
        tasks.TASK_WEBHOOK_TOKEN = original_webhook_token
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


if __name__ == "__main__":
    raise SystemExit(main())
