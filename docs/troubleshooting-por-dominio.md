# Troubleshooting por dominio

Guía rápida cuando un medio pasa de **N artículos a 0**, devuelve muchos
`articles_partial`, o el crawl termina sin errores pero sin noticias útiles.

Antes de cambiar config, revisa siempre:

1. `output/<sitio>.json` → `crawl_metadata.errors[]` y `total_pages_visited`
2. `output/checkpoints/<sitio>/articles.jsonl` → artículos parciales tras un crash
3. Logs con nivel `INFO` o `DEBUG` (`--log-level DEBUG`)
4. Filtro de fechas en **UTC** (ver README, sección date_range)

---

## Síntomas globales (cualquier medio)

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| `total_articles_extracted: 0`, muchas páginas visitadas | Filtro `date_range` / `--to-date` en UTC excluye todo | Extiende `to` en UTC (ej. `2026-07-05T04:59:59Z` para cubrir el 4 en Lima) |
| `total_pages_visited: 0` | Feed/sitemap vacío o bloqueado | Revisa `discovery.mode`, URLs del feed, 403 en logs |
| HTTP 403 en casi todas las URLs | Anti-bot / Cloudflare | `use_playwright_on_403: true` o `prefer_playwright: true` + `playwright install chromium` |
| HTML "Just a moment…" | Cloudflare challenge | `prefer_playwright: true`, delays más altos, referencia `config/sites/expreso_com_pe.yaml` |
| `confidence_score` muy bajo, `articles_partial` alto | DOM distinto al esperado | Ajusta `selectors.article_root` / `parrafos` en el YAML del sitio |
| Mismo texto en todos los `content_blocks` | Widget lateral capturado como cuerpo | Prioriza `.story-contents` (Arc) o selector específico del medio |
| Crawl interrumpido, JSON final vacío | Proceso matado antes de `write_final` | Recupera `output/checkpoints/<sitio>/articles.jsonl` y reanuda el crawl |
| Búsqueda sin resultados con JSON lleno | `min_score` alto o keywords mal elegidas | `scraper-agent search --input output/<sitio>.json` con otro `--min-score` |

---

## Por medio (10 sitios del manifiesto)

### gestion.pe

| | |
|---|---|
| **Config** | `config/gestion_pe.yaml` |
| **Discovery** | `mode: both` + feed Arc RSS |
| **Anti-bot** | httpx suele bastar |
| **Selectores** | `.story-contents` (crítico: no usar el primer `<article>` de la página) |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| 0 artículos con fechas “correctas” en Lima | `published_at` en UTC posterior a `--to-date` | Ampliar `to` en UTC |
| Pocos artículos vs portal | `max_pages: 30`, feed limitado a 25 | Subir `max_items_per_feed` / `max_pages` |
| `content_blocks` vacíos o repetidos | Selector de cuerpo incorrecto | Confirmar `article_root: ".story-contents"` |
| Enlaces inline perdidos | Sin `runs[]` | Ya soportado; regenerar JSON con versión actual |

---

### elcomercio.pe

| | |
|---|---|
| **Config** | `config/sites/elcomercio_pe.yaml` |
| **Discovery** | `mode: both` + feed Arc |
| **Notas** | Misma familia Arc que gestion.pe |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Similar a gestion.pe | Mismo stack Arc | Mismos fixes: RSS + `.story-contents` |
| RSS falla (404) | URL de feed cambiada en el portal | Actualizar `discovery.rss_feeds[]` desde el sitio |

---

### larepublica.pe

| | |
|---|---|
| **Config** | `config/sites/larepublica_pe.yaml` |
| **Discovery** | `mode: both`, feed `rss/home.xml` |
| **Calidad** | Suele dar más `articles_partial` (DOM distinto) |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Artículos con poco cuerpo | Selectores genéricos | Refinar `selectors` en el YAML; revisar `extraction_quality` |
| 0 tras cambio del portal | Feed o estructura HTML nueva | Probar feed en navegador; ajustar `article_root` |

---

### ojo.pe

