"""Lightweight in-memory metrics collector — no external dependencies."""
import time
import threading
from collections import defaultdict, deque

_lock = threading.Lock()

_metrics = {
    "requests_total": defaultdict(int),        # (method, path, status) -> count
    "request_duration": deque(maxlen=1000),     # (method, path, duration)
    "startup_time": time.time(),
}


def record_request(method: str, path: str, status: int, duration: float):
    with _lock:
        _metrics["requests_total"][(method, path, str(status))] += 1
        _metrics["request_duration"].append((method, path, duration))


def render_prometheus() -> str:
    lines: list[str] = []

    # uptime
    uptime = time.time() - _metrics["startup_time"]
    lines.append("# HELP coauthor_uptime_seconds Seconds since server start")
    lines.append("# TYPE coauthor_uptime_seconds gauge")
    lines.append(f"coauthor_uptime_seconds {uptime:.1f}")
    lines.append("")

    # requests_total
    lines.append("# HELP coauthor_requests_total Total HTTP requests")
    lines.append("# TYPE coauthor_requests_total counter")
    with _lock:
        for (method, path, status), count in sorted(_metrics["requests_total"].items()):
            lines.append(
                f'coauthor_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )
    lines.append("")

    # avg duration
    with _lock:
        durations = [d for _, _, d in _metrics["request_duration"]]
    if durations:
        avg = sum(durations) / len(durations)
        lines.append("# HELP coauthor_request_duration_avg_seconds Average request duration (last 1000)")
        lines.append("# TYPE coauthor_request_duration_avg_seconds gauge")
        lines.append(f"coauthor_request_duration_avg_seconds {avg:.4f}")
        lines.append("")

    return "\n".join(lines) + "\n"
