"""Tests del motor de correlación tipo Sigma (defense_env/correlation.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scraper_agent.defense_env.correlation import evaluate_rule, load_events, load_rules, run_correlation
from scraper_agent.defense_env.models import CorrelationRule

BASE_TIME = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


def _event(offset_seconds: int, **fields) -> dict:
    return {
        "timestamp": (BASE_TIME + timedelta(seconds=offset_seconds)).isoformat(),
        **fields,
    }


class TestEvaluateRuleThresholdOne:
    def test_single_matching_event_produces_one_alert(self) -> None:
        rule = CorrelationRule(
            id="test.high_risk",
            title="Categoría de alto riesgo",
            severity="medium",
            logsource="tool_audit",
            filter={"allowed": True, "category": ["bounded_fuzzing", "active_scanning"]},
            threshold_count=1,
        )
        events = [
            _event(0, allowed=True, category="bounded_fuzzing", requested_by="agent"),
            _event(10, allowed=True, category="passive_recon", requested_by="agent"),
        ]

        alerts = evaluate_rule(rule, events)

        assert len(alerts) == 1
        assert alerts[0].rule_id == "test.high_risk"
        assert alerts[0].severity == "medium"

    def test_no_matching_events_produces_no_alerts(self) -> None:
        rule = CorrelationRule(
            id="test.high_risk",
            title="x",
            severity="medium",
            logsource="tool_audit",
            filter={"allowed": True, "category": ["bounded_fuzzing"]},
        )
        events = [_event(0, allowed=True, category="passive_recon")]

        assert evaluate_rule(rule, events) == []

    def test_multiple_matching_events_produce_one_alert_each(self) -> None:
        rule = CorrelationRule(
            id="test.high_risk",
            title="x",
            severity="medium",
            logsource="tool_audit",
            filter={"allowed": True, "category": ["bounded_fuzzing"]},
        )
        events = [
            _event(0, allowed=True, category="bounded_fuzzing"),
            _event(5, allowed=True, category="bounded_fuzzing"),
        ]

        alerts = evaluate_rule(rule, events)

        assert len(alerts) == 2


class TestEvaluateRuleFrequency:
    def test_burst_within_window_triggers_alert(self) -> None:
        rule = CorrelationRule(
            id="test.repeated_denied",
            title="x",
            severity="high",
            logsource="tool_audit",
            filter={"allowed": False},
            group_by="requested_by",
            threshold_count=3,
            window_seconds=300,
        )
        events = [
            _event(0, allowed=False, requested_by="agent"),
            _event(60, allowed=False, requested_by="agent"),
            _event(120, allowed=False, requested_by="agent"),
        ]

        alerts = evaluate_rule(rule, events)

        assert len(alerts) == 1
        assert alerts[0].severity == "high"

    def test_events_below_threshold_do_not_trigger(self) -> None:
        rule = CorrelationRule(
            id="test.repeated_denied",
            title="x",
            severity="high",
            logsource="tool_audit",
            filter={"allowed": False},
            group_by="requested_by",
            threshold_count=3,
            window_seconds=300,
        )
        events = [
            _event(0, allowed=False, requested_by="agent"),
            _event(60, allowed=False, requested_by="agent"),
        ]

        assert evaluate_rule(rule, events) == []

    def test_events_spread_outside_window_do_not_trigger(self) -> None:
        rule = CorrelationRule(
            id="test.repeated_denied",
            title="x",
            severity="high",
            logsource="tool_audit",
            filter={"allowed": False},
            group_by="requested_by",
            threshold_count=3,
            window_seconds=300,
        )
        events = [
            _event(0, allowed=False, requested_by="agent"),
            _event(400, allowed=False, requested_by="agent"),
            _event(800, allowed=False, requested_by="agent"),
        ]

        assert evaluate_rule(rule, events) == []

    def test_groups_are_evaluated_independently(self) -> None:
        rule = CorrelationRule(
            id="test.repeated_denied",
            title="x",
            severity="high",
            logsource="tool_audit",
            filter={"allowed": False},
            group_by="requested_by",
            threshold_count=3,
            window_seconds=300,
        )
        events = [
            _event(0, allowed=False, requested_by="agent-a"),
            _event(60, allowed=False, requested_by="agent-b"),
            _event(120, allowed=False, requested_by="agent-a"),
            _event(180, allowed=False, requested_by="agent-b"),
        ]

        # ninguno de los dos grupos llega a 3 -> sin alertas
        assert evaluate_rule(rule, events) == []


class TestLoadEventsAndRules:
    def test_load_events_reads_jsonl(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        path.write_text(
            json.dumps(_event(0, allowed=True)) + "\n" + json.dumps(_event(1, allowed=False)) + "\n",
            encoding="utf-8",
        )

        events = load_events(path)

        assert len(events) == 2
        assert events[0]["allowed"] is True

    def test_load_events_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        assert load_events(tmp_path / "no_existe.jsonl") == []

    def test_load_rules_reads_all_yaml_in_dir(self, tmp_path: Path) -> None:
        (tmp_path / "rule_a.yaml").write_text(
            "id: a\ntitle: A\nseverity: low\nlogsource: tool_audit\nfilter: {}\n",
            encoding="utf-8",
        )
        (tmp_path / "rule_b.yaml").write_text(
            "id: b\ntitle: B\nseverity: high\nlogsource: tool_audit\nfilter: {}\n",
            encoding="utf-8",
        )

        rules = load_rules(tmp_path)

        assert {r.id for r in rules} == {"a", "b"}


class TestRunCorrelation:
    def test_runs_multiple_rules_against_their_logsource(self) -> None:
        rule_a = CorrelationRule(
            id="a", title="A", severity="medium", logsource="tool_audit", filter={"allowed": True}
        )
        rule_b = CorrelationRule(
            id="b", title="B", severity="high", logsource="other_source", filter={"x": 1}
        )
        events_by_source = {
            "tool_audit": [_event(0, allowed=True)],
            "other_source": [_event(0, x=1), _event(1, x=1)],
        }

        alerts = run_correlation([rule_a, rule_b], events_by_source)

        rule_ids = [a.rule_id for a in alerts]
        assert rule_ids.count("a") == 1
        assert rule_ids.count("b") == 2

    def test_rule_with_no_matching_logsource_produces_nothing(self) -> None:
        rule = CorrelationRule(
            id="a", title="A", severity="medium", logsource="missing_source", filter={}
        )

        alerts = run_correlation([rule], {})

        assert alerts == []
