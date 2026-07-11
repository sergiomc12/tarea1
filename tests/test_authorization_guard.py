"""Tests de authorization_guard — rechazo antes de ejecutar herramientas."""

from datetime import date
from pathlib import Path

import pytest

from scraper_agent.security_env.authorization_guard import (
    AuthorizationGuard,
    load_authorized_targets,
)
from scraper_agent.security_env.exceptions import AuthorizationDenied

FIXTURE = Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"


@pytest.fixture
def guard() -> AuthorizationGuard:
    return AuthorizationGuard(load_authorized_targets(FIXTURE))


def test_load_authorized_targets_fixture(guard: AuthorizationGuard) -> None:
    assert len(guard.entries) == 7


def test_authorize_extended_categories_on_full_target(guard: AuthorizationGuard) -> None:
    for category in (
        "active_scanning",
        "known_vuln_scanning",
        "bounded_fuzzing",
    ):
        result = guard.authorize("app.full.example.com", category, on=date(2026, 7, 6))
        assert result.allowed is True, category


def test_authorize_dns_enumeration_on_full_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("app.full.example.com", "dns_enumeration", on=date(2026, 7, 6))
    assert result.allowed is True


def test_reject_dns_enumeration_on_basic_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("app.allowed.example.com", "dns_enumeration", on=date(2026, 7, 6))
    assert result.allowed is False
    assert "categor" in result.reason.lower()


def test_reject_extended_categories_on_basic_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("app.allowed.example.com", "active_scanning", on=date(2026, 7, 6))
    assert result.allowed is False
    assert "categor" in result.reason.lower()


def test_authorize_subdomain_via_scope(guard: AuthorizationGuard) -> None:
    result = guard.authorize("app.allowed.example.com", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is True


def test_authorize_exact_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("allowed.example.com", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is True


def test_reject_unknown_host(guard: AuthorizationGuard) -> None:
    result = guard.authorize("evil.example.com", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is False
    assert "no autorizado" in result.reason.lower()


def test_reject_expired_authorization(guard: AuthorizationGuard) -> None:
    result = guard.authorize("expired.example.com", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is False
    assert "expir" in result.reason.lower()


def test_reject_category_not_allowed(guard: AuthorizationGuard) -> None:
    result = guard.authorize("limited.example.com", "light_active_scan", on=date(2026, 7, 6))
    assert result.allowed is False
    assert "categor" in result.reason.lower()


def test_authorize_ip_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("203.0.113.50", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is True


def test_require_raises_on_denied(guard: AuthorizationGuard) -> None:
    with pytest.raises(AuthorizationDenied):
        guard.require("evil.example.com", "passive_recon", on=date(2026, 7, 6))


def test_normalize_strips_port(guard: AuthorizationGuard) -> None:
    result = guard.authorize("app.allowed.example.com:443", "passive_recon", on=date(2026, 7, 6))
    assert result.allowed is True


class TestLockdown:
    """Fase 3 (respuesta activa, defense_env/active_response.py): un lockdown
    activo deniega TODO, sin importar si el target/categoría normalmente
    estarían autorizados -- fail-closed real, no solo un log más."""

    def test_authorize_denies_everything_when_lockdown_active(self, tmp_path: Path) -> None:
        from scraper_agent.defense_env.active_response import trigger_lockdown

        flag_path = tmp_path / "LOCKDOWN.json"
        trigger_lockdown("alerta critica de FIM", flag_path)
        locked_guard = AuthorizationGuard(load_authorized_targets(FIXTURE), lockdown_path=flag_path)

        result = locked_guard.authorize("app.allowed.example.com", "passive_recon", on=date(2026, 7, 6))

        assert result.allowed is False
        assert "lockdown" in result.reason.lower()

    def test_authorize_normal_when_lockdown_path_given_but_no_flag(self, tmp_path: Path) -> None:
        locked_guard = AuthorizationGuard(
            load_authorized_targets(FIXTURE), lockdown_path=tmp_path / "LOCKDOWN.json"
        )

        result = locked_guard.authorize("app.allowed.example.com", "passive_recon", on=date(2026, 7, 6))

        assert result.allowed is True

    def test_authorize_normal_when_no_lockdown_path_configured(self, guard: AuthorizationGuard) -> None:
        result = guard.authorize("app.allowed.example.com", "passive_recon", on=date(2026, 7, 6))

        assert result.allowed is True