| | |
|---|---|
| **Config** | `config/sites/ojo_pe.yaml` |
| **Discovery** | `mode: both` + feed Arc |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| `articles_partial` alto | DOM no estándar Arc | Igual que larepublica: selectores + JSON-LD fallback |
| Pocas URLs encoladas | `max_depth: 2` | Normal con RSS; confiar en el feed |

---

### trome.com

| | |
|---|---|
| **Config** | `config/sites/trome_com.yaml` |
| **Discovery** | `mode: rss`, `max_depth: 8` |
| **Fechas** | Muy sensible a UTC en filtro |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| 0 artículos con rango “julio 1–6” local | Notas del 4–5 julio en UTC caen fuera del `to` | Usar `to: 2026-07-06T04:59:59Z` o equivalente |
| Pocas notas | Solo RSS, 25 ítems | Subir `max_items_per_feed` |

---

### peru21.pe

| | |
|---|---|
| **Config** | `config/sites/peru21_pe.yaml` |
| **Discovery** | `mode: rss` |
| **Anti-bot** | `use_playwright_on_403: true` (histórico 0→16 artículos) |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| 0 artículos, 403 en logs | Bloqueo httpx | Activar `use_playwright_on_403`; instalar Chromium |
| Playwright no arranca | Binario no instalado | `playwright install chromium` |

---

### expreso.com.pe

| | |
|---|---|
| **Config** | `config/sites/expreso_com_pe.yaml` |
| **Discovery** | `article_link_pattern: "-noticia"`, `expand_sitemaps: false` |
| **Anti-bot** | `prefer_playwright: true` (Cloudflare) |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| 0 artículos, CF en HTML | httpx insuficiente | `prefer_playwright: true` (ya en config) |
| Cola vacía | Sin patrón en home | Verificar `article_link_pattern` sigue coincidiendo con URLs del sitio |
| Muy lento | Playwright por página + delays | Esperado; no subir concurrencia en CF |
| Sitemap encola basura | Índice XML expandido | Mantener `expand_sitemaps: false` |

---

### libero.pe

| | |
|---|---|
| **Config** | `config/sites/libero_pe.yaml` |
| **Discovery** | `mode: rss`, `max_depth: 8` |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| 0 artículos tras fix de depth | Antes `max_depth: 2` bloqueaba feed | Usar `max_depth: 8` (ya en config) |
| Feed vacío | URL RSS cambiada | Comprobar `https://libero.pe/rss/home.xml` |

---

### elchino.pe

| | |
|---|---|
| **Config** | `config/sites/elchino_pe.yaml` |
| **Discovery** | `post-sitemap.xml` + `mode: both` |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Sitemap ilegible / 0 URLs | `Accept-Encoding: br` corrupto | Fix en `fetcher/headers.py` (ya aplicado) |
| Muchas URLs, pocos artículos | Filtro de fechas o `max_pages` | Revisar `date_range` y límites |

---

### elperuano.pe

| | |
|---|---|
| **Config** | `config/sites/elperuano_pe.yaml` |
| **Discovery** | `sitemap_urls[]` explícitos, expansión de índices |

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Páginas visitadas = XML sin artículos | Sitemap índice sin expandir | `expand_sitemaps: true` (default); URLs en `sitemap_urls` |
| `articles_partial` | WordPress / DOM propio | Ajustar selectores; validar JSON-LD `articleBody` |

---

## Comandos útiles de diagnóstico

```powershell
# Un solo medio con log detallado
scraper-agent run -c config/gestion_pe.yaml --log-level DEBUG

# Validar salida
scraper-agent validate-output output/gestion_pe.json

# Búsqueda sin re-crawl (probar si hay datos en el JSON)
scraper-agent search --input output/gestion_pe.json --keywords "economía" --min-score 0.0

# Reanudar tras crash (misma config; lee checkpoint + articles.jsonl)
scraper-agent run -c config/sites/expreso_com_pe.yaml
```

---

## Cuándo abrir un ítem en CHANGELOG

Si un fix requiere **código** (no solo YAML), agrégalo en `[Unreleased]` → `### Fixed`
con el dominio y el síntoma. Si solo actualizas config del sitio, documenta la fecha
en este archivo y en la nota del YAML si aplica.

Ver también: `README.md` (anti-bot / discovery), `CHANGELOG.md` (`[Unreleased]`).
