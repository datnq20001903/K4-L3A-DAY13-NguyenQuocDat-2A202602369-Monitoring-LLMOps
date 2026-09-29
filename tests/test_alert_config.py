from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_alert_contract_has_three_complete_symptom_based_alerts() -> None:
    config = yaml.safe_load((ROOT / "config" / "alert_rules.yaml").read_text(encoding="utf-8"))
    alerts = config["alerts"]

    assert len(alerts) == 3
    for index, alert in enumerate(alerts, start=1):
        assert alert["name"] and "TODO" not in alert["name"]
        assert alert["condition"] and "TODO" not in alert["condition"]
        assert alert["duration"] and "TODO" not in alert["duration"]
        assert alert["severity"] in {"warning", "critical"}
        assert alert["type"] == "symptom-based"
        assert alert["channel"] == "slack"
        assert alert["slack_channel"].startswith("#")
        assert alert["owner"] and "TODO" not in alert["owner"]
        assert alert["runbook"] == f"docs/alerts.md#alert-{index}"

    runbook = (ROOT / "docs" / "alerts.md").read_text(encoding="utf-8")
    for index in range(1, 4):
        assert f"## Alert {index}" in runbook
        assert "Ba bước kiểm tra đầu tiên" in runbook
