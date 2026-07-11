"""Tests de docker-compose.yml (estructura ítem 13)."""

from pathlib import Path

import yaml


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def test_compose_single_public_port() -> None:
    raw = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    scraper = raw["services"]["scraper_agent"]
    ports = scraper.get("ports", [])
    assert ports == ["1212:8000"]


def test_kali_has_no_host_ports() -> None:
    raw = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    kali = raw["services"]["kali"]
    assert "ports" not in kali
    assert kali.get("container_name") == "kali-tools"


def test_scraper_depends_on_kali() -> None:
    raw = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    scraper = raw["services"]["scraper_agent"]
    assert "kali" in scraper["depends_on"]
    assert scraper["environment"]["KALI_CONTAINER"] == "kali-tools"


def test_dockerfiles_exist() -> None:
    root = COMPOSE_PATH.parent
    assert (root / "docker/kali/Dockerfile").is_file()
    assert (root / "docker/scraper_agent/Dockerfile").is_file()
