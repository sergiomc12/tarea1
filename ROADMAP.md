# Roadmap

## v0.2.x — Migración a scraper-schema.json (en curso)

- [x] Extracción `articles[]` con `content_blocks[]`, `media`, `links`, `dates`, `access`
- [x] Validación post-crawl con `jsonschema` + comando `validate-output`
- [x] Filtro por rango de fechas (`--from-date` / `--to-date` y `date_range` en YAML)
- [~] Selectores por sitio más robustos — configs base en `config/sites/` para 9 medios + gestion.pe
- [x] Extracción completa de `authorship.authors[]` y `taxonomy` (2026-07-06)
- [x] Búsqueda por objetivo profesional (`scraper-agent search`, `search_results[]`) (2026-07-06)
- [x] Validación por artículo bloqueante antes de persistir (2026-07-05)
- [x] Soporte JSONL incremental para corridas largas

## v0.3.x — Operación y calidad

- [ ] Métricas Prometheus / health endpoint opcional
- [ ] Perfiles de sitio predefinidos (`config/sites/`)
- [x] CI con pytest + validación de fixtures contra schema (2026-07-06)
- [x] Documentación de selectores y troubleshooting por dominio (`docs/troubleshooting-por-dominio.md`, 2026-07-06)
- [x] Objetivos de búsqueda predefinidos (`config/targets/`: licitaciones, empleo, commodities, sentencias, decretos)

## v1.0 — Release estable

- [ ] Todos los ítems `[Unreleased]` del CHANGELOG en `[x]`
- [x] Eliminar código legacy (`PageRecord`, parsers viejos) (2026-07-06)
- [x] Guía `CONTRIBUTING.md` (2026-07-06)
- [ ] Guía de contribución y ejemplos multi-dominio
