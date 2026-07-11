"""Tests de aislamiento de red del contenedor comprometido
(defense_env/container_isolation.py).

Distinto del lockdown de active_response.py: el lockdown detiene la
ejecución ofensiva DE `tarea1` mismo (útil si `tarea1` fue comprometido y
usado de arma). Esto aísla a un atacante EXTERNO desconectando el
contenedor afectado de la red docker -- corrección señalada por el usuario:
el lockdown no le hacía nada a un atacante externo. Ver CHANGELOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from scraper_agent.defense_env.container_isolation import (
    is_isolated,
    isolate_container,
    reconnect_container,
)


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def _fake_runner(calls: list[list[str]], *, returncode: int = 0, stderr: str = ""):
    def _runner(argv: list[str]):
        calls.append(argv)
        return _FakeCompletedProcess(returncode=returncode, stderr=stderr)

    return _runner


class TestIsolateContainer:
    def test_calls_docker_network_disconnect(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        state_path = tmp_path / "isolation.json"

        isolate_container(
            "kali-tools",
            network="scraper_internal",
            reason="patron de ransomware detectado",
            state_path=state_path,
            runner=_fake_runner(calls),
        )

        assert calls == [["docker", "network", "disconnect", "scraper_internal", "kali-tools"]]

    def test_persists_isolation_state(self, tmp_path: Path) -> None:
        state_path = tmp_path / "isolation.json"

        record = isolate_container(
            "kali-tools",
            network="scraper_internal",
            reason="patron de ransomware detectado",
            state_path=state_path,
            runner=_fake_runner([]),
        )

        assert state_path.exists()
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["container"] == "kali-tools"
        assert data["reason"] == "patron de ransomware detectado"
        assert record == data

    def test_idempotent_does_not_call_docker_twice(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        state_path = tmp_path / "isolation.json"
        runner = _fake_runner(calls)

        isolate_container("kali-tools", network="net", reason="motivo 1", state_path=state_path, runner=runner)
        isolate_container("kali-tools", network="net", reason="motivo 2 (nueva alerta)", state_path=state_path, runner=runner)

        assert len(calls) == 1
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["reason"] == "motivo 1"  # se conserva el motivo original

    def test_records_docker_failure_without_raising(self, tmp_path: Path) -> None:
        state_path = tmp_path / "isolation.json"
        runner = _fake_runner([], returncode=1, stderr="Error: No such container")

        record = isolate_container(
            "no-existe", network="net", reason="x", state_path=state_path, runner=runner
        )

        assert record["docker_exit_code"] == 1
        assert "No such container" in record["docker_stderr"]


class TestIsIsolated:
    def test_false_when_no_state_file(self, tmp_path: Path) -> None:
        assert is_isolated(tmp_path / "isolation.json") is False

    def test_true_after_isolate(self, tmp_path: Path) -> None:
        state_path = tmp_path / "isolation.json"
        isolate_container("x", network="net", reason="r", state_path=state_path, runner=_fake_runner([]))

        assert is_isolated(state_path) is True


class TestReconnectContainer:
    def test_calls_docker_network_connect(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        state_path = tmp_path / "isolation.json"
        isolate_container("kali-tools", network="net", reason="r", state_path=state_path, runner=_fake_runner([]))

        reconnect_container("kali-tools", network="net", state_path=state_path, runner=_fake_runner(calls))

        assert calls == [["docker", "network", "connect", "net", "kali-tools"]]

    def test_clears_isolation_state(self, tmp_path: Path) -> None:
        state_path = tmp_path / "isolation.json"
        isolate_container("kali-tools", network="net", reason="r", state_path=state_path, runner=_fake_runner([]))

        reconnect_container("kali-tools", network="net", state_path=state_path, runner=_fake_runner([]))

        assert is_isolated(state_path) is False

    def test_noop_when_not_isolated(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        state_path = tmp_path / "isolation.json"

        reconnect_container("kali-tools", network="net", state_path=state_path, runner=_fake_runner(calls))

        assert calls == []  # no llama a docker si no había nada que reconectar
