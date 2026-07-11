"""Tests del comando CLI defense-correlate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def _write_rule(rules_dir: Path) -> None:
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "high_risk.yaml").write_text(
        "id: test.high_risk\n"
        "title: X\n"
        "severity: medium\n"
        "logsource: tool_audit\n"
        "filter:\n"
        "  allowed: true\n"
        "  category: [bounded_fuzzing]\n"
        "threshold_count: 1\n",
        encoding="utf-8",
    )


def test_defense_correlate_no_matches_exits_zero(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    _write_rule(rules_dir)
    audit = tmp_path / "audit.jsonl"
    audit.write_text(
        json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "allowed": True, "category": "passive_recon"})
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "defense-correlate",
            "--rules-dir",
            str(rules_dir),
            "--tool-audit",
            str(audit),
            "--alerts-out",
            str(tmp_path / "alerts.jsonl"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Sin coincidencias" in result.output


def test_defense_correlate_match_persists_and_exits_nonzero_for_high(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "repeated_denied.yaml").write_text(
        "id: test.repeated_denied\n"
        "title: X\n"
        "severity: high\n"
        "logsource: tool_audit\n"
        "filter:\n  allowed: false\n"
        "group_by: requested_by\n"
        "threshold_count: 2\n"
        "window_seconds: 300\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.jsonl"
    now = datetime.now(timezone.utc)
    lines = [
        json.dumps({"timestamp": now.isoformat(), "allowed": False, "requested_by": "agent"}),
        json.dumps({"timestamp": now.isoformat(), "allowed": False, "requested_by": "agent"}),
    ]
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    alerts_out = tmp_path / "alerts.jsonl"

    result = runner.invoke(
        app,
        [
            "defense-correlate",
            "--rules-dir",
            str(rules_dir),
            "--tool-audit",
            str(audit),
            "--alerts-out",
            str(alerts_out),
        ],
    )

    assert result.exit_code == 1, result.output
    assert alerts_out.exists()
    assert len(alerts_out.read_text(encoding="utf-8").strip().splitlines()) == 1
