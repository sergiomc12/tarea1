"""Selectores CSS configurables por sitio."""

from bs4 import BeautifulSoup


def extract_with_selectors(soup: BeautifulSoup, selectors: dict[str, str]) -> dict[str, str | list[str]]:
    """Extrae datos según mapa selector -> clave."""
    data: dict[str, str | list[str]] = {}
    for key, css in selectors.items():
        if not css:
            continue
        elements = soup.select(css)
        if not elements:
            continue
        if len(elements) == 1:
            data[key] = elements[0].get_text(" ", strip=True)
        else:
            data[key] = [el.get_text(" ", strip=True) for el in elements]
    return data
