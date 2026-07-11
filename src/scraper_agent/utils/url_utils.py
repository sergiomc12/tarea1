"""Utilidades para normalización y comparación de URLs."""

from urllib.parse import urldefrag, urljoin, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normaliza URL: sin fragmento, sin trailing slash redundante en path vacío."""
    url, _ = urldefrag(url.strip())
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, parsed.params, parsed.query, ""))


def is_same_registrable_domain(url: str, root_domain: str, include_subdomains: bool = True) -> bool:
    """Comprueba si la URL pertenece al dominio raíz (opcionalmente subdominios)."""
    host = urlparse(url).netloc.lower()
    root = root_domain.lower().lstrip(".")
    if host == root:
        return True
    if include_subdomains and host.endswith(f".{root}"):
        return True
    return False


def resolve_url(base: str, href: str) -> str | None:
    """Resuelve href relativo contra base; descarta mailto/tel/javascript."""
    if not href or not href.strip():
        return None
    href = href.strip()
    lower = href.lower()
    if lower.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    return normalize_url(urljoin(base, href))


def registrable_domain(url: str) -> str:
    """Extrae el host de una URL."""
    return urlparse(url).netloc.lower()


def path_depth(url: str, root_url: str) -> int:
    """Profundidad relativa de path respecto a la raíz."""
    root_path = urlparse(root_url).path.rstrip("/") or "/"
    path = urlparse(url).path.rstrip("/") or "/"
    if path == root_path:
        return 0
    rel = path[len(root_path) :].strip("/") if path.startswith(root_path) else path.strip("/")
    if not rel:
        return 0
    return len([p for p in rel.split("/") if p])
