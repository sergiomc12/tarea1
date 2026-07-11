# Scraper Agent
## WAZUH CON CORTES, THE HIVE, KALI

Agente de web scraping en Python para sitios de noticias: crawl recursivo, extracción de artículos estructurados, validación contra schema y checkpoints.

## Requisitos

- Python 3.11+
- `playwright install chromium` (solo si el sitio requiere render JS)

## Instalación

```powershell
cd D:\Backend\tarea1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

Copiar variables opcionales desde `.env.example` a `.env`.

## Uso rápido

```powershell
# Validar configuración YAML
scraper-agent validate-config -c config/gestion_pe.yaml

# Crawlear un dominio (salida según scraper-schema.json)
scraper-agent run --domain https://gestion.pe/ --config config/gestion_pe.yaml

# Filtrar por fecha de publicación (ISO 8601)
scraper-agent run --domain https://gestion.pe/ --config config/gestion_pe.yaml `
  --from-date 2026-07-01T00:00:00Z --to-date 2026-07-04T23:59:59Z

# Validar JSON generado contra el contrato oficial
scraper-agent validate-output output/gestion_pe.json

# Generar HTML legible (misma ruta que el JSON, extensión .html)
scraper-agent export-html output/gestion_pe.json
# -> output/gestion_pe.html
```

## Medios peruanos (multi-sitio)

### Crawl de todos los medios de una vez

Un solo comando recorre **los 10 medios** definidos en `config/sites/sites.yaml` y genera
JSON + HTML propios por sitio en `output/`:

```powershell
scraper-agent run-all

# Con filtro de fechas (aplica a todos)
scraper-agent run-all --from-date 2026-07-01T05:00:00Z --to-date 2026-07-05T04:59:59Z

# Búsqueda por objetivo en todos los medios (consolidado en output/busqueda_<label>.json)
scraper-agent run-all --target-file config/targets/licitaciones.yaml
```

Salidas esperadas (ejemplo):

| Medio | JSON | HTML |
|-------|------|------|
| gestion.pe | `output/gestion_pe.json` | `output/gestion_pe.html` |
| elcomercio.pe | `output/elcomercio_pe.json` | `output/elcomercio_pe.html` |
| … | `output/<sitio>.json` | `output/<sitio>.html` |

Lista completa en el manifiesto: `config/sites/sites.yaml`.

### Crawl de un solo medio

Configs en `config/sites/` (índice: `config/sites/sites.yaml`):

| Medio | Config | Comando ejemplo |
|-------|--------|-----------------|
| gestion.pe | `config/gestion_pe.yaml` | `scraper-agent run -c config/gestion_pe.yaml` |
| elcomercio.pe | `config/sites/elcomercio_pe.yaml` | `scraper-agent run -c config/sites/elcomercio_pe.yaml` |
| larepublica.pe | `config/sites/larepublica_pe.yaml` | `scraper-agent run -c config/sites/larepublica_pe.yaml` |
| ojo.pe | `config/sites/ojo_pe.yaml` | `scraper-agent run -c config/sites/ojo_pe.yaml` |
| trome.com | `config/sites/trome_com.yaml` | `scraper-agent run -c config/sites/trome_com.yaml` |
| elchino.pe | `config/sites/elchino_pe.yaml` | `scraper-agent run -c config/sites/elchino_pe.yaml` |
| peru21.pe | `config/sites/peru21_pe.yaml` | `scraper-agent run -c config/sites/peru21_pe.yaml` |
| expreso.com.pe | `config/sites/expreso_com_pe.yaml` | `scraper-agent run -c config/sites/expreso_com_pe.yaml` |
| libero.pe | `config/sites/libero_pe.yaml` | `scraper-agent run -c config/sites/libero_pe.yaml` |
| elperuano.pe | `config/sites/elperuano_pe.yaml` | `scraper-agent run -c config/sites/elperuano_pe.yaml` |

Tras cada crawl: `scraper-agent export-html output/<sitio>.json`

También puedes definir el rango en YAML:

```yaml
date_range:
  from: "2026-07-01T00:00:00Z"
  to: "2026-07-04T23:59:59Z"
