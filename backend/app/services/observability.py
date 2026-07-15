"""Lightweight in-process observability counters and metric rendering."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from time import monotonic


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class ObservabilityRegistry:
    """Process-local counters used by the metrics endpoint."""

    _instance: "ObservabilityRegistry | None" = None

    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at = monotonic()
        self._http_requests: Counter[tuple[str, str, str]] = Counter()
        self._http_duration_totals_ms: Counter[tuple[str, str]] = Counter()
        self._http_duration_counts: Counter[tuple[str, str]] = Counter()
        self._copilot_runs: Counter[tuple[str, str]] = Counter()
        self._access_audit_events: Counter[tuple[str, str]] = Counter()

    @classmethod
    def get_instance(cls) -> "ObservabilityRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        method_key = method.upper()
        path_key = path or "unknown"
        status_key = str(status_code)
        with self._lock:
            self._http_requests[(method_key, path_key, status_key)] += 1
            self._http_duration_totals_ms[(method_key, path_key)] += max(duration_ms, 0.0)
            self._http_duration_counts[(method_key, path_key)] += 1

    def record_copilot_run(self, *, template: str, status: str) -> None:
        with self._lock:
            self._copilot_runs[(template or "unknown", status or "unknown")] += 1

    def record_access_audit(self, *, action: str, result: str) -> None:
        with self._lock:
            self._access_audit_events[(action or "unknown", result or "unknown")] += 1

    def render_prometheus(self, *, guardrail_counters: dict[str, int]) -> str:
        with self._lock:
            http_requests = dict(self._http_requests)
            http_duration_totals = dict(self._http_duration_totals_ms)
            http_duration_counts = dict(self._http_duration_counts)
            copilot_runs = dict(self._copilot_runs)
            access_audit_events = dict(self._access_audit_events)
            uptime_seconds = max(monotonic() - self._started_at, 0.0)

        lines = [
            "# HELP medmemory_uptime_seconds Time since the API process started.",
            "# TYPE medmemory_uptime_seconds gauge",
            f"medmemory_uptime_seconds {uptime_seconds:.3f}",
            "# HELP medmemory_http_requests_total Count of HTTP requests handled by the API.",
            "# TYPE medmemory_http_requests_total counter",
        ]
        if http_requests:
            for (method, path, status), value in sorted(http_requests.items()):
                lines.append(
                    'medmemory_http_requests_total'
                    f'{{method="{_escape_label(method)}",path="{_escape_label(path)}",status="{_escape_label(status)}"}} {value}'
                )
        else:
            lines.append('medmemory_http_requests_total{method="none",path="none",status="none"} 0')

        lines.extend(
            [
                "# HELP medmemory_http_request_duration_ms_total Total request duration in milliseconds.",
                "# TYPE medmemory_http_request_duration_ms_total counter",
            ]
        )
        if http_duration_totals:
            for (method, path), value in sorted(http_duration_totals.items()):
                lines.append(
                    'medmemory_http_request_duration_ms_total'
                    f'{{method="{_escape_label(method)}",path="{_escape_label(path)}"}} {value:.3f}'
                )
        else:
            lines.append('medmemory_http_request_duration_ms_total{method="none",path="none"} 0')

        lines.extend(
            [
                "# HELP medmemory_http_request_duration_ms_count Count of request duration samples.",
                "# TYPE medmemory_http_request_duration_ms_count counter",
            ]
        )
        if http_duration_counts:
            for (method, path), value in sorted(http_duration_counts.items()):
                lines.append(
                    'medmemory_http_request_duration_ms_count'
                    f'{{method="{_escape_label(method)}",path="{_escape_label(path)}"}} {value}'
                )
        else:
            lines.append('medmemory_http_request_duration_ms_count{method="none",path="none"} 0')

        lines.extend(
            [
                "# HELP medmemory_clinician_agent_runs_total Count of clinician copilot runs created.",
                "# TYPE medmemory_clinician_agent_runs_total counter",
            ]
        )
        if copilot_runs:
            for (template, status), value in sorted(copilot_runs.items()):
                lines.append(
                    'medmemory_clinician_agent_runs_total'
                    f'{{template="{_escape_label(template)}",status="{_escape_label(status)}"}} {value}'
                )
        else:
            lines.append('medmemory_clinician_agent_runs_total{template="none",status="none"} 0')

        lines.extend(
            [
                "# HELP medmemory_access_audit_events_total Count of access audit events.",
                "# TYPE medmemory_access_audit_events_total counter",
            ]
        )
        if access_audit_events:
            for (action, result), value in sorted(access_audit_events.items()):
                lines.append(
                    'medmemory_access_audit_events_total'
                    f'{{action="{_escape_label(action)}",result="{_escape_label(result)}"}} {value}'
                )
        else:
            lines.append('medmemory_access_audit_events_total{action="none",result="none"} 0')

        lines.extend(
            [
                "# HELP medmemory_guardrail_events_total Count of guardrail events.",
                "# TYPE medmemory_guardrail_events_total counter",
            ]
        )
        if guardrail_counters:
            for event, value in sorted(guardrail_counters.items()):
                lines.append(
                    f'medmemory_guardrail_events_total{{event="{_escape_label(event)}"}} {value}'
                )
        else:
            lines.append('medmemory_guardrail_events_total{event="none"} 0')

        return "\n".join(lines) + "\n"
