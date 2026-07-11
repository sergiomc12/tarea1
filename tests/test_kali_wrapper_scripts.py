"""Regresión: los wrappers de docker/kali/bin/ deben tener line endings LF.

Bug real encontrado en una corrida completa contra krapcom.net: en Windows
con `core.autocrlf=true`, git convierte estos scripts a CRLF al hacer
checkout. El shebang `#!/bin/sh\\r` no resuelve — el runtime busca un
intérprete llamado literalmente `/bin/sh\\r`, que no existe — y `docker exec`
falla con "no such file or directory" aunque el archivo sí exista. Afectó a
`wpscan_enum_safe` en producción. `.gitattributes` fuerza LF para
`docker/kali/bin/*`, pero este test detecta una regresión aunque alguien
borre o ignore ese archivo.
"""

from __future__ import annotations

from pathlib import Path

BIN_DIR = Path(__file__).resolve().parents[1] / "docker" / "kali" / "bin"


def _wrapper_scripts() -> list[Path]:
    assert BIN_DIR.is_dir(), f"no existe {BIN_DIR}"
    scripts = sorted(BIN_DIR.iterdir())
    assert scripts, f"{BIN_DIR} no tiene wrappers"
    return scripts


def test_wrapper_scripts_use_lf_line_endings() -> None:
    for script in _wrapper_scripts():
        raw = script.read_bytes()
        assert b"\r\n" not in raw, (
            f"{script.name} tiene CRLF — rompe el shebang dentro del "
            "contenedor Linux (ver docstring del test)"
        )


def test_wrapper_scripts_have_valid_shebang() -> None:
    for script in _wrapper_scripts():
        first_line = script.read_bytes().split(b"\n", 1)[0]
        assert first_line.startswith(b"#!/"), f"{script.name}: shebang ausente o inválido"
