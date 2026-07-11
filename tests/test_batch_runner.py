"""Tests del crawl por lotes de medios."""

from pathlib import Path

from scraper_agent.crawler.batch_runner import load_sites_manifest


def test_load_sites_manifest_includes_all_media():
    root = Path(__file__).resolve().parents[1]
    manifest = root / "config" / "sites" / "sites.yaml"
    sites = load_sites_manifest(manifest)
    names = {s.name for s in sites}
    expected = {
        "gestion.pe",
        "elcomercio.pe",
        "larepublica.pe",
        "ojo.pe",
        "trome.com",
        "elchino.pe",
        "peru21.pe",
        "expreso.com.pe",
        "libero.pe",
        "elperuano.pe",
    }
    assert expected == names
    assert all(s.config_path.exists() for s in sites)
