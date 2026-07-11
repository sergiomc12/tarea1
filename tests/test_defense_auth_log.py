"""Tests del parser de logs de autenticación SSH
(defense_env/auth_log_parser.py) — RHEL/CentOS: /var/log/secure;
Debian/Ubuntu: /var/log/auth.log. Convierte líneas de syslog de sshd en
eventos que el motor de correlación EXISTENTE (correlation.py) ya sabe
procesar — no se reimplementa detección de umbral/ventana.
"""

from __future__ import annotations

from pathlib import Path

from scraper_agent.defense_env.auth_log_parser import parse_ssh_auth_line, parse_ssh_auth_log

FAILED_INVALID_USER = "Jul  9 21:45:01 myhost sshd[12345]: Failed password for invalid user admin from 203.0.113.7 port 54321 ssh2"
FAILED_REAL_USER = "Jul  9 21:45:03 myhost sshd[12345]: Failed password for root from 203.0.113.7 port 54322 ssh2"
ACCEPTED = "Jul  9 21:45:10 myhost sshd[12346]: Accepted password for validuser from 198.51.100.5 port 22334 ssh2"
UNRELATED_LINE = "Jul  9 21:45:15 myhost systemd[1]: Started Session 42 of user validuser."


class TestParseSshAuthLine:
    def test_parses_failed_invalid_user(self) -> None:
        event = parse_ssh_auth_line(FAILED_INVALID_USER, year=2026)

        assert event is not None
        assert event["allowed"] is False
        assert event["user"] == "admin"
        assert event["source_ip"] == "203.0.113.7"
        assert event["port"] == 54321
        assert event["timestamp"].startswith("2026-07-09")

    def test_parses_failed_real_user(self) -> None:
        event = parse_ssh_auth_line(FAILED_REAL_USER, year=2026)

        assert event is not None
        assert event["allowed"] is False
        assert event["user"] == "root"

    def test_parses_accepted_login(self) -> None:
        event = parse_ssh_auth_line(ACCEPTED, year=2026)

        assert event is not None
        assert event["allowed"] is True
        assert event["source_ip"] == "198.51.100.5"

    def test_unrelated_line_returns_none(self) -> None:
        assert parse_ssh_auth_line(UNRELATED_LINE, year=2026) is None

    def test_empty_line_returns_none(self) -> None:
        assert parse_ssh_auth_line("", year=2026) is None

    def test_defaults_to_current_year_when_not_specified(self) -> None:
        import datetime

        event = parse_ssh_auth_line(FAILED_INVALID_USER)

        assert event is not None
        assert event["timestamp"].startswith(str(datetime.datetime.now(datetime.timezone.utc).year))


class TestParseSshAuthLog:
    def test_parses_all_matching_lines_in_file(self, tmp_path: Path) -> None:
        log_path = tmp_path / "secure"
        log_path.write_text(
            "\n".join([FAILED_INVALID_USER, FAILED_REAL_USER, ACCEPTED, UNRELATED_LINE]) + "\n",
            encoding="utf-8",
        )

        events = parse_ssh_auth_log(log_path, year=2026)

        assert len(events) == 3
        assert sum(1 for e in events if not e["allowed"]) == 2

    def test_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        assert parse_ssh_auth_log(tmp_path / "no_existe", year=2026) == []
