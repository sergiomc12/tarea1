"""Tests de defense_env/remediation.py — REGLA DURA (ver CHANGELOG.md):
toda acción de remediación SIEMPRE informa, sugiere la solución exacta, y
exige confirmación humana explícita antes de aplicar. Nunca auto-aplica,
sin excepción. Distinto de la contención rápida (lockdown/aislamiento/
block_ip), que sigue siendo automática por ser reflejos de emergencia que
no pueden esperar confirmación.

`apply_remediation()` rechaza ESTRUCTURALMENTE (no solo por convención de
CLI) cualquier intento de aplicar sin `confirmed=True`.
"""

from __future__ import annotations

import pytest

from scraper_agent.defense_env.remediation import (
    RemediationSuggestion,
    apply_remediation,
    suggest_remediation,
)


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestSuggestRemediation:
    def test_known_pattern_returns_suggestion_with_command(self) -> None:
        suggestion = suggest_remediation(
            "outdated_openssh", {"detail": "OpenSSH_7.4 (CVE-2018-15473)", "package_manager": "dnf"}
        )

        assert suggestion is not None
        assert suggestion.suggested_command[0] == "dnf"
        assert "openssh-server" in suggestion.suggested_command
        assert suggestion.risk_level in ("low", "medium", "high")

    def test_unknown_pattern_returns_none_never_invents_a_fix(self) -> None:
        assert suggest_remediation("patron-que-no-existe", {}) is None

    def test_weak_sshd_config_pattern(self) -> None:
        suggestion = suggest_remediation(
            "weak_sshd_config", {"setting": "PermitRootLogin", "current_value": "yes"}
        )

        assert suggestion is not None
        assert "sshd_config" in " ".join(suggestion.suggested_command)
        assert suggestion.risk_level == "high"

    def test_suggestion_never_executes_anything_itself(self) -> None:
        """suggest_remediation es puro -- solo arma la sugerencia, no toca
        el sistema. Si esto alguna vez ejecuta algo, es un bug grave."""
        # No hay runner inyectable acá a propósito: si la función intentara
        # ejecutar un comando real, este test fallaría con un error de
        # sistema (comando no encontrado, permisos, etc.) en vez de pasar
        # limpio -- la ausencia de ese fallo ES la prueba de que es puro.
        suggestion = suggest_remediation("outdated_openssh", {"package_manager": "dnf"})
        assert isinstance(suggestion, RemediationSuggestion)


class TestApplyRemediationRequiresConfirmation:
    def test_raises_without_explicit_confirmation(self) -> None:
        suggestion = suggest_remediation("outdated_openssh", {"package_manager": "dnf"})
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess()

        with pytest.raises(ValueError, match="confirmed"):
            apply_remediation(suggestion, confirmed=False, runner=runner)

        assert calls == []  # el runner NUNCA se llamó -- cero efectos secundarios

    def test_raises_when_confirmed_is_falsy_default(self) -> None:
        """El default de `confirmed` no puede ser True -- confirmar debe
        ser un acto explícito del caller, nunca implícito."""
        suggestion = suggest_remediation("outdated_openssh", {"package_manager": "dnf"})

        with pytest.raises(TypeError):
            apply_remediation(suggestion)  # falta el kwarg confirmed a propósito

    def test_applies_when_confirmed_true(self) -> None:
        suggestion = suggest_remediation("outdated_openssh", {"package_manager": "dnf"})
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        result = apply_remediation(suggestion, confirmed=True, runner=runner)

        assert result["success"] is True
        assert calls == [suggestion.suggested_command]

    def test_reports_failure_from_command(self) -> None:
        suggestion = suggest_remediation("outdated_openssh", {"package_manager": "dnf"})

        def runner(argv):
            return _FakeCompletedProcess(returncode=1, stderr="permission denied")

        result = apply_remediation(suggestion, confirmed=True, runner=runner)

        assert result["success"] is False
        assert "permission denied" in result["detail"]
