from __future__ import annotations

import json
from pathlib import Path

from app.logging_config import scrub_event
from scripts import validate_logs


def test_validator_detects_raw_vietnamese_phone(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    log_path = tmp_path / "logs.jsonl"
    record = {
        "ts": "2026-08-10T00:00:00Z",
        "level": "info",
        "service": "api",
        "event": "request_received",
        "correlation_id": "req-12345678",
        "user_id_hash": "abc123",
        "session_id": "session-01",
        "feature": "monitoring",
        "model": "fake-llm",
        "payload": {"message_preview": "Contact 090 123 4567"},
    }
    log_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(validate_logs, "LOG_PATH", log_path)

    validate_logs.main()

    output = capsys.readouterr().out
    assert "Potential PII leaks detected: 1" in output
    assert "phone_vn" in output
    assert "[FAILED] PII scrubbing" in output


def test_scrub_event_redacts_all_string_values_before_rendering() -> None:
    event = {
        "event": "request_failed",
        "error_detail": "student@vinuni.edu.vn called 090 123 4567",
        "payload": {
            "nested": ["CCCD 012345678901", {"card": "4111-1111-1111-1111"}],
        },
    }

    scrubbed = scrub_event(None, "error", event)
    rendered = json.dumps(scrubbed, ensure_ascii=False)

    assert "student@vinuni.edu.vn" not in rendered
    assert "090 123 4567" not in rendered
    assert "012345678901" not in rendered
    assert "4111-1111-1111-1111" not in rendered