```

**Semántica del filtro:** `--from-date` y `--to-date` definen un **intervalo continuo e
inclusivo**, no dos fechas sueltas. Se incluye un artículo si:

```text
from <= dates.published_at <= to
```

Solo se guardan artículos cuya fecha de publicación cae **dentro** de ese tramo. Las
fechas se comparan en **UTC** (ISO 8601). Ejemplo: una nota publicada el 04/07/2026 a
las 20:48 hora Lima equivale a `2026-07-05T01:48:00Z` y queda **fuera** de un
`--to-date 2026-07-04T23:59:59Z`. Para cubrir todo el día 4 en Lima, extiende `to`
hasta el fin de ese día en UTC o usa `--to-date 2026-07-05T04:59:59Z`.

## Contrato de salida

La salida cumple `scraper-schema.json` (JSON Schema Draft 2020-12). Estructura resumida:

```json
{
  "crawl_metadata": {
    "crawl_id": "gestion-20260704-235401",
    "domain": "gestion.pe",
    "crawler_version": "0.2.0",
    "total_pages_visited": 15,
    "total_articles_extracted": 8,
    "date_range_filter": { "from": null, "to": null }
  },
  "articles": [
    {
      "article_id": "gestion-abc123def456",
      "url": "https://gestion.pe/economia/nota-ejemplo/",
      "headline": { "title": "Titulo del articulo" },
      "dates": { "published_at": "2026-07-04T18:19:00Z" },
      "content_blocks": [
        { "type": "heading", "order": 0, "text": "Subtitulo" },
        { "type": "paragraph", "order": 1, "text": "Cuerpo del articulo..." }
      ],
      "media": { "cover_image": { "url": "https://..." } },
      "access": { "is_paywalled": false }
    }
  ],
  "extraction_quality": {
    "articles_fully_parsed": 6,
    "articles_partial": 2,
    "articles_failed": 0,
    "confidence_score": 0.85
  }
}
```

El formato anterior (`pages[].data` con arrays planos) está **deprecado** y ya no se genera.

### Texto enriquecido (`runs[]`)

En párrafos con enlaces **incrustados a mitad de oración** (común en gestion.pe), el campo
opcional `runs[]` preserva cada tramo sin perder el `href`. El campo `text` sigue siendo
obligatorio y la concatenación de `runs[].text` coincide con `text`.

**Antes (solo texto plano — se pierde el enlace):**

```json
{
  "type": "paragraph",
  "order": 0,
  "text": "Beijing, China.- Mientras nuevos productos agrícolas... Perú registra..."
}
```

**Después (con `runs[]` opcional):**

```json
{
  "type": "paragraph",
  "order": 0,
  "text": "Beijing, China.- Mientras nuevos productos agrícolas... Perú registra...",
  "runs": [
    { "kind": "text", "text": "Beijing, China.- " },
    {
      "kind": "link",
      "text": "Mientras nuevos productos agrícolas buscan abrirse paso hacia China, otros ya se han consolidado y concentran la mayor parte de los envíos del sector.",
      "url": "https://gestion.pe/economia/otra-nota/"
    },
    { "kind": "text", "text": " Perú registra una lista de agroexportaciones..." }
  ]
}
```

Si un párrafo no tiene enlaces inline, `runs` se omite (comportamiento válido según el schema).

En gestion.pe, el contenedor principal del artículo es `.story-contents` (no el primer
`<article>` de la página, que suele ser un widget de "más leídos"). El extractor
prioriza ese contenedor automáticamente.

**Nota sobre longitud de textos:** cada párrafo del artículo es un bloque separado en
`content_blocks[]` (no un único string gigante). La bajada bajo el titular, enlaces
destacados (`ul.sht__list`), bloques "LEA TAMBIÉN" y captions de foto se extraen como
bloques propios. La bio del autor no se incluye en el cuerpo.

## Búsqueda por objetivo profesional

Capa de filtrado **posterior** al crawl: declaras qué buscas (términos, patrones,
campos) y el motor puntúa y ordena los artículos extraídos. El pipeline de extracción
no cambia — se agrega `search_results[]` al JSON de salida.

### Comando `scraper-agent search`

```powershell
# Objetivo inline (crawl + búsqueda)
scraper-agent search `
  --url https://gestion.pe `
  --keywords "licitación,concurso público,buena pro" `
  --exclude "deportes,espectáculos" `
  --from-date 2026-07-01 --to-date 2026-07-06 `
  --min-score 0.4 `
  --match-in headline,content_blocks,outbound_links `
  --out output/busqueda_licitaciones.json

# Objetivo reutilizable desde YAML
scraper-agent search `
  --url https://gestion.pe `
  --target-file config/targets/licitaciones.yaml `
  --out output/busqueda_licitaciones.json

# Sin re-crawlear: búsqueda sobre JSON ya generado (iterar objetivos / min_score)
scraper-agent search `
  --input output/gestion_pe.json `
  --target-file config/targets/licitaciones.yaml `
  --out output/busqueda_licitaciones.json

