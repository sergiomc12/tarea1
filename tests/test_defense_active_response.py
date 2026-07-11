"""Tests de la respuesta activa (Fase 3, defense_env/active_response.py).

MVP deliberadamente conservador: la única acción automática es un
"circuit breaker" fail-closed (bloquear TODA ejecución ofensiva hasta que
un humano lo limpie) — nunca una acción destructiva ni una modificación
automática de `authorized_targets.yaml`. Ver CHANGELOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from scraper_agent.defense_env.active_response import (
    clear_lockdown,
    is_locked_down,
    read_lockdown_reason,
    trigger_lockdown,
)


def test_is_locked_down_false_when_no_file(tmp_path: Path) -> None:
    assert is_locked_down(tmp_path / "LOCKDOWN.json") is False


def test_trigger_lockdown_creates_flag_file(tmp_path: Path) -> None:
    flag_path = tmp_path / "security" / "LOCKDOWN.json"

    trigger_lockdown("alerta critica: authorized_targets.yaml modificado", flag_path)

    assert flag_path.exists()
    data = json.loads(flag_path.read_text(encoding="utf-8"))
    assert data["reason"] == "alerta critica: authorized_targets.yaml modificado"
    assert "triggered_at" in data


def test_is_locked_down_true_after_trigger(tmp_path: Path) -> None:
    flag_path = tmp_path / "LOCKDOWN.json"
    trigger_lockdown("motivo x", flag_path)

    assert is_locked_down(flag_path) is True


def test_read_lockdown_reason_returns_reason(tmp_path: Path) -> None:
    flag_path = tmp_path / "LOCKDOWN.json"
    trigger_lockdown("motivo x", flag_path)

    assert read_lockdown_reason(flag_path) == "motivo x"


def test_read_lockdown_reason_none_when_not_locked(tmp_path: Path) -> None:
    assert read_lockdown_reason(tmp_path / "LOCKDOWN.json") is None


def test_clear_lockdown_removes_file(tmp_path: Path) -> None:
    flag_path = tmp_path / "LOCKDOWN.json"
    trigger_lockdown("motivo x", flag_path)

    clear_lockdown(flag_path)

    assert is_locked_down(flag_path) is False


def test_clear_lockdown_on_missing_file_is_noop(tmp_path: Path) -> None:
    clear_lockdown(tmp_path / "no_existe.json")  # no debe lanzar


def test_trigger_lockdown_does_not_overwrite_earlier_reason(tmp_path: Path) -> None:
    """Si ya hay un lockdown activo, un segundo trigger no debe pisar el
    motivo original -- el humano necesita saber la PRIMERA causa, no la
    última alerta que llegó mientras investigaba."""
    flag_path = tmp_path / "LOCKDOWN.json"
    trigger_lockdown("motivo original", flag_path)

    trigger_lockdown("motivo nuevo", flag_path)

    assert read_lockdown_reason(flag_path) == "motivo original"
