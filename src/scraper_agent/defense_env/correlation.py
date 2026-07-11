"""Motor de correlación tipo Sigma simplificado: reglas YAML con filtro de
campos + umbral de frecuencia opcional, evaluadas contra logs JSONL propios
(hoy: `output/security/tool_audit.jsonl`, ver `tool_runner.py`).

No es una reimplementación del formato Sigma completo (SigmaHQ/sigma) ni de
un motor de correlación de producción — es una Fase 2 real y honesta: filtro
de igualdad por campo + ventana deslizante de frecuencia, suficiente para
las reglas que tiene hoy `defense_env/rules/builtin/`. Ver CHANGELOG.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from scraper_agent.defense_env.models import Alert, CorrelationRule


def load_events(path: Path) -> list[dict]:
    """Lee eventos JSONL (una alerta/entrada por línea). `[]` si no existe."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def load_rules(rules_dir: Path) -> list[CorrelationRule]:
    """Carga todas las reglas `*.yaml` de `rules_dir`."""
    rules = []
    for yaml_path in sorted(rules_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        rules.append(CorrelationRule.model_validate(raw))
    return rules


def _event_matches(event: dict, filter_: dict[str, object]) -> bool:
    for field, expected in filter_.items():
        actual = event.get(field)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _build_alert(rule: CorrelationRule, sample_event: dict, *, group_key: str | None, count: int) -> Alert:
    group_note = f" (grupo: {group_key}, {count} evento(s) en la ventana)" if group_key is not None else ""
    return Alert(
        rule_id=rule.id,
        severity=rule.severity,
        description=f"{rule.title}{group_note}",
        mitre_technique=rule.mitre_technique,
        evidence={k: str(v) for k, v in sample_event.items()},
    )


def evaluate_rule(rule: CorrelationRule, events: list[dict]) -> list[Alert]:
    """Evalúa una regla contra una lista de eventos ya cargados.

    `threshold_count <= 1`: una alerta por cada evento que matchea el filtro
    (regla de visibilidad/auditoría, sin agrupar).

    `threshold_count > 1`: agrupa por `group_by` (o un único grupo global si
    es `None`) y busca una ráfaga de al menos `threshold_count` eventos
    dentro de una ventana deslizante de `window_seconds` — una alerta por
    grupo en la primera ráfaga que cruza el umbral (no una por evento, para
    no inundar de alertas ante un ataque sostenido)."""
    matching = [e for e in events if _event_matches(e, rule.filter)]
    if not matching:
        return []

    if rule.threshold_count <= 1:
        return [_build_alert(rule, event, group_key=None, count=1) for event in matching]

    groups: dict[str, list[dict]] = defaultdict(list)
    for event in matching:
        key = str(event.get(rule.group_by)) if rule.group_by else "_all_"
        groups[key].append(event)

    window = timedelta(seconds=rule.window_seconds)
    alerts: list[Alert] = []
    for key, group_events in groups.items():
        ordered = sorted(group_events, key=lambda e: _parse_timestamp(e["timestamp"]))
        timestamps = [_parse_timestamp(e["timestamp"]) for e in ordered]
        for i, current in enumerate(timestamps):
            count = sum(1 for t in timestamps if current - window <= t <= current)
            if count >= rule.threshold_count:
                alerts.append(_build_alert(rule, ordered[i], group_key=key, count=count))
                break  # un solo aviso por grupo evita inundar de alertas
    return alerts


def run_correlation(rules: list[CorrelationRule], events_by_logsource: dict[str, list[dict]]) -> list[Alert]:
    """Corre cada regla contra los eventos de su `logsource` correspondiente."""
    alerts: list[Alert] = []
    for rule in rules:
        events = events_by_logsource.get(rule.logsource, [])
        alerts.extend(evaluate_rule(rule, events))
    return alerts
