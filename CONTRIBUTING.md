# Contribuir a scraper-agent

Gracias por mejorar el scraper de noticias peruanas. El contrato de salida único es
**`scraper-schema.json`** — todo cambio que afecte JSON generado debe validarse contra ese
schema.

Antes de abrir un PR:

1. Lee `CHANGELOG.md` → sección `[Unreleased]`
2. Ejecuta `ruff check src tests` y `pytest tests/ -q`
3. Si tocas salida JSON, añade o actualiza fixtures en `tests/fixtures/`

---

## Añadir un medio nuevo

### 1. Config YAML

Crea `config/sites/<slug>.yaml` (slug = dominio con puntos → guiones bajos, ej. `foo_pe.yaml`).

Plantilla mínima (Arc / feed RSS):

```yaml
domain: "https://ejemplo.pe/"
discovery:
  mode: both
  rss_feeds:
    - "https://ejemplo.pe/arc/outboundfeeds/rss/?outputType=xml"
  max_items_per_feed: 25
scope:
  max_depth: 2
  max_pages: 30
output:
  path: "output/ejemplo_pe.json"
  checkpoint_dir: "output/checkpoints/ejemplo_pe"
selectors:
  article_root: ".story-contents"
  titulo: "h1"
  parrafos: ".story-contents p, article p"
```

Sitio con Cloudflare: copia `config/sites/expreso_com_pe.yaml` (`prefer_playwright`,
`article_link_pattern`). Ver `docs/troubleshooting-por-dominio.md`.

### 2. Manifiesto

Añade la entrada en `config/sites/sites.yaml`:

```yaml
  - name: ejemplo.pe
    config: config/sites/ejemplo_pe.yaml
    domain: https://ejemplo.pe/
```

### 3. Validar

```powershell
scraper-agent run -c config/sites/ejemplo_pe.yaml
scraper-agent validate-output output/ejemplo_pe.json
```

Si `extraction_quality.confidence_score` es bajo, ajusta `selectors` en el YAML antes del PR.

### 4. Documentar

- Entrada breve en `docs/troubleshooting-por-dominio.md` si el sitio tiene peculiaridades
- Línea en `CHANGELOG.md` bajo `[Unreleased]`

---

## Añadir un objetivo de búsqueda (`config/targets/`)

1. Copia `config/targets/licitaciones.yaml`
2. Ajusta `label`, `keywords`, `patterns`, `match_in`, `min_score`
3. Campos válidos en `match_in`: `headline`, `excerpt`, `content_blocks`, `outbound_links`,
   `authors`, `taxonomy`
4. Prueba sin crawl:

```powershell
scraper-agent search --input output/gestion_pe.json --target-file config/targets/mi_objetivo.yaml --out output/busqueda_test.json
```

5. El test `test_all_predefined_targets_load` debe seguir pasando (añade tu YAML al directorio)

---

## Cambiar el extractor o el schema

| Cambio | Archivos típicos | Tests |
|--------|------------------|-------|
| Nuevos campos en artículo | `parser/article_extractor.py`, `scraper-schema.json` | `test_article_extractor.py`, fixture JSON |
| Validación | `storage/schema_validator.py` | `test_schema_fixtures.py` |
| Búsqueda | `search/matchers.py`, `search/scorer.py` | `test_search.py` |
| Crawl / discovery | `crawler/orchestrator.py` | `test_crawler.py` |

**Regla:** si modificas `scraper-schema.json`, actualiza al menos un fixture en
`tests/fixtures/` y ejecuta `pytest tests/test_schema_fixtures.py`.

---

## Estilo de código

- Python 3.11+, tipos en firmas públicas
- Inmutabilidad: preferir copias nuevas a mutar listas/dicts in-place
- Sin `print()` — usar `logging_config` / structlog
- Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:` (conventional commits)
- PR: describir medios probados y pegar salida de `pytest` + `validate-output` si aplica

---

## Qué no incluir en PRs

- Secretos (`.env`, API keys, proxies con credenciales)
- `output/*.json` de corridas reales (salvo fixtures mínimos sintéticos en `tests/fixtures/`)
- Cambios masivos no relacionados con el ítem del CHANGELOG

---

## Recursos

| Documento | Contenido |
|-----------|-----------|
| `README.md` | Uso CLI, anti-bot, búsqueda |
| `AGENTS.md` | Arquitectura para agentes de IA |
| `docs/troubleshooting-por-dominio.md` | Diagnóstico por medio |
| `scraper-schema.json` | Contrato de salida |
| `.github/workflows/ci.yml` | Pipeline CI |
