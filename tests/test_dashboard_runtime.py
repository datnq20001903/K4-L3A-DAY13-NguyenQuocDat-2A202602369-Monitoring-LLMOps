from __future__ import annotations

from datetime import datetime, timezone

from scripts.dashboard_snapshot import compute_metrics, render_html


def _config() -> tuple[dict, dict]:
    dashboard = {
        "dashboard": {
            "time_range_minutes": 60,
            "panels": [
                {"id": "latency", "threshold": {"aggregation": "p95", "operator": "lte", "value": 3000}},
                {"id": "traffic", "threshold": {"aggregation": "rate_per_minute", "operator": "gte", "value": 1}},
                {"id": "errors", "threshold": {"aggregation": "error_rate_pct", "operator": "lte", "value": 2}},
                {"id": "cost", "threshold": {"aggregation": "total", "operator": "lte", "value": 2.5}},
                {"id": "tokens", "threshold": {"aggregation": "sum_by_field", "operator": "lte", "value": 50000}},
                {"id": "quality", "threshold": {"aggregation": "mean", "operator": "gte", "value": 0.75}},
            ],
        }
    }
    slo = {"primary_slo": {"target_percent": 99.5, "error_budget_percent": 0.5}}
    return dashboard, slo


def test_compute_metrics_uses_six_log_panels_and_error_budget() -> None:
    end = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
    records = [
        {"event": "request_received", "ts": "2026-09-29T04:59:00Z"},
        {"event": "request_received", "ts": "2026-09-29T04:58:00Z"},
        {"event": "request_failed", "error_type": "timeout", "ts": "2026-09-29T04:59:30Z"},
        {
            "event": "response_sent",
            "ts": "2026-09-29T04:59:10Z",
            "latency_ms": 1000,
            "ttft_ms": 100,
            "cost_usd": 0.01,
            "tokens_in": 10,
            "tokens_out": 20,
            "quality_score": 0.8,
            "tool_success": True,
        },
        {
            "event": "response_sent",
            "ts": "2026-09-29T04:58:10Z",
            "latency_ms": 2000,
            "ttft_ms": 200,
            "cost_usd": 0.02,
            "tokens_in": 30,
            "tokens_out": 40,
            "quality_score": 0.9,
            "tool_success": False,
        },
    ]
    dashboard, slo = _config()

    snapshot = compute_metrics(records, dashboard, slo, end_time=end)

    assert set(snapshot["panels"]) == {"latency", "traffic", "errors", "cost", "tokens", "quality"}
    assert snapshot["window"]["minutes"] == 60
    assert snapshot["panels"]["latency"]["values"]["p95"] == 1950
    assert snapshot["panels"]["traffic"]["values"]["count"] == 2
    assert snapshot["panels"]["errors"]["values"]["error_rate_pct"] == 50.0
    assert snapshot["panels"]["errors"]["values"]["retrieval_success_rate_pct"] == 50.0
    assert snapshot["panels"]["cost"]["values"]["total"] == 0.03
    assert snapshot["panels"]["tokens"]["values"] == {"tokens_in": 40, "tokens_out": 60}
    assert snapshot["panels"]["quality"]["values"]["mean"] == 0.85
    assert snapshot["slo"]["error_budget_percent"] == 0.5


def test_render_html_contains_exactly_six_panels_and_thresholds() -> None:
    dashboard, slo = _config()
    snapshot = compute_metrics([], dashboard, slo, end_time=datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc))

    html = render_html(snapshot, dashboard)

    assert html.count('<article class="panel">') == 6
    assert html.count('class="range">Time range: 60 minutes') == 6
    assert "threshold" in html.lower()
    assert "Latency percentiles and TTFT" in html
