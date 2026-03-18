"""Lightweight in-process Prometheus-style metrics for Analyse_IA.

No external dependency required: exposes metrics in text format compatible with
Prometheus scraping conventions.
"""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Dict, Iterable, Tuple


_LOCK = Lock()

_HTTP_REQUESTS_TOTAL: Dict[Tuple[str, str, str], int] = defaultdict(int)
_HTTP_REQUEST_DURATION_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
_HTTP_REQUEST_DURATION_COUNTS: Dict[Tuple[str, str], Dict[float, int]] = defaultdict(
    lambda: defaultdict(int)
)
_HTTP_REQUEST_DURATION_SUM: Dict[Tuple[str, str], float] = defaultdict(float)
_HTTP_REQUEST_DURATION_COUNT: Dict[Tuple[str, str], int] = defaultdict(int)

_TASK_EVENTS_TOTAL: Dict[Tuple[str, str], int] = defaultdict(int)
_TASK_DURATION_BUCKETS = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
_TASK_DURATION_COUNTS: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
_TASK_DURATION_SUM: Dict[str, float] = defaultdict(float)
_TASK_DURATION_COUNT: Dict[str, int] = defaultdict(int)


def _escape_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def _format_labels(labels: Dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{key}="{_escape_label(str(value))}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    method_u = method.upper()
    status_s = str(status_code)

    with _LOCK:
        _HTTP_REQUESTS_TOTAL[(method_u, path, status_s)] += 1

        histogram_key = (method_u, path)
        _HTTP_REQUEST_DURATION_SUM[histogram_key] += max(duration_seconds, 0.0)
        _HTTP_REQUEST_DURATION_COUNT[histogram_key] += 1

        for bucket in _HTTP_REQUEST_DURATION_BUCKETS:
            if duration_seconds <= bucket:
                _HTTP_REQUEST_DURATION_COUNTS[histogram_key][bucket] += 1


def record_task_event(task_name: str, status: str) -> None:
    with _LOCK:
        _TASK_EVENTS_TOTAL[(task_name, status)] += 1


def observe_task_duration(task_name: str, duration_seconds: float) -> None:
    value = max(duration_seconds, 0.0)
    with _LOCK:
        _TASK_DURATION_SUM[task_name] += value
        _TASK_DURATION_COUNT[task_name] += 1

        for bucket in _TASK_DURATION_BUCKETS:
            if value <= bucket:
                _TASK_DURATION_COUNTS[task_name][bucket] += 1


def _render_counter(metric_name: str, labels_to_value: Dict[Tuple[str, ...], int], label_names: Iterable[str]) -> list[str]:
    lines: list[str] = []
    label_names = list(label_names)
    for label_values, value in sorted(labels_to_value.items()):
        labels = {name: str(v) for name, v in zip(label_names, label_values)}
        lines.append(f"{metric_name}{_format_labels(labels)} {value}")
    return lines


def render_prometheus_text() -> str:
    with _LOCK:
        lines: list[str] = []

        lines.append("# HELP analyseia_up Service health status (1=up)")
        lines.append("# TYPE analyseia_up gauge")
        lines.append("analyseia_up 1")

        lines.append("# HELP analyseia_http_requests_total Total HTTP requests")
        lines.append("# TYPE analyseia_http_requests_total counter")
        lines.extend(
            _render_counter(
                "analyseia_http_requests_total",
                _HTTP_REQUESTS_TOTAL,
                ["method", "path", "status"],
            )
        )

        lines.append("# HELP analyseia_http_request_duration_seconds HTTP request duration seconds")
        lines.append("# TYPE analyseia_http_request_duration_seconds histogram")
        for (method, path), bucket_counts in sorted(_HTTP_REQUEST_DURATION_COUNTS.items()):
            cumulative = 0
            for bucket in _HTTP_REQUEST_DURATION_BUCKETS:
                cumulative = bucket_counts.get(bucket, cumulative)
                labels = {
                    "method": method,
                    "path": path,
                    "le": str(bucket),
                }
                lines.append(
                    f"analyseia_http_request_duration_seconds_bucket{_format_labels(labels)} {cumulative}"
                )

            labels_inf = {"method": method, "path": path, "le": "+Inf"}
            count_value = _HTTP_REQUEST_DURATION_COUNT.get((method, path), 0)
            sum_value = _HTTP_REQUEST_DURATION_SUM.get((method, path), 0.0)
            lines.append(
                f"analyseia_http_request_duration_seconds_bucket{_format_labels(labels_inf)} {count_value}"
            )
            lines.append(
                f"analyseia_http_request_duration_seconds_sum{_format_labels({'method': method, 'path': path})} {sum_value}"
            )
            lines.append(
                f"analyseia_http_request_duration_seconds_count{_format_labels({'method': method, 'path': path})} {count_value}"
            )

        lines.append("# HELP analyseia_celery_task_events_total Total Celery task events by status")
        lines.append("# TYPE analyseia_celery_task_events_total counter")
        lines.extend(
            _render_counter(
                "analyseia_celery_task_events_total",
                _TASK_EVENTS_TOTAL,
                ["task_name", "status"],
            )
        )

        lines.append("# HELP analyseia_celery_task_duration_seconds Celery task duration seconds")
        lines.append("# TYPE analyseia_celery_task_duration_seconds histogram")
        for task_name, bucket_counts in sorted(_TASK_DURATION_COUNTS.items()):
            cumulative = 0
            for bucket in _TASK_DURATION_BUCKETS:
                cumulative = bucket_counts.get(bucket, cumulative)
                labels = {
                    "task_name": task_name,
                    "le": str(bucket),
                }
                lines.append(
                    f"analyseia_celery_task_duration_seconds_bucket{_format_labels(labels)} {cumulative}"
                )

            count_value = _TASK_DURATION_COUNT.get(task_name, 0)
            sum_value = _TASK_DURATION_SUM.get(task_name, 0.0)
            lines.append(
                f"analyseia_celery_task_duration_seconds_bucket{_format_labels({'task_name': task_name, 'le': '+Inf'})} {count_value}"
            )
            lines.append(
                f"analyseia_celery_task_duration_seconds_sum{_format_labels({'task_name': task_name})} {sum_value}"
            )
            lines.append(
                f"analyseia_celery_task_duration_seconds_count{_format_labels({'task_name': task_name})} {count_value}"
            )

        return "\n".join(lines) + "\n"
