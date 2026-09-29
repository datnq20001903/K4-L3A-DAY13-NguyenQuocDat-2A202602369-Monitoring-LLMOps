"""Build a six-panel runtime dashboard snapshot from the JSONL log contract.

The lab permits any dashboard tool.  This script intentionally uses only the
repository's existing dependencies and emits a self-contained HTML dashboard,
so the runtime evidence can be opened without a separate service.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_ORDER = ("latency", "traffic", "errors", "cost", "tokens", "quality")
DEFAULT_PANEL_TITLES = {
    "latency": "Latency percentiles and TTFT",
    "traffic": "Request traffic",
    "errors": "Error rate and retrieval success",
    "cost": "Cost over time",
    "tokens": "Input and output tokens",
    "quality": "Quality proxy",
}


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _panel_config(dashboard_config: dict[str, Any], panel_id: str) -> dict[str, Any]:
    panels = dashboard_config.get("dashboard", {}).get("panels", [])
    return next((panel for panel in panels if panel.get("id") == panel_id), {"id": panel_id})


def _panel(
    dashboard_config: dict[str, Any], panel_id: str, values: dict[str, Any]
) -> dict[str, Any]:
    config = _panel_config(dashboard_config, panel_id)
    return {
        "title": config.get("title", DEFAULT_PANEL_TITLES[panel_id]),
        "unit": config.get("unit", ""),
        "values": _rounded(values),
        "threshold": config.get("threshold", {}),
    }


def compute_metrics(
    records: list[dict[str, Any]],
    dashboard_config: dict[str, Any],
    slo_config: dict[str, Any],
    *,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    """Compute all six contract panels over the latest configured time window."""

    dashboard = dashboard_config.get("dashboard", {})
    window_minutes = int(dashboard.get("time_range_minutes", 60))
    timestamped = [(record, parse_timestamp(record.get("ts"))) for record in records]
    timestamped = [(record, timestamp) for record, timestamp in timestamped if timestamp is not None]
    if end_time is None:
        end_time = max((timestamp for _, timestamp in timestamped), default=datetime.now(timezone.utc))
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    end_time = end_time.astimezone(timezone.utc)
    start_time = end_time - timedelta(minutes=window_minutes)
    window_records = [
        record for record, timestamp in timestamped if start_time <= timestamp <= end_time
    ]

    requests = [record for record in window_records if record.get("event") == "request_received"]
    failures = [record for record in window_records if record.get("event") == "request_failed"]
    responses = [record for record in window_records if record.get("event") == "response_sent"]

    latencies = [value for record in responses if (value := _number(record.get("latency_ms"))) is not None]
    ttfts = [value for record in responses if (value := _number(record.get("ttft_ms"))) is not None]
    costs = [value for record in responses if (value := _number(record.get("cost_usd"))) is not None]
    tokens_in = [value for record in responses if (value := _number(record.get("tokens_in"))) is not None]
    tokens_out = [value for record in responses if (value := _number(record.get("tokens_out"))) is not None]
    qualities = [value for record in responses if (value := _number(record.get("quality_score"))) is not None]
    retrieval_values = [record.get("tool_success") for record in responses if record.get("tool_success") is not None]
    retrieval_success = (
        sum(value is True for value in retrieval_values) / len(retrieval_values) * 100
        if retrieval_values
        else None
    )
    error_rate = len(failures) / len(requests) * 100 if requests else None
    error_breakdown = dict(sorted(Counter(record.get("error_type", "unknown") for record in failures).items()))

    cost_by_minute: defaultdict[str, float] = defaultdict(float)
    for record in responses:
        timestamp = parse_timestamp(record.get("ts"))
        cost = _number(record.get("cost_usd"))
        if timestamp is not None and cost is not None:
            minute = timestamp.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
            cost_by_minute[minute] += cost

    panels = {
        "latency": _panel(
            dashboard_config,
            "latency",
            {
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "p99": _percentile(latencies, 99),
                "ttft_p95": _percentile(ttfts, 95),
            },
        ),
        "traffic": _panel(
            dashboard_config,
            "traffic",
            {"count": len(requests), "rate_per_minute": len(requests) / window_minutes},
        ),
        "errors": _panel(
            dashboard_config,
            "errors",
            {
                "error_rate_pct": error_rate,
                "breakdown": error_breakdown,
                "retrieval_success_rate_pct": retrieval_success,
                "tool_success_rate_pct": retrieval_success,
            },
        ),
        "cost": _panel(
            dashboard_config,
            "cost",
            {"total": sum(costs), "by_minute": dict(sorted(cost_by_minute.items()))},
        ),
        "tokens": _panel(
            dashboard_config,
            "tokens",
            {"tokens_in": sum(tokens_in), "tokens_out": sum(tokens_out)},
        ),
        "quality": _panel(dashboard_config, "quality", {"mean": _mean(qualities)}),
    }

    primary_slo = slo_config.get("primary_slo", {})
    target = _number(primary_slo.get("target_percent"))
    budget = _number(primary_slo.get("error_budget_percent"))
    good_requests = sum(
        (_number(record.get("latency_ms")) is not None and _number(record.get("latency_ms")) <= 3000)
        for record in responses
    )
    observed_sli = good_requests / len(requests) * 100 if requests else None
    bad_percent = 100 - observed_sli if observed_sli is not None else None
    budget_consumed = bad_percent / budget * 100 if bad_percent is not None and budget else None

    return _rounded(
        {
            "title": dashboard.get("title", "Monitoring dashboard"),
            "source": "data/logs.jsonl",
            "window": {
                "minutes": window_minutes,
                "start": start_time.isoformat().replace("+00:00", "Z"),
                "end": end_time.isoformat().replace("+00:00", "Z"),
            },
            "panels": panels,
            "slo": {
                "target_percent": target,
                "error_budget_percent": budget,
                "observed_sli_percent": observed_sli,
                "budget_consumed_percent": budget_consumed,
            },
        }
    )


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL không hợp lệ tại dòng {line_number}: {exc}") from exc
        if isinstance(record, dict):
            records.append(record)
    return records


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, dict):
        if not value:
            return "none"
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def _threshold_text(threshold: dict[str, Any]) -> str:
    operators = {"lte": "≤", "gte": "≥"}
    if not threshold:
        return "n/a"
    return f"{threshold.get('aggregation', 'value')} {operators.get(threshold.get('operator'), threshold.get('operator', ''))} {threshold.get('value')}"


def render_html(snapshot: dict[str, Any], dashboard_config: dict[str, Any]) -> str:
    """Render a self-contained runtime dashboard with exactly six primary panels."""

    panel_markup: list[str] = []
    for panel_id in PANEL_ORDER:
        panel = snapshot["panels"][panel_id]
        config = _panel_config(dashboard_config, panel_id)
        rows = "".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(_format_value(value))}</td></tr>"
            for key, value in panel["values"].items()
        )
        panel_markup.append(
            "<article class=\"panel\">"
            f"<h2>{html.escape(str(panel['title']))}</h2>"
            f"<p class=\"unit\">Unit: {html.escape(str(panel['unit']))}</p>"
            f"<p class=\"range\">Time range: {snapshot['window']['minutes']} minutes</p>"
            f"<table>{rows}</table>"
            f"<p class=\"threshold\">Threshold/SLO line: {html.escape(_threshold_text(panel['threshold']))}</p>"
            f"<p class=\"query\">Source: {html.escape(str(config.get('source', snapshot['source'])))}</p>"
            "</article>"
        )

    window = snapshot["window"]
    slo = snapshot["slo"]
    slo_text = (
        f"SLO target {slo['target_percent']}%, error budget {slo['error_budget_percent']}%, "
        f"observed {slo['observed_sli_percent'] if slo['observed_sli_percent'] is not None else 'n/a'}%"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(str(snapshot['title']))}</title>
<style>
body {{ background:#101827; color:#e5edf7; font:15px system-ui,sans-serif; margin:0; padding:24px; }}
header {{ margin:0 auto 18px; max-width:1200px; }}
h1 {{ margin:0 0 8px; }}
.meta,.slo {{ color:#b9c7d8; margin:6px 0; }}
.grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin:auto; max-width:1200px; }}
.panel {{ background:#172337; border:1px solid #2c405e; border-radius:10px; padding:16px; min-height:220px; }}
.panel h2 {{ margin-top:0; font-size:18px; }}
.unit,.threshold {{ color:#9fe3b1; }}
.query {{ color:#8fa3bc; font-size:12px; }}
table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
th,td {{ border-bottom:1px solid #2c405e; padding:7px 4px; text-align:left; vertical-align:top; }}
th {{ color:#b9c7d8; font-weight:600; width:42%; }}
@media(max-width:750px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
<h1>{html.escape(str(snapshot['title']))}</h1>
<p class="meta">Source: {html.escape(snapshot['source'])} · Time range: {window['minutes']} minutes · {html.escape(window['start'])} → {html.escape(window['end'])}</p>
<p class="slo">{html.escape(slo_text)}</p>
</header>
<main class="grid">{''.join(panel_markup)}</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo dashboard HTML từ data/logs.jsonl")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--dashboard", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--slo", type=Path, default=REPO_ROOT / "config" / "slo.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.html",
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    records = load_records(args.logs)
    dashboard_config = yaml.safe_load(args.dashboard.read_text(encoding="utf-8"))
    slo_config = yaml.safe_load(args.slo.read_text(encoding="utf-8"))
    snapshot = compute_metrics(records, dashboard_config, slo_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(snapshot, dashboard_config), encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dashboard runtime: {args.output}")
    print(f"Window: {snapshot['window']['start']} -> {snapshot['window']['end']} ({snapshot['window']['minutes']} minutes)")
    print(f"SLO observed: {snapshot['slo']['observed_sli_percent']}%; budget consumed: {snapshot['slo']['budget_consumed_percent']}%")
    print("Panels: " + ", ".join(PANEL_ORDER))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