# Mismo archivo de entrada (sobrescribe con search_results)
scraper-agent search --input output/gestion_pe.json --keywords "cobre,zinc" --min-score 0.35
```

Con `--input` no se usa red ni Playwright: solo se leen los `articles[]` del JSON,
se aplican matchers y se escribe el resultado (en `--out` o sobrescribiendo el `--input`).
Genera JSON + HTML automáticamente. Si haces crawl con `--url` y no pasas `--out`, usa la ruta del config del sitio.

### Campos de `SearchTarget`

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `label` | string | `"busqueda"` | Nombre legible del objetivo (logs, HTML, consolidado) |
| `keywords` | string[] | `[]` | Términos a buscar (OR; con `require_all: true` → AND) |
| `exclude_keywords` | string[] | `[]` | Descarta el artículo si aparece alguno |
| `patterns` | string[] | `[]` | Regex sobre los mismos campos que keywords |
| `match_in` | string[] | todos | `headline`, `excerpt`, `content_blocks`, `outbound_links`, `authors`, `taxonomy` |
| `min_score` | float 0–1 | `0.3` | Umbral mínimo para incluir en `search_results[]` |
| `require_all` | bool | `false` | Exige que aparezcan todos los `keywords` |
| `date_range` | objeto | — | Filtro adicional por `published_at` (`from` / `to`) |

Objetivos versionables en `config/targets/*.yaml`:

| Archivo | Uso |
|---------|-----|
| `licitaciones.yaml` | Licitaciones, OSCE, buena pro |
| `empleo.yaml` | Convocatorias, CAS, plazas públicas |
| `commodities.yaml` | Cobre, zinc, petróleo, precios |
| `sentencias.yaml` | Fallos, Poder Judicial, casación |
| `decretos.yaml` | Decretos supremos, normas en El Peruano |

Ejemplo: `config/targets/licitaciones.yaml`.

### Matchers (4 tipos)

| Matcher | Qué hace | Ejemplo de uso |
|---------|----------|----------------|
| **text** | Busca `keywords[]` en texto plano (sin tildes, case-insensitive) | Notas que mencionan "licitación" o "buena pro" |
| **date** | Filtra por `date_range` del objetivo (reutiliza `article_in_date_range`) | Solo noticias del 1–6 julio 2026 |
| **link** | Busca en `outbound_links` (anchor + URL) | Artículos que enlazan a `osce.gob.pe` |
| **pattern** | Aplica regex de `patterns[]` | Códigos `N° 1234-2026` o montos `S/. 1,500,000` |

### Formato `search_results[]`

Paralelo a `articles[]`, ordenado por `score` descendente. Los fragmentos usan `[[término]]`
(sin HTML) para marcar coincidencias; en el HTML exportado se convierten en `<mark>`.

```json
{
  "article_id": "gestion-abc123",
  "score": 0.87,
  "matched_fields": ["headline", "content_blocks"],
  "matched_terms": ["licitación", "buena pro"],
  "matched_snippets": [
    {
      "field": "headline",
      "text": "Gobierno convoca [[licitación]] para obra vial"
    }
  ]
}
```

`crawl_metadata.search_target` registra el objetivo usado en la corrida (auditable).

### Ejemplos listos para copiar

```powershell
# Licitaciones públicas
scraper-agent search --url https://gestion.pe --target-file config/targets/licitaciones.yaml

# Convocatorias de empleo (sin re-crawl si ya tienes el JSON)
scraper-agent search --input output/gestion_pe.json --target-file config/targets/empleo.yaml --out output/busqueda_empleo.json

# Precios de commodities
scraper-agent search --input output/gestion_pe.json --target-file config/targets/commodities.yaml

# Sentencias judiciales
scraper-agent search --input output/gestion_pe.json --target-file config/targets/sentencias.yaml

# Decretos supremos (útil con elperuano.pe / gestión normativa)
scraper-agent search --url https://elperuano.pe --target-file config/targets/decretos.yaml

# Búsqueda cruzada en los 10 medios
scraper-agent run-all --target-file config/targets/licitaciones.yaml
# -> output/busqueda_<label>.json (consolidado)
```

## Configuración

Archivos en `config/` (ej. `gestion_pe.yaml`):

| Sección | Descripción |
|---------|-------------|
| `domain` | URL semilla |
| `scope.max_pages` / `max_depth` | Límites del crawl |
| `concurrency.requests_per_second_per_domain` | Rate limit |
| `output.path` | Ruta del JSON final |
| `selectors` | Selectores CSS para título y párrafos |
| `date_range` | Intervalo inclusivo `from`→`to` por `published_at` (UTC); ver semántica arriba |
| `discovery` | Descubrimiento de URLs: `mode` (`crawl`, `rss`, `both`), `rss_feeds[]`, `max_items_per_feed` |

### Descubrimiento de artículos (`discovery`)

Por defecto el crawler hace BFS desde la home y el sitemap. Opciones avanzadas:

| Campo | Default | Qué hace |
|-------|---------|----------|
| `mode` | `crawl` | `crawl` \| `rss` \| `both` — ver abajo |
| `rss_feeds[]` | `[]` | URLs de feeds Arc/WordPress |
| `max_items_per_feed` | `30` | Tope de URLs por feed o por siembra desde home |
| `sitemap_urls[]` | `[]` | Sitemaps extra (p. ej. elperuano.pe) |
| `expand_sitemaps` | `true` | Si el sitemap es un **índice** XML, sigue los hijos y encola noticias (no trata cada `.xml` como artículo) |
| `article_link_pattern` | — | Regex sobre `href` para sembrar desde la **home** vía Playwright (requiere `prefer_playwright: true`) |

Para medios peruanos (Arc / Grupo El Comercio) conviene combinar **feeds RSS** con el crawl:

```yaml
discovery:
  mode: both          # crawl | rss | both
  rss_feeds:
    - "https://gestion.pe/arc/outboundfeeds/rss/?outputType=xml"
  max_items_per_feed: 25
  expand_sitemaps: true
```

- **`rss`**: solo URLs del feed (no sigue enlaces de secciones).
- **`both`**: feed (prioridad) + sitemap expandido + enlaces.
- **`crawl`**: comportamiento clásico BFS.

Sitemaps adicionales (WordPress, diarios oficiales):

```yaml
discovery:
  sitemap_urls:
    - "https://elperuano.pe/sitemap/noticias.xml"
```

**`expand_sitemaps: false`** — útil cuando el sitemap del sitio es plano o la expansión recursiva
encola cientos de URLs irrelevantes (ej. `expreso.com.pe`).

**`article_link_pattern`** — cuando Cloudflare bloquea httpx y el RSS no alcanza, el orchestrator
abre la home con Playwright, extrae enlaces cuyo `href` coincide con el patrón y los encola con
prioridad. Ejemplo real:

```yaml
discovery:
  mode: crawl
  expand_sitemaps: false
  article_link_pattern: "-noticia"   # URLs tipo ...-noticia12345

anti_detection:
  prefer_playwright: true
```

Si el DOM no produce párrafos, el extractor usa **`articleBody`** del JSON-LD
(`NewsArticle`) como fallback para poblar `content_blocks[]`.

### Anti-detección y Cloudflare (`anti_detection`)

Opciones en cada config YAML para sitios que devuelven **HTTP 403** o páginas de desafío Cloudflare:

| Campo | Default | Qué hace |
|-------|---------|----------|
| `session_warmup` | `true` | Visita la home antes del crawl (cookies de sesión) |
| `chrome_client_hints` | `true` | Headers `Sec-CH-UA` / `Sec-Fetch-*` coherentes con Chrome |
| `use_playwright_on_403` | `false` | Si httpx recibe 403, reintenta con Chromium headless |
| `prefer_playwright` | `false` | **Siempre** usa Playwright en lugar de httpx (sitios CF duros) |
| `random_delay_range` | `[1.0, 3.0]` | Pausa entre requests (segundos) |
| `proxies_env` | `PROXY_LIST` | Proxies opcionales desde `.env` |

```yaml
anti_detection:
  session_warmup: true
  chrome_client_hints: true
  use_playwright_on_403: true    # fallback solo ante 403
  prefer_playwright: false       # true = todo vía browser (más lento, más fiable en CF)
  random_delay_range: [2.5, 5.0]
  proxies_env: "PROXY_LIST"
```

**Cuándo usar qué**

| Síntoma | Config sugerida |
|---------|-----------------|
| Algunas URLs 403, la mayoría OK | `use_playwright_on_403: true` |
| 403 en casi todo, o HTML de “Just a moment…” | `prefer_playwright: true` + `article_link_pattern` si el RSS falla |
| Crawl muy lento pero estable | Bajar `requests_per_second_per_domain`, subir `random_delay_range` |
| 0 artículos tras CF | Revisar `playwright install chromium`; probar `config/sites/expreso_com_pe.yaml` como referencia |

Con **`prefer_playwright: true`**, el orchestrator:

1. Renderiza cada URL con Chromium (browser fresco por página, excepto la home).
2. Detecta HTML de Cloudflare (`is_cloudflare_challenge`) y reintenta con `wait_until=load`.
3. Opcionalmente siembra la cola desde la home con `article_link_pattern`.
4. Reinicia el browser entre páginas (`_reset_renderer`) para evitar sesiones corruptas.

El cliente HTTP usa un **User-Agent fijo por sesión** (no rota en cada request).
Playwright arranca con locale `es-PE`, viewport realista y `navigator.webdriver` oculto.

**Requisito:** si usas `use_playwright_on_403` o `prefer_playwright`, instala el navegador una vez:

```powershell
playwright install chromium
```

Variables de entorno (`.env`):

- `SCRAPER_USERNAME` / `SCRAPER_PASSWORD` — login opcional
- `PROXY_LIST` — proxies separados por coma

## Salida y checkpoints

- JSON consolidado: p. ej. `output/gestion_pe.json`
- Checkpoints: `output/checkpoints/<nombre>/visited_urls.json`, `frontier_queue.json`
- **JSONL incremental** (activo por defecto con `output.incremental: true`): cada artículo
  extraído se escribe al instante en `output/checkpoints/<nombre>/articles.jsonl` (una línea
  JSON por artículo). Si el proceso se cae a mitad de un crawl largo, esos artículos no se
  pierden; al reanudar, el scraper recarga el JSONL y continúa desde `visited_urls` /
  `frontier_queue`. El JSON final sigue generándose al terminar la corrida.

## Tests

```powershell
pytest
```

Los fixtures en `tests/fixtures/*.json` son salidas de ejemplo (crawl, búsqueda, consolidado)
validadas en CI contra `scraper-schema.json` (`tests/test_schema_fixtures.py`).

### CI (GitHub Actions)

Workflow `.github/workflows/ci.yml` en cada push/PR a `main`, `desarrollo` o `feature/**`:

- Python 3.11 y 3.12
- `ruff check src tests`
- `pytest tests/` (incluye validación de fixtures del schema)

Para reproducir localmente:

```powershell
pip install -e ".[dev]"
ruff check src tests
pytest tests/ -q
```

## Arquitectura

Ver `AGENTS.md`, `CONTRIBUTING.md` y `CHANGELOG.md` (leer `[Unreleased]` antes de cambiar código).

## Troubleshooting por medio

Si un sitio baja de N a 0 artículos o la calidad cae tras un cambio del portal, consulta
**`docs/troubleshooting-por-dominio.md`**: tabla síntoma → causa → fix para los 10 medios
del manifiesto y checks globales (UTC, Cloudflare, selectores, JSONL).

## Ética

Por defecto respeta `robots.txt`. Usar `--ignore-robots` solo bajo responsabilidad del operador.

## Agente de seguridad (v0.4.x)

La línea **v0.4.x** (Kali + chat en puerto 1212) incluye scraping vía chat y capa
de pentesting acotado. El alcance ético y legal está en **`docs/alcance-seguridad.md`**.

### Capa `security_env/` (implementada)

| Módulo | Rol |
|--------|-----|
| `authorization_guard.py` | Lee `config/authorized_targets.yaml`; rechaza hosts no autorizados, expirados o con categoría no permitida |
| `tool_catalog.yaml` | Catálogo cerrado (32 herramientas; ver tabla abajo) |
| `tool_runner.py` | Valida params → autoriza → ejecuta vía runtime; log auditable |
| `kali_runtime.py` | Sesiones con workspace `/tmp/<session_id>` y egress allowlist |
| `categories.py` | Constantes de categorías alineadas al documento de alcance |

### Categorías de pentesting disponibles

Cada objetivo en `authorized_targets.yaml` declara qué categorías permite en
`allowed_categories`. Sin la categoría explícita, la herramienta se rechaza aunque
el dominio esté autorizado.

| Categoría | Herramientas | Uso |
|-----------|--------------|-----|
| `passive_recon` | `whois`, `dig_a`, `nslookup_a`, `curl_headers`, `whatweb_safe`, `httpx_probe`, `wafw00f_safe` | WHOIS, DNS A, headers HTTP, fingerprint web |
| `dns_enumeration` | `dnsenum_safe`, `dnsrecon_std`, `sublist3r_safe`, `fierce_safe` | Enum DNS / subdominios acotado |
| `network_discovery` | `netdiscover_passive` | Solo CIDR autorizado; ping sweep acotado |
| `light_active_scan` | `nmap_top100` | TCP top 100 puertos, sin NSE |
| `active_scanning` | `nmap_services`, `masscan_top_ports`, `zmap_safe`, `unicornscan_safe` | Servicios/puertos rate-limited, 1 host |
| `known_vuln_scanning` | `nikto_safe`, `nuclei_safe` | Nikto / Nuclei templates no destructivos |
| `osint_recon` | `amass_passive`, `theharvester_safe`, `spiderfoot_passive` | OSINT pasivo acotado |
| `bounded_fuzzing` | `gobuster_dir`, `dirb_small`, `ffuf_dir`, `wpscan_enum` | Wordlists pequeñas; sin brute credenciales |
| `tls_analysis` | `sslscan_safe`, `sslyze_safe`, `testssl_safe`, `openssl_cert` | Certificado, cipher suites, protocolos TLS |
| `vuln_script_scanning` | `nmap_vuln_scripts` | Subconjunto seguro de scripts NSE (sin `--script vuln` completo) |
| `ics_scada_recon` | `modbus_s7_discover` | Identificación Modbus/S7 solo-lectura; requiere autorización industrial explícita |

> `external_api_recon` (Shodan/Censys) fue **retirada** el 2026-07-07 — ver `CHANGELOG.md`.

Ejemplo en `config/authorized_targets.yaml.example`: descomentar las categorías
ampliadas solo tras autorización explícita del responsable del activo.

Copiar `config/authorized_targets.yaml.example` → `config/authorized_targets.yaml`
antes de usar herramientas de seguridad en un despliegue real.

```python
# Uso programático (tests usan FakeExecutor; producción usará contenedor Kali)
from scraper_agent.security_env import (
    AuthorizationGuard,
    KaliRuntime,
    ToolRunner,
    load_authorized_targets,
    load_tool_catalog,
)
```

Pendiente: métricas Prometheus / health extendido (v0.3.x backlog).

### Cliente DeepSeek (`agent/llm_client.py`) — ítem 11

| Variable | Descripción |
|----------|-------------|
| `DEEPSEEK_API_KEY` | Obligatoria para el agente LLM |
| `DEEPSEEK_API_URL` | Default `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | Default `deepseek-chat` (compatible tool calls; migrar a `deepseek-v4-flash`) |

**Tool-use confirmado:** DeepSeek expone function calling en `POST /chat/completions` (formato OpenAI).
Modo preferido: `tool_calls`; fallback documentado: respuesta JSON con `{"action": "...", "arguments": {...}}`.

Tools expuestas al LLM: `run_site_crawl`, `search_crawl_output`, `list_security_tools`, `run_security_tool`.

### Chat API (ítem 12)

```powershell
# Requiere DEEPSEEK_API_KEY en .env
scraper-agent serve --port 8000

# Health
curl http://localhost:8000/health

# Chat con streaming SSE
curl -N -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\": \"lista herramientas de seguridad\"}"
```

Eventos SSE: `status`, `tool_start`, `tool_end`, `assistant_delta`, `final`, `error`.
Sesiones auditadas en `output/sessions/<session_id>.jsonl`.

### Despliegue Docker Compose (ítem 13)

```powershell
# 1. Copiar plantillas
copy config\authorized_targets.yaml.example config\authorized_targets.yaml
copy .env.example .env
# Editar .env: DEEPSEEK_API_KEY=...

# 2. Levantar pila (único puerto host: 1212)
docker compose up --build -d

# 3. Probar
curl http://localhost:1212/health
curl -N -X POST http://localhost:1212/chat -H "Content-Type: application/json" -d "{\"message\": \"lista herramientas kali\"}"
```

| Servicio | Rol | Puerto host |
|----------|-----|-------------|
| `scraper_agent` | API chat + scraper + agente LLM | **1212** → 8000 |
| `kali` (`kali-tools`) | whois, dig, curl, nmap, nikto, gobuster, seclists | ninguno (solo red interna + docker exec) |

`scraper_agent` monta `/var/run/docker.sock` para ejecutar herramientas en Kali vía `docker exec`.
Variables: `KALI_CONTAINER=kali-tools`, `DEEPSEEK_API_KEY` (requerida para chat).

Tras cambios en `docker/kali/Dockerfile` (CA certs, whois), reconstruir solo Kali:

```powershell
docker compose build kali
docker compose up -d kali
```

**Pentest repetible** (host debe estar en `authorized_targets.yaml`):

```powershell
# Sin --phase corre TODO el catálogo (32 herramientas) — es el default desde
# 2026-07-07. "full" se calcula desde tool_catalog.yaml en cada corrida, no
# es una lista fija: cualquier herramienta nueva del catálogo se incluye
# automáticamente. Puede tardar >30 min (Nuclei, SpiderFoot, wpscan
# actualizan sus fuentes antes de escanear).
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net
# Informe: output/pentest_krapcom_net.json — exit 0 solo si todas las herramientas pasan.
# Herramientas no aplicables al objetivo o no autorizadas para su categoría
# (ej. netdiscover_passive contra un dominio, modbus_s7_discover sin
# ics_scada_recon) no se omiten en silencio: quedan como FAIL en el reporte
# con el motivo exacto.

# Fase 5a — recon DNS intermedio
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 5a

# Fase 5b — masscan + Nuclei (masscan resuelve IP vía dig_a)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 5b

# Fase 5c — OSINT avanzado (Amass, theHarvester, SpiderFoot; puede tardar varios minutos)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 5c

# Fase 5d — fuzzing web (dirb, ffuf, wpscan enum)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 5d

# Fase 6a — escaneo ampliado (zmap, unicornscan)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6a

# Fase 6b — recon web / fingerprint (whatweb, httpx, wafw00f)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6b

# Fase 6c — TLS/SSL (sslscan, sslyze, testssl.sh, openssl)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6c

# Fase 6d — DNS adicional (fierce)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6d

# Fase 6e — subconjunto seguro de scripts NSE
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6e

# Fase 6f — ICS/SCADA solo-lectura (requiere categoría ics_scada_recon dedicada
# por objetivo en authorized_targets.yaml, por riesgo sobre sistemas
# industriales reales; sí está incluida en --phase full, pero fallará con
# AuthorizationDenied contra cualquier objetivo que no la tenga habilitada)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase 6f

# Equivalente explícito al default (catálogo completo, sin Shodan/Censys — retirados)
.\.venv\Scripts\python.exe scripts\run_pentest.py krapcom.net --phase full

# netdiscover solo contra CIDR en authorized_targets (ej. 203.0.113.0/28)
.\.venv\Scripts\python.exe scripts\run_pentest.py 203.0.113.0/28 --tools netdiscover_passive
```

## Capa defensiva (`defense_env/`)

`defense_env/` es la contraparte **defensiva** de `security_env/`: vigila el propio
proyecto/host en vez de atacar objetivos externos. Todo lo de abajo está
implementado (ver `CHANGELOG.md` para el detalle completo, incluyendo qué NO
se implementó a propósito y por qué):

1. **FIM** (File Integrity Monitoring) — detecta drift en archivos críticos y
   en el código fuente (backdoors).
2. **Correlación** — reglas tipo Sigma sobre el audit log de herramientas.
3. **Respuesta activa (lockdown)** — circuit breaker que detiene a `tarea1`
   mismo ante alerta `critical`.
4. **Gestión de casos** — equivalente acotado a TheHive.
5. **Aislamiento de red** — desconecta de la red al contenedor comprometido
   (distinto del lockdown: esto detiene a un atacante externo, no a `tarea1`).
6. **Ransomware** — detector de ráfaga de cambios masivos, dispara aislamiento.
7. **Fugas de información** — canary files (honeytokens).
8. **Exploits** — self-scan defensivo (el catálogo ofensivo, contra sí mismo).
9. **Defensa del sistema operativo** — bloqueo de IP/puerto y kill de
   procesos a nivel de host Linux real (CentOS/RHEL), no solo contenedores.
10. **Agente continuo** — FIM del SO + fuerza bruta SSH + bloqueo
    automático + identificación de atacante, en loop 24/7.

### 1. FIM

Vigila (por defecto) `config/authorized_targets.yaml`,
`security_env/tool_catalog.yaml`, `security_env/categories.py`,
`docker-compose.yml`, `docker/kali/Dockerfile`, **y `.env`** — ver
`config/defense/fim_watch.yaml`.

`.env` se vigila **hash-only**: FIM nunca lee ni almacena el contenido de
ningún archivo, solo un SHA-256 (así funciona desde el día 1 para todos los
archivos, no es un modo especial para `.env`). Un hash no es reversible al
secreto original. Si corrés `defense_watcher` en Docker, `.env` necesita su
propio bind mount (`./.env:/app/.env:ro`) — `env_file:` de Compose solo
inyecta las variables ya resueltas al proceso, no monta el archivo en el
filesystem del contenedor.

```powershell
# 1. Generar el baseline (estado conocido-bueno) — correr una sola vez o tras un
#    cambio legítimo intencional
scraper-agent fim-baseline

# 2. Comparar el estado actual contra el baseline
scraper-agent fim-scan
```

Vigilancia **continua**: servicio `defense_watcher` en `docker-compose.yml`
(reusa la imagen de `scraper_agent`; corre `fim-scan` **y** `defense-correlate`
en el mismo loop cada `DEFENSE_SCAN_INTERVAL_SECONDS`, default 300s — antes
se llamaba `fim_watcher` y solo corría FIM, ver `CHANGELOG.md`):

```powershell
docker compose up -d defense_watcher
```

**Severidad de las alertas de FIM:**

| Severidad | Cuándo | Exit code de `fim-scan` |
|-----------|--------|--------------------------|
| `critical` | Se modificó o borró un archivo en `critical_files` (`authorized_targets.yaml`, `tool_catalog.yaml`) — amplían el alcance ofensivo autorizado | `1` (+ lockdown + caso automáticos) |
| `high` | Se modificó o borró cualquier otro archivo vigilado | `1` |
| `medium` | Apareció un archivo nuevo dentro de un path vigilado | `0` |

Alertas críticas/altas se etiquetan con la técnica MITRE ATT&CK `T1565`
(Data Manipulation). Persisten en `output/security/fim_alerts.jsonl`.

### 2. Motor de correlación

Reglas tipo Sigma simplificado (YAML: filtro de campos + umbral de frecuencia
opcional) sobre `output/security/tool_audit.jsonl` (audit log real de
`tool_runner`, ya persistido a disco). 2 reglas incluidas en
`defense_env/rules/builtin/`: rechazos repetidos de autorización (posible
sondeo) y ejecución de categorías de alto impacto (visibilidad/auditoría).

```powershell
scraper-agent defense-correlate
```

Corre continua junto con FIM dentro de `defense_watcher` (ver sección 1) —
no hace falta dispararla a mano en producción.

### 3. Respuesta activa (lockdown)

Circuit breaker **fail-closed**: una alerta `critical` de FIM o correlación
bloquea TODA ejecución ofensiva (`AuthorizationGuard` deniega todo, sin
importar si el target/categoría normalmente estarían autorizados) hasta que
un humano lo levanta explícitamente. Sin auto-recuperación, a propósito.

```powershell
# Ver si hay un lockdown activo y por qué
scraper-agent defense-status

# Levantarlo (requiere --yes explícito)
scraper-agent defense-clear-lockdown --yes
```

Desactivar el auto-lockdown para calibrar reglas sin bloquearse:
`scraper-agent fim-scan --no-auto-lockdown` / `defense-correlate --no-auto-lockdown`.

### 4. Gestión de casos

Equivalente acotado a TheHive: una alerta `critical` abre un caso
automáticamente (agrupa la investigación en vez de perderse en el JSONL
crudo de alertas).

```powershell
scraper-agent defense-case-list [--status open|investigating|closed]
scraper-agent defense-case-create "Título del caso" [--severity high]
scraper-agent defense-case-close <id-o-prefijo> [--note "causa raíz"]
```

### 5. Aislamiento de red (respuesta a un atacante externo real)

**Distinto del lockdown de la sección 3**: el lockdown detiene la ejecución
ofensiva *de `tarea1` mismo* (útil si sus propias credenciales fueron
robadas). Esto responde al caso que el lockdown NO cubre: un atacante
externo comprometiendo la infraestructura de `tarea1`. La acción es
`docker network disconnect` real sobre el contenedor afectado.

```powershell
scraper-agent defense-isolation-status
scraper-agent defense-reconnect --yes
```

### 6. Ransomware

Detector de ráfaga: si 5+ archivos vigilados cambian en el mismo ciclo de
`fim-scan` (patrón de cifrado/borrado masivo, MITRE `T1486`), abre un caso
`critical` **y** aísla de red el contenedor configurado automáticamente
(`--auto-isolate`, default on). Limitación honesta: solo ve los paths de
`config/defense/fim_watch.yaml`, no "la mayoría del filesystem".

### 7. Fugas de información (canary files)

Archivos señuelo (honeytokens) con contenido de cebo realista, sin ningún
uso legítimo — cualquier interacción dispara `critical`.

```powershell
scraper-agent defense-canary-deploy
scraper-agent defense-canary-check
```

Limitación honesta: la señal es modificación/borrado/movido, no lectura
(`atime` no es confiable entre filesystems — se evaluó y se descartó a
propósito).

### 8. Exploits (self-scan defensivo)

Reusa el catálogo **ofensivo** de `security_env/` (las mismas herramientas
del pentest) contra la propia infraestructura, resolviendo la IP real del
contenedor vía `docker inspect` — nunca toca `config/authorized_targets.yaml`.

```powershell
scraper-agent defense-self-scan --tools nmap_top100,curl_headers,whatweb_safe
```

No interpreta el hallazgo por vos — entrega el resultado crudo de cada
herramienta para revisión humana.

### 9. Defensa del sistema operativo (servidor Linux real — CentOS/RHEL)

**Distinto de todo lo de arriba**: las secciones 1-8 actúan sobre
contenedores Docker propios de `tarea1`. Esto actúa sobre el **sistema
operativo del servidor real** donde corra `tarea1` en producción (pensado
para CentOS/RHEL). Auto-detecta el sistema operativo y qué herramienta de
firewall está REALMENTE instalada (`firewalld` → `nftables` → `iptables`,
en ese orden de prioridad) — no asume ninguna fija.

```powershell
# Correr esto PRIMERO en el servidor real, antes que cualquier otro comando de esta sección
scraper-agent defense-host-detect

# Cerrar conexión de una IP (bloqueo total, nivel SO)
scraper-agent defense-host-block-ip 203.0.113.7 --yes

# Cerrar un puerto
scraper-agent defense-host-close-port 8080 --yes

# Matar un proceso (por PID o por nombre)
scraper-agent defense-host-kill-process --pid 1234 --yes
scraper-agent defense-host-kill-process --name "proceso_malicioso" --yes

# Ver conexiones de red activas (solo lectura)
scraper-agent defense-host-connections
```

Las 3 acciones destructivas exigen `--yes` explícito — no se ejecuta nada
irreversible sobre el sistema operativo real por accidente.

### 10. Agente continuo (FIM del SO + fuerza bruta SSH + respuesta automática)

Cierra el gap "todo manual" de la sección 9: un ciclo que vigila archivos
críticos del SO (`config/defense/host_fim_watch.yaml`: `/etc/passwd`,
`/etc/shadow`, `/etc/ssh/sshd_config`, `/etc/sudoers`, cron,
`authorized_keys`) y detecta fuerza bruta SSH (`/var/log/secure`) —
5+ intentos fallidos desde la misma IP en 2 minutos **bloquea esa IP
automáticamente** y corre recon pasivo (`whois`/`dig`) para ayudar a
identificar al atacante.

```powershell
# Un solo ciclo (para probar, o para cron)
scraper-agent defense-host-agent-cycle

# Loop continuo -- dos formas:
# (a) systemd (preferido en RHEL/CentOS):
sudo cp scripts/tarea1-host-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tarea1-host-agent

# (b) script bash (cualquier Linux, sin systemd):
chmod +x scripts/host_agent_loop.sh
HOST_AGENT_INTERVAL_SECONDS=60 ./scripts/host_agent_loop.sh &
```

Solo la fuerza bruta SSH dispara bloqueo automático — una alerta crítica
de FIM abre un caso pero no bloquea nada sola (no trae una IP de origen
confiable para actuar).

### Extensión nativa opcional (C++/pybind11) para el hashing de FIM

`defense_env/_fim_native/` — motor de hashing SHA-256 en C++ (OpenSSL EVP),
compilado y **verificado correcto** dentro de Docker (hash idéntico a
`hashlib` de Python, byte a byte). Completamente opcional: si no está
compilada (Windows sin toolchain, o un servidor sin `build-essential`),
`fim.py` cae solo a `hashlib` puro sin que ningún comando falle. No hace
falta ninguna acción manual — se compila sola durante `docker build`.

**Limitación honesta, la más importante de esta sección**: desarrollado y
testeado en un entorno Windows, sin acceso a un CentOS/RHEL real para
verificar contra infraestructura de producción de verdad (a diferencia de
las secciones 1-8, que sí se probaron contra los contenedores Docker reales
de este proyecto). Correr `defense-host-detect` en el servidor real y
revisar el resultado antes de confiar en el resto de los comandos.

**Limitaciones honestas generales** (ver detalle completo en `CHANGELOG.md`):
- La respuesta activa es deliberadamente conservadora: sin reversión
  automática de ninguna acción de esta sección — un humano deshace la
  regla de firewall a mano.
- **Botnets: explícitamente no implementado.** Requeriría análisis de
  tráfico de red (beaconing C2, DNS) para el que no hay visibilidad real en
  este entorno (Docker Desktop en Windows).
- Esto no reemplaza un SIEM/XDR de producción como Wazuh (agentes en
  endpoints, miles de reglas de correlación, motor de indexado a escala,
  compliance mapping) — es una capa defensiva real y creciente para este
  proyecto específico, no una migración de Wazuh.
