"""File Integrity Monitoring: baseline de hashes + detección de drift.

Diseño alineado a NIST SP 800-94 (categoría host-based IDPS: vigilar el
estado de un host/proyecto propio, no tráfico de red). No sustituye un FIM
de producción (auditd, Wazuh syscheck) — es la Fase 1 de `defense_env/`,
ver CHANGELOG.md.
"""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path

from scraper_agent.defense_env.models import Alert, DriftType, FimBaselineEntry, FimWatchConfig

CRITICAL_FILE_MITRE_TECHNIQUE = "T1565"  # Data Manipulation

# Extensión OPCIONAL de C++ (pybind11) -- ver CHANGELOG.md "candidatos a
# migración C/C++ + pybind11". Nunca un requisito duro: si no está
# compilada/disponible (Windows sin toolchain de C++, o un servidor sin
# build-essential/libssl-dev), el hashing sigue funcionando con
# hashlib puro más abajo -- ningún caller necesita saber cuál se usó.
#
# `_fim_native/` no tiene `__init__.py` (es solo la fuente .cpp + el .so
# compilado que deja setup.py ahí) -- Python 3 la trata como "namespace
# package" (PEP 420) e importa el directorio SIN ERROR aunque no haya
# ningún .so compilado adentro. El try/except solo no alcanza: hace falta
# `hasattr(..., "hash_files")` para confirmar que es de verdad la extensión
# compilada, no un directorio vacío. Bug real, encontrado corriendo los
# tests de FIM en este mismo entorno Windows tras agregar la extensión.
try:
    from scraper_agent.defense_env import _fim_native

    NATIVE_HASHING_AVAILABLE = hasattr(_fim_native, "hash_files")
except ImportError:
    _fim_native = None
    NATIVE_HASHING_AVAILABLE = False


def _is_excluded(path: Path, exclude_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in exclude_patterns)


def _iter_watched_files(config: FimWatchConfig):
    for root in config.paths:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = [p for p in root.rglob("*") if p.is_file()]
        else:
            continue
        for candidate in candidates:
            if not _is_excluded(candidate, config.exclude_patterns):
                yield candidate


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_native(files: list[Path]) -> dict[str, FimBaselineEntry]:
    """Hashea `files` con la extensión C++ (`_fim_native.hash_files`) --
    una sola llamada nativa para todo el lote, en vez de un loop Python con
    un objeto Pydantic construido por archivo. Devuelve el mismo formato
    que `_snapshot()` (claves posix)."""
    native_results = _fim_native.hash_files([str(p) for p in files])
    snapshot: dict[str, FimBaselineEntry] = {}
    for path in files:
        key = path.as_posix()
        data = native_results.get(str(path))
        if data is None:
            continue
        snapshot[key] = FimBaselineEntry(
            path=key, sha256=data["sha256"], size_bytes=data["size_bytes"], mtime=data["mtime"]
        )
    return snapshot


def _snapshot_python(files: list[Path]) -> dict[str, FimBaselineEntry]:
    """Fallback puro Python (hashlib) -- usado si la extensión nativa no
    está compilada/disponible."""
    snapshot: dict[str, FimBaselineEntry] = {}
    for path in files:
        stat = path.stat()
        key = path.as_posix()
        snapshot[key] = FimBaselineEntry(
            path=key,
            sha256=_hash_file(path),
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
        )
    return snapshot


def _snapshot(config: FimWatchConfig) -> dict[str, FimBaselineEntry]:
    """Claves SIEMPRE en formato posix (`/`), nunca `str(path)` -- un
    baseline generado en Windows (`fim-baseline` corrido a mano en el host)
    y escaneado en Linux (`fim_watcher` en Docker) tenía claves distintas
    para el MISMO archivo (`\\` vs `/`), así que cada archivo aparecía como
    "borrado" y "agregado" a la vez. Bug real, visto en los primeros logs
    del sidecar `fim_watcher`. Ver CHANGELOG.md.

    Usa la extensión nativa de C++ si está disponible (`NATIVE_HASHING_AVAILABLE`),
    si no cae a hashlib puro -- mismo resultado en ambos casos."""
    files = list(_iter_watched_files(config))
    if NATIVE_HASHING_AVAILABLE and files:
        return _snapshot_native(files)
    return _snapshot_python(files)


def compute_baseline(config: FimWatchConfig) -> dict[str, FimBaselineEntry]:
    """Hashea todos los archivos vigilados y devuelve el estado conocido-bueno."""
    return _snapshot(config)


def missing_watched_paths(config: FimWatchConfig) -> list[str]:
    """Rutas de `config.paths` que no existen (ni archivo ni directorio) --
    `_iter_watched_files` las saltea en silencio, lo cual es exactamente el
    bug real que dejó a `fim_watcher` vigilando 3 de 5 archivos declarados
    sin ningún aviso (docker-compose.yml/docker/ no montados en el
    contenedor). El caller (CLI) debe mostrar esto como advertencia. Ver
    CHANGELOG.md."""
    return [p.as_posix() for p in config.paths if not p.exists()]


def _severity_for(path_str: str, config: FimWatchConfig) -> str:
    basename = Path(path_str).name
    return "critical" if basename in config.critical_files else "high"


def scan_for_drift(baseline: dict[str, FimBaselineEntry], config: FimWatchConfig) -> list[Alert]:
    """Compara el estado actual contra `baseline` y emite una `Alert` por cada
    archivo agregado, modificado o borrado. No muta `baseline`."""
    current = _snapshot(config)
    alerts: list[Alert] = []

    for path_str, entry in current.items():
        if path_str not in baseline:
            alerts.append(
                Alert(
                    rule_id="fim.file_added",
                    severity="medium",
                    drift_type=DriftType.ADDED,
                    description=f"Archivo nuevo no presente en el baseline: {path_str}",
                )
            )
        elif entry.sha256 != baseline[path_str].sha256:
            severity = _severity_for(path_str, config)
            alerts.append(
                Alert(
                    rule_id="fim.file_modified",
                    severity=severity,
                    drift_type=DriftType.MODIFIED,
                    description=f"Contenido modificado respecto al baseline: {path_str}",
                    mitre_technique=CRITICAL_FILE_MITRE_TECHNIQUE if severity == "critical" else None,
                    evidence={"baseline_sha256": baseline[path_str].sha256, "current_sha256": entry.sha256},
                )
            )

    for path_str in baseline:
        if path_str not in current:
            severity = _severity_for(path_str, config)
            alerts.append(
                Alert(
                    rule_id="fim.file_deleted",
                    severity=severity,
                    drift_type=DriftType.DELETED,
                    description=f"Archivo vigilado ya no existe: {path_str}",
                    mitre_technique=CRITICAL_FILE_MITRE_TECHNIQUE if severity == "critical" else None,
                )
            )

    return alerts
