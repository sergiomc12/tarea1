"""Genera configs de sitios — uso interno."""

from pathlib import Path

SITES = [
    ("elcomercio_pe", "https://elcomercio.pe/"),
    ("larepublica_pe", "https://larepublica.pe/"),
    ("ojo_pe", "https://ojo.pe/"),
    ("trome_com", "https://trome.com/"),
    ("elchino_pe", "https://elchino.pe/"),
    ("peru21_pe", "https://peru21.pe/"),
    ("expreso_com_pe", "https://www.expreso.com.pe/"),
    ("libero_pe", "https://libero.pe/"),
    ("elperuano_pe", "https://elperuano.pe/"),
]

TEMPLATE = """domain: "{domain}"
scope:
  include_subdomains: false
  max_depth: 2
  max_pages: 15
  exclude_patterns:
    - "/logout"
    - "/login"
    - "/suscri"
    - "/autor/"
    - "\\\\.(pdf|zip|jpg|jpeg|png|gif|webp|mp4|svg)$"
concurrency:
  max_workers: 4
  requests_per_second_per_domain: 1
retry:
  max_attempts: 3
  backoff_factor: 2
render:
  mode: "auto"
auth:
  enabled: false
  login_url: ""
  username_env: "SCRAPER_USERNAME"
  password_env: "SCRAPER_PASSWORD"
anti_detection:
  rotate_user_agent: true
  random_delay_range: [1.5, 3.0]
  proxies_env: "PROXY_LIST"
output:
  format: "json"
  path: "output/{slug}.json"
  checkpoint_dir: "output/checkpoints/{slug}"
date_range:
  from: "2026-07-01T05:00:00Z"
  to: "2026-07-05T04:59:59Z"
respect_robots_txt: true
selectors:
  article_root: ".story-contents"
  titulo: "h1"
  titulos_seccion: "h2, h3"
  parrafos: "article p, .story-contents p, p"
"""


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "config" / "sites"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, domain in SITES:
        path = out_dir / f"{slug}.yaml"
        path.write_text(TEMPLATE.format(domain=domain, slug=slug), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
