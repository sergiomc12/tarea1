"""Validación de hosts y construcción segura de argv."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from scraper_agent.security_env.exceptions import InvalidToolParams
from scraper_agent.security_env.models import ToolCatalogEntry, ToolParamSpec

_HOSTNAME_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
)
_FORBIDDEN_SHELL_CHARS = re.compile(r"[`$;&|<>\\'\n\r]")


def normalize_host(value: str) -> str:
    """Normaliza dominio/IP: quita esquema, path y puerto."""
    raw = value.strip().lower()
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or raw
    if raw.startswith("[") and "]" in raw:
        raw = raw[1 : raw.index("]")]
    if ":" in raw and not _looks_like_ipv6(raw):
        host, _, port = raw.rpartition(":")
        if port.isdigit():
            raw = host
    return raw.strip(".")


def _looks_like_ipv6(value: str) -> bool:
    return value.count(":") >= 2


def validate_hostname(value: str) -> str:
    """Valida dominio o IP; rechaza metacaracteres de shell."""
    host = normalize_host(value)
    if not host or _FORBIDDEN_SHELL_CHARS.search(host):
        raise InvalidToolParams(f"host invalido: {value!r}")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if _HOSTNAME_RE.match(host):
        return host
    raise InvalidToolParams(f"host invalido: {value!r}")


def validate_port(value: int | str) -> int:
    port = int(value)
    if port < 1 or port > 65535:
        raise InvalidToolParams(f"puerto fuera de rango: {port}")
    return port


def validate_cidr(value: str) -> str:
    """Valida notación CIDR; rechaza metacaracteres de shell."""
    raw = value.strip()
    if not raw or _FORBIDDEN_SHELL_CHARS.search(raw):
        raise InvalidToolParams(f"cidr invalido: {value!r}")
    try:
        network = ipaddress.ip_network(raw, strict=False)
    except ValueError as exc:
        raise InvalidToolParams(f"cidr invalido: {value!r}") from exc
    return str(network)


def validate_param(spec: ToolParamSpec, raw_value: str | int | None) -> str | int:
    if raw_value is None:
        if spec.required:
            raise InvalidToolParams(f"parametro requerido ausente: {spec.name}")
        raise InvalidToolParams(f"parametro requerido ausente: {spec.name}")
    if spec.type == "hostname":
        return validate_hostname(str(raw_value))
    if spec.type == "port":
        return validate_port(raw_value)
    if spec.type == "cidr":
        return validate_cidr(str(raw_value))
    raise InvalidToolParams(f"tipo de parametro desconocido: {spec.type}")


def validate_tool_params(
    entry: ToolCatalogEntry,
    params: dict[str, str | int],
    *,
    host: str,
) -> dict[str, str | int]:
    """Valida params contra el catálogo; inyecta host si está declarado."""
    merged = dict(params)
    if any(p.name == "host" for p in entry.params):
        merged.setdefault("host", host)
    validated: dict[str, str | int] = {}
    spec_by_name = {p.name: p for p in entry.params}
    for name, spec in spec_by_name.items():
        validated[name] = validate_param(spec, merged.get(name))
    extra = set(merged) - set(spec_by_name)
    if extra:
        raise InvalidToolParams(f"parametros no permitidos: {sorted(extra)}")
    return validated


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _render_argv_token(token: str, validated_params: dict[str, str | int]) -> str:
    """Sustituye placeholders `{name}` dentro de un token argv."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in validated_params:
            raise InvalidToolParams(f"placeholder sin valor: {key}")
        return str(validated_params[key])

    rendered = _PLACEHOLDER_RE.sub(repl, token)
    if _PLACEHOLDER_RE.search(rendered):
        raise InvalidToolParams(f"placeholder sin valor en token: {token!r}")
    return rendered


def build_argv(entry: ToolCatalogEntry, validated_params: dict[str, str | int]) -> list[str]:
    """Construye argv solo desde plantilla y valores validados."""
    argv: list[str] = []
    for token in entry.argv_template:
        if token.startswith("{") and token.endswith("}") and "{" not in token[1:-1]:
            key = token[1:-1]
            if key not in validated_params:
                raise InvalidToolParams(f"placeholder sin valor: {key}")
            argv.append(str(validated_params[key]))
        else:
            argv.append(_render_argv_token(token, validated_params))
    if argv and argv[0] != entry.binary:
        raise InvalidToolParams("argv_template debe comenzar con binary declarado")
    return argv
