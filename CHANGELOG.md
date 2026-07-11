# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

## Cómo usar este archivo (leer antes de tocar código)

- **`[Unreleased]`** es la única sección donde se agregan cambios en curso. Nunca se
  agregan cambios directamente a una versión ya publicada.
- Cada ítem dentro de `[Unreleased]` tiene un estado explícito:
  - `[ ]` pendiente — no implementado.
  - `[~]` en progreso — implementado parcialmente, ver nota.
  - `[x]` resuelto — implementado y validado. **No se debe re-trabajar.**
- Antes de proponer o implementar cualquier cambio, el agente/dev debe:
  1. Buscar en `[Unreleased]` si el ítem ya existe.
  2. Si existe como `[x]` → está resuelto, no se repite el trabajo.
  3. Si existe como `[ ]` o `[~]` → continuar desde ahí, no reescribir desde cero.
  4. Si no existe → agregarlo como `[ ]` con referencia al campo/módulo del schema afectado.
- Cuando un ítem se marca `[x]`, se agrega la fecha y un breve "cómo se validó"
  (ej. "validado con jsonschema Draft202012Validator, 0 errores").
- Al cortar una versión (release), todo lo que esté `[x]` en `[Unreleased]` se mueve
  en bloque a una nueva sección con número de versión y fecha; `[Unreleased]` queda vacío.
- **`README.md` se actualiza siempre que haya un cambio en `[Unreleased]`, sin excepción.**
  Ningún ítem se marca `[x]` si el `README.md` no refleja ya ese cambio (ejemplos de
  formato de salida, referencia al schema vigente, instrucciones de uso actualizadas,
  etc.). Si un cambio no requiere tocar el README (ej. un fix interno invisible al
  usuario), se debe declarar explícitamente `README: no aplica — <razón>` en la entrada,
  para dejar constancia de que se evaluó y no fue una omisión.
- **Un ítem `[x]` con tests sintéticos no es lo mismo que un ítem validado contra una
  corrida real.** Si una corrida real (`gestion_pe.json` de producción) contradice lo
  que un ítem `[x]` afirma, se documenta como un **bug nuevo** en `### Fixed` — no se
  revierte el `[x]` original silenciosamente, para no perder el rastro de qué se
  probó y con qué datos.

## [Unreleased]

### Contexto del cambio

El proyecto fue creado inicialmente con un formato de salida de scraping **insuficiente**
para explotar la información de noticias. Formato original (obsoleto, deprecado):

```json
{
  "domain": "ejemplo.com",
  "crawl_started_at": "2026-07-04T10:00:00Z",
  "crawl_finished_at": "2026-07-04T10:45:12Z",
  "total_pages_visited": 342,
  "total_records_extracted": 1287,
  "pages": [
    {
      "url": "https://ejemplo.com/productos/123",
      "status_code": 200,
      "fetched_at": "2026-07-04T10:03:22Z",
      "data": { }
    }
  ]
}
```

**Problemas detectados en este formato:**
- No relaciona título ↔ contenido ↔ imágenes ↔ enlaces de una misma noticia.
- Campos de texto (`titulos_seccion[]`, `parrafos[]`) son arrays planos sin orden
  garantizado ni tipo de bloque (no se distingue título de subtítulo de párrafo de cita).
- No captura fecha de publicación real del artículo (solo `fetched_at` del crawler).
- No captura autor, categoría/sección, ni si el contenido está detrás de paywall.
- No captura imágenes, videos ni enlaces salientes de forma estructurada.
- Imposible auditar calidad de extracción (no hay score de confianza ni distinción
  entre artículos bien/mal parseados).

**Formato nuevo:** `scraper-schema.json` (JSON Schema Draft 2020-12), que define:
- `articles[]` como lista de artículos, cada uno **autocontenido**.
- `content_blocks[]` con `type` + `order` explícito para reconstruir el artículo
  exactamente en su orden de lectura real (heading, paragraph, quote, related_link, etc.).
- Bloques `media` (portada + imágenes inline + video + embeds) con posición referenciada
  a `content_blocks[].order`.
- Bloques `links.outbound_links[]` con anchor text y posición.
- `authorship`, `dates`, `taxonomy`, `access` (paywall), `seo_and_metadata` como objetos
  estructurados y tipados.
- `extraction_quality` a nivel de corrida completa (confidence score, artículos fallidos/parciales).

Archivo de referencia: `scraper-schema.json` (raíz del proyecto).

### Brechas adicionales identificadas (2026-07-04)

Además del cambio de formato de salida, se identificaron dos vacíos funcionales que
tampoco estaban cubiertos en la versión inicial del proyecto:

1. **Documentación de ejecución ausente** — el `README.md` no explica cómo instalar,
   configurar ni correr el scraper. Alguien nuevo en el proyecto no sabría cómo
   levantarlo desde cero.
2. **Sin búsqueda por intervalo de tiempo** — el scraper no soporta filtrar/buscar
   noticias dentro de un rango de fechas (`from` / `to`). Solo scrapea lo que
   encuentra en el momento de la corrida, sin acotar por fecha de publicación.

### Brecha adicional identificada (2026-07-05)

Al inspeccionar manualmente una noticia real de gestion.pe ("Agro de Perú en China: 3
apuestas que causan más 'ilusión'...") se detectó que el sitio incrusta **enlaces a
mitad de una oración**, dentro del cuerpo de un párrafo normal — no solo en cajas
separadas tipo "LEA TAMBIÉN". Ejemplo real observado:

> "Beijing, China.- <ins>Mientras nuevos productos agrícolas buscan abrirse paso hacia
> China, otros ya se han consolidado y concentran la mayor parte de los envíos del
> sector.</ins> Perú registra una lista de agroexportaciones..."

(la parte subrayada es un hyperlink hacia otro artículo, incrustado en medio del texto).

**Problema:** el `content_block` tipo `paragraph` solo tenía un campo `text` (string
plano). No existía forma de representar que una porción de ese string era, en
realidad, un enlace. El campo `related_link` no cubre este caso porque modela un
bloque **separado** (una caja tipo "LEA TAMBIÉN"), no un tramo **dentro** de un
párrafo ya existente. Resultado: al extraer esta noticia, el enlace se pierde por
completo — solo sobrevive el texto, sin el `href`.

### Bug detectado en producción (2026-07-05, corrida `gestion-20260705-041630`)

Al revisar una corrida real (`gestion_pe.json`, 3 artículos, filtrada con
`date_range_filter` 2026-07-01→2026-07-04) se encontró que **ninguno de los 3
artículos tiene su cuerpo real capturado**:

- Los 3 artículos (`estacionamiento-chocaron-tu-auto...`,
  `keiko-fujimori-tiene-mas-de-100...`, `trabajadores-de-confianza-corte-suprema...`)
  tienen `content_blocks[]` con **un único bloque idéntico** entre sí:
  `{"type":"heading","order":0,"text":"PLUS G Inversión china llega a Las Malvinas: de la importación a la compra de locales, ¿qué sigue?","level":2}`
- Los 3 tienen **0 bloques `paragraph`**.
- Los 3 comparten el mismo `outbound_links[0].url`
  (`.../las-malvinas-y-las-rutas-de-exportacion.../`), que apunta a un módulo de
  "recomendados" del sidebar, no a contenido propio del artículo.
- La propia `extraction_quality` del archivo ya lo advertía honestamente:
  `articles_fully_parsed: 0`, `articles_partial: 3`, `confidence_score: 0.0`.

**Diagnóstico:** el extractor de `content_blocks[]` está seleccionando el nodo DOM de
un widget global de "recomendados" (idéntico en todas las páginas del sitio) en vez
del contenedor real del cuerpo del artículo. La extracción a nivel de artículo
(`headline`, `dates.published_at`, `authorship`, `summary.excerpt`) sí funciona
correctamente — el bug está acotado al selector que arma `content_blocks[]` desde
el DOM.

**Consecuencia directa sobre el ítem de `runs[]` marcado `[x]` más abajo:** esa
validación se hizo con datos sintéticos (bloque de ejemplo construido a mano
reproduciendo el caso de "Agro de Perú en China"), no con una extracción real de
gestion.pe — porque, con este bug activo, **no existe todavía ninguna corrida real
con un solo bloque `paragraph` genuino** donde probarlo. El ítem no se revierte a
`[ ]`, pero queda anotado que su validación es sintética, no de producción, hasta
que este bug se corrija.

**Lo que sí funciona correctamente en esta misma corrida** (para no perder de vista
lo que va bien): `crawl_metadata.date_range_filter` presente y correcto
(`2026-07-01T00:00:00Z` → `2026-07-04T23:59:59Z`), `dates.published_at` en ISO 8601
real, `authorship.authors[]`, y `summary.excerpt` — los 4 se extrajeron bien a nivel
de artículo en las 3 noticias.

### Added
- [x] Definir e integrar `scraper-schema.json` como contrato de salida oficial del scraper.
      _(2026-07-04 — `storage/schema_validator.py`, comando `validate-output`; validado con Draft202012Validator, 0 errores en fixture de test)_
- [x] Migrar el parser/extractor para producir `articles[]` en vez de `pages[].data`.
      _(2026-07-04 — `parser/article_extractor.py` + `crawler/orchestrator.py`; 20 tests pytest OK)_
- [x] Implementar generación de `content_blocks[]` respetando orden real del DOM
      (mapeo de `<h2>`→`heading`, `<p>`→`paragraph`, `<blockquote>`→`quote`, etc.).
      _(2026-07-05 — `build_content_blocks()` + fix `_find_article_root()`; corrida
      `gestion-20260705-042902`: 29 y 23 párrafos distintos por artículo;
      test `test_find_article_root_ignores_sidebar_widget`)_
- [x] Implementar extracción de `links.outbound_links[]` (enlaces "Lea también", citas, etc.).
      _(2026-07-05 — `_extract_outbound_links()` acotado a `article_root`; enlaces del
      cuerpo real, no del widget "más leídos")_
- [x] Implementar `authorship.authors[]` (nombre + URL de perfil del autor).
      _(2026-07-06 — JSON-LD Person, perfiles `/autor/`, bylines "Por …";
      tests `test_authorship_taxonomy.py`)_
- [x] Implementar `dates.published_at` en ISO 8601 real (no solo timestamp de fetch).
      _(2026-07-04 — meta `article:published_time`, JSON-LD y `<time>`; confirmado
      además con datos reales el 2026-07-05: los 3 artículos de la corrida
      `gestion-20260705-041630` traen `published_at` ISO 8601 correcto)_
- [x] Implementar `access.is_paywalled` / `paywall_type` (detectar banners tipo
      "EXCLUSIVO PARA SUSCRIPTORES").
      _(2026-07-04 — heurística `PAYWALL_PATTERNS`)_
- [x] Implementar `article_id` determinístico (hash de dominio + slug + fecha) para
      deduplicar entre corridas.
      _(2026-07-04 — `generate_article_id()`; test determinístico)_
- [x] Implementar validación automática post-extracción contra `scraper-schema.json`
      usando `jsonschema` (Draft202012Validator) antes de persistir cualquier artículo.
      _(2026-07-05 — `validate_article()` en orchestrator; **bloquea persistencia** si
      hay errores de schema (`article_schema_rejected`); corrida solo persiste artículos
      válidos)_
- [x] Implementar `extraction_quality` a nivel de corrida (conteo de artículos
      completos/parciales/fallidos + `confidence_score`).
      _(2026-07-04 — `compute_extraction_quality()`; confirmado funcionando en
      producción el 2026-07-05: reportó honestamente `confidence_score: 0.0` en la
      corrida con el bug de `content_blocks[]`, permitiendo detectarlo)_
- [x] **Actualizar `README.md`**: reemplazar el ejemplo de output del formato viejo
      (`pages[].data`) por un ejemplo con el formato nuevo (`articles[].content_blocks[]`),
      agregar referencia a `scraper-schema.json` como contrato de datos oficial, y
      documentar cómo correr la validación (`jsonschema` contra el schema) como parte
      del flujo de uso del proyecto.
      _(2026-07-04 — README actualizado)_
- [x] **Documentar en `README.md` cómo ejecutar el scraper end-to-end**: instalación
      de dependencias, variables/archivo de configuración (dominio a scrapear, límites,
      credenciales si aplica), comando exacto de arranque, y un ejemplo de salida
      esperada en consola. Este apartado no existe actualmente en el README.
      _(2026-07-04 — sección "Uso rápido" en README)_
- [x] **Implementar búsqueda de noticias por intervalo de tiempo** (rango `from`/`to`):
      permitir acotar el scraping a noticias publicadas dentro de una fecha inicial y
      una fecha final. No soportado en la versión inicial del proyecto.
      _(2026-07-04 — CLI `--from-date`/`--to-date`, `date_range` en YAML,
      `article_in_date_range()`; confirmado funcionando en producción el 2026-07-05:
      `crawl_metadata.date_range_filter` presente y correcto en la corrida real)_
- [x] Agregar a `scraper-schema.json` el campo `crawl_metadata.date_range_filter`
      (objeto opcional `{ "from": "<date>", "to": "<date>" }`) para dejar registro de
      qué rango de fechas se usó en cada corrida y poder auditar/reproducir resultados.
      _(2026-07-04 — campo en schema + `write_final()`; confirmado en producción 2026-07-05)_
- [x] **Documentar en `README.md` el uso del filtro de intervalo de tiempo**: sintaxis
      de los parámetros/flags, formato de fecha aceptado, y ejemplos de comandos
      (ej. scrapear "última semana", "mes específico", "rango exacto").
      _(2026-07-04 — README, ejemplos PowerShell)_
- [x] **Agregar a `scraper-schema.json` la definición `text_run` y el campo opcional
      `runs[]`** en los bloques `paragraph` y `list_item`, para representar texto
      enriquecido (tramos `text` / `link`) y así preservar enlaces incrustados a
      mitad de una oración, en vez de perderlos al aplanar el bloque a `text` plano.
      Campo **opcional y aditivo** — no rompe compatibilidad con `content_blocks[]`
      ya emitidos sin `runs`.
      _(2026-07-05 — `scraper-schema.json`, `$defs.text_run` + `content_block.allOf`
      para `paragraph`/`list_item`; validado con Draft202012Validator: (1) el schema
      compila correctamente, (2) una instancia previa sin `runs` sigue validando sin
      errores — confirma que no es breaking change, (3) un bloque `paragraph` con
      `runs[]` reconstruyendo el ejemplo real de gestion.pe ["Agro de Perú en China"]
      valida correctamente, (4) un `run` tipo `link` sin `url` es rechazado
      correctamente por la validación condicional)_
- [x] Implementar en el extractor real la generación de `runs[]` a partir del DOM:
      recorrer los nodos hijos de cada `<p>`/`<li>` y, cuando se encuentre un `<a>`,
      emitir un run `{ "kind": "link", "text": ..., "url": ... }`; el resto del
      contenido textual del nodo se emite como runs `{ "kind": "text", ... }`.
      Debe garantizarse que la concatenación de `runs[].text` sea idéntica al `text`
      plano ya generado (mismo bloque, misma fuente). — campo/módulo afectado:
      `content_blocks[].runs[]` en `parser/article_extractor.py`.
      _(2026-07-05 — `_build_text_runs()`; test `test_paragraph_runs_inline_link`;
      confirmado en producción tras fix de contenedor: 1+ párrafos con `runs[]` en artículo
      real de gestion.pe; 22 pytest OK)_

### Changed
- [x] Reemplazar `pages[].data.titulos_seccion[]` y `pages[].data.parrafos[]`
      (arrays planos sin relación) por `articles[].content_blocks[]` (bloques
      tipados y ordenados). **Breaking change** — no hay compatibilidad hacia atrás.
      _(2026-07-04 — `JsonWriter` reescrito; `output/gestion_pe.json` legacy pendiente de regenerar)_
- [x] Reemplazar `total_records_extracted` (métrica ambigua) por
      `crawl_metadata.total_articles_extracted` + `extraction_quality.*`.
      _(2026-07-04 — métricas en `crawl_metadata` y `extraction_quality`)_

### Deprecated
- [x] Formato original (`pages[].data` con arrays planos) — **deprecado formalmente
      a partir de esta entrada.** No recibirá nuevos campos ni correcciones.
      _(2026-07-04 — decisión tomada en esta sesión, ver contexto arriba)_

### Removed
- Ninguno todavía. El formato viejo se remueve del código solo cuando todos los
  ítems de `Added`/`Changed` de esta entrada estén en `[x]`.

### Fixed
- [x] **Bug: `content_blocks[]` captura un widget de sidebar repetido en vez del
      cuerpo real del artículo.** Reproducido con evidencia concreta: 3 artículos
      distintos de una misma corrida (`gestion-20260705-041630`) devuelven el mismo
      bloque exacto (`"PLUS G Inversión china llega a Las Malvinas..."`) y comparten
      el mismo `outbound_links[0].url`, en vez de su propio cuerpo. Causa raíz
      probable: el selector CSS/XPath usado para ubicar el contenedor del artículo
      coincide también (o coincide únicamente) con un módulo de recomendados que
      existe idéntico en todas las páginas de gestion.pe. — campo/módulo afectado:
      `content_blocks[]` en `parser/article_extractor.py` (selector del contenedor
      principal del artículo). Archivo de evidencia: `gestion_pe.json`
      (`crawl_id: gestion-20260705-041630`).
      _(2026-07-05 — `_find_article_root()` prioriza `.story-contents` y puntúa
      candidatos; `_in_excluded_region()` limita exclusión al contenedor elegido;
      test `test_find_article_root_ignores_sidebar_widget`; URL real: 29 párrafos,
      sin texto "Malvinas")_

### Fixed
- [x] **Extracción incompleta de texto en `content_blocks[]` (gestion.pe).** Los bloques
      se guardan párrafo a párrafo (correcto según schema), pero faltaban piezas visibles
      en el artículo: bajada bajo el titular (`headline.subtitle` solo en metadatos),
      enlaces bajo el titular (`ul.sht__list`), bloques "LEA TAMBIÉN" sin `url` (tipo
      `quote` en vez de `related_link`), captions de foto en `<div>` sin `<p>`, y bio
      del autor mezclada como párrafo final. — módulo: `parser/article_extractor.py`.
      _(2026-07-05 — deck en bloque 0, `.sht__list`→`related_link`, LEA TAMBIÉN con url,
      `image_caption`, exclusión `about-author`/copy-blocker/link-list; Agro: 23 bloques,
      28 pytest OK)_

### Documentación / semántica
- [x] **Aclarar semántica del filtro de fechas: intervalo continuo inclusivo, no dos
      fechas aisladas.** El filtro `--from-date` / `--to-date` (y `date_range` en YAML)
      define un tramo `from <= published_at <= to`; no son dos fechas independientes ni
      una unión de días sueltos. La comparación usa UTC. Caso documentado: noticia
      "Agro de Perú en China" (04/07/2026 20:48 Lima = 05/07/2026 01:48 UTC) excluida
      con `--to-date 2026-07-04T23:59:59Z` — comportamiento correcto del intervalo,
      no un bug. — módulo: `article_in_date_range()` en `parser/article_extractor.py`.
      _(2026-07-05 — README actualizado + tests `test_date_range.py`; 4 casos pytest)_

### Security
- N/A.

### README
- [x] Documentar en `README.md` el campo `runs[]` (texto enriquecido) con un ejemplo
      antes/después usando el caso real de "Agro de Perú en China": mostrar cómo un
      párrafo con un enlace incrustado a mitad de oración se representa con
      `kind: "text"` / `kind: "link"`, y aclarar que es opcional y no reemplaza a
      `text`.
      _(2026-07-05 — sección "Texto enriquecido (runs[])" en README)_
- [x] Agregar nota en README junto al ejemplo de `runs[]` aclarando que, a la fecha,
      esa validación es sintética (no de producción) por el bug de `content_blocks[]`
      documentado arriba — para no dar a entender que cualquier corrida real de
      gestion.pe ya devuelve `runs[]` poblado.
      _(2026-07-05 — nota bajo sección runs[]; bug corregido, runs confirmado en producción)_

### Added (2026-07-05 — nueva tanda)
- [x] **Ajuste `runs[]`:** si un `<p>` entero es un solo `<a>` (recirculación tipo gestion.pe),
      omitir `runs[]` y dejar solo `text` — evita marcar todo el párrafo como un único
      `kind: "link"` cuando el contenido ya está en `text`. — módulo:
      `parser/article_extractor.py` (`_build_text_runs()`).
      _(2026-07-05 — test `test_whole_paragraph_link_omits_runs`; 31 pytest OK)_
- [x] **Export HTML legible** desde `gestion_pe.json` (y cualquier salida del schema):
      generar `output/<nombre>.html` junto al JSON para revisar artículos en navegador
      (titular, bajada, bloques, enlaces, imágenes). — módulo: `storage/html_writer.py`,
      comando CLI `export-html`.
      _(2026-07-05 — `output/gestion_pe.html` generado; tests `test_html_writer.py`)_
- [x] **Scraping multi-sitio (medios peruanos):** run-all-final **10/10 sitios**,
      **144 artículos** totales, JSON+HTML en `output/`.
      _(2026-07-05 — log `output/run-all-final.log`)_
- [x] **Comando `run-all` — crawl batch de todos los medios:** una sola ejecución
      (`scraper-agent run-all`) recorre el manifiesto completo sin invocar sitio por sitio.
      Por cada dominio genera automáticamente su par `output/<sitio>.json` +
      `output/<sitio>.html`. — módulos: `crawler/batch_runner.py`, CLI `run-all`.
      _(2026-07-05 — corrida real: 10 JSON + 10 HTML en `output/`; log en
      `output/run-all.log`; schema OK en los 10)_

### README
- [x] Documentar comando `export-html` y tabla de configs en `config/sites/`.
      _(2026-07-05 — README sección multi-sitio y export HTML)_
- [x] Documentar `scraper-agent run-all` como forma principal de scrapear todos los
      medios de una vez (referencia al manifiesto `config/sites/sites.yaml`, sin listar
      dominios en el CHANGELOG).
      _(2026-07-05 — README sección "Crawl de todos los medios de una vez")_

### Added (2026-07-05 — descubrimiento RSS + articleBody)
- [x] **Modo de descubrimiento `discovery` en configs YAML:** `mode: crawl | rss | both`,
      lista `rss_feeds[]` y `max_items_per_feed`. En `rss`/`both` el orquestador siembra
      la cola con URLs de noticias desde feeds RSS/Atom (sin depender del BFS por secciones).
      — módulos: `models/schemas.py` (`DiscoveryConfig`), `parser/rss_feed.py`,
      `crawler/orchestrator.py`, `crawler/url_frontier.py`.
      _(2026-07-05 — feed Arc gestion.pe OK; 7 artículos vs 1 sin RSS; `test_rss_feed.py`)_
- [x] **Fallback `articleBody` (JSON-LD) para `content_blocks[]`:** si el DOM no produce
      párrafos sustantivos, usar `articleBody` de `NewsArticle`/`Article` en
      `<script type="application/ld+json">` (patrón Grupo El Comercio / Arc Publishing).
      — módulo: `parser/article_extractor.py` (`blocks_from_article_body()`).
      _(2026-07-05 — test `test_extract_article_falls_back_to_jsonld_article_body`; 36 pytest OK)_

### Added (2026-07-05 — anti-bot / HTTP 403)
- [x] **Mejoras anti-detección para sitios con bloqueo 403** (peru21.pe, expreso.com.pe):
      UA fijo por sesión, `Sec-CH-UA` / `Sec-Fetch-*`, warmup de cookies en la home,
      reintentos con backoff ante 403, fallback automático a **Playwright** cuando
      `anti_detection.use_playwright_on_403: true`. — módulos: `fetcher/headers.py`,
      `anti_detection/fingerprint.py`, `fetcher/http_client.py`, `renderer/playwright_renderer.py`,
      `crawler/orchestrator.py`.
      _(2026-07-05 — peru21.pe: 0→16 artículos; requiere `playwright install chromium`)_
- [x] **Normalización de feeds RSS envueltos en HTML** (`<pre>` con XML escapado) tras
      fallback Playwright — módulo: `parser/rss_feed.py` (`normalize_feed_xml()`).
      _(2026-07-05 — test `test_parse_rss_wrapped_in_html_pre`)_

### Fixed / pendientes (2026-07-05 — run-all 4 sitios en 0)
- [x] **elperuano.pe — sitemaps anidados:** el crawler visitaba XML de sitemap como
      páginas sin extraer `<loc>` de noticias; ahora `_expand_sitemaps()` y detección
      `is_sitemap_document()` encolan URLs `/noticia/…`. — módulos: `link_extractor.py`,
      `orchestrator.py`, config `elperuano_pe.yaml`.
      _(2026-07-05 — run-all-v2: **25 artículos**)_
- [x] **Expansión recursiva de sitemaps** (`_expand_sitemaps`) y `discovery.sitemap_urls[]`
      para índices WordPress / diarios oficiales. — `orchestrator.py`, `schemas.py`.
      _(2026-07-05 — elperuano validado)_
- [x] **Cola con prioridad** (`enqueue_priority`) para URLs de feeds RSS antes del BFS.
      — `url_frontier.py`.
      _(2026-07-05 — libero RSS encola tras max_depth fix)_
- [x] **libero.pe — cola BFS consumía secciones:** `max_depth: 2` bloqueaba URLs
      `/seccion/2026/07/04/slug`; modo `rss` + `max_depth: 8` + `enqueue_priority()`.
      — config `libero_pe.yaml`.
      _(2026-07-05 — **25 artículos** con `--to-date 2026-07-06T04:59:59Z`)_
- [x] **elchino.pe — sitemap / feed:** `Accept-Encoding: br` devolvía XML corrupto;
      descubrimiento vía `post-sitemap.xml` (1001 URLs). Feed `/feed/` inválido (XML roto).
      — `fetcher/headers.py`, config `elchino_pe.yaml`.
      _(2026-07-05 — **2 artículos** en corrida piloto; sitemap OK)_
- [x] **expreso.com.pe — Cloudflare:** browser nuevo por artículo (`fresh_browser` +
      `_reset_renderer`); home seed cierra sesión antes del crawl. **25 artículos**
      en run-all-final. — `orchestrator.py`, `expreso_com_pe.yaml`.
      _(2026-07-05 — `output/run-all-final.log`; validado)_
- [x] **trome.com — filtro de fechas UTC:** `to: 2026-07-06T04:59:59Z` + `mode: rss`
      + `max_depth: 8`. — config `trome_com.yaml`.
      _(2026-07-05 — piloto: **24 artículos** en `output/trome_com.json`)_
- [x] **Decodificación HTTP:** quitar `br` de `Accept-Encoding` — sitemaps WordPress
      (elchino `post-sitemap.xml`) llegaban como bytes inválidos. — `fetcher/headers.py`.
      _(2026-07-05 — elchino `post-sitemap.xml`; 1001 URLs parseables tras fix)_

### Added (2026-07-05 — Playwright preferido / Cloudflare)
- [x] **`anti_detection.prefer_playwright` + `_reset_renderer()`:** browser fresco
      por artículo en sitios CF; `render_persistent` solo para home seed.
      _(2026-07-05 — expreso 12/12 páginas OK)_
- [x] **`discovery.article_link_pattern` + `expand_sitemaps`:** siembra desde home
      Playwright para sitios con feed/sitemap bloqueados.
      _(2026-07-05 — expreso encola 25 URLs `-noticia`)_

### README
- [x] Documentar `prefer_playwright`, `article_link_pattern`, `expand_sitemaps` y nota
      expreso/Cloudflare — sección anti-bot / discovery.
      _(2026-07-06 — README con tablas y expreso.com.pe)_
- [x] Documentar `discovery.sitemap_urls[]` y modo `rss` para evitar crawl de menús.
      _(2026-07-05 — README sección discovery ampliada)_

---

### Added (2026-07-06 — buscador por objetivo profesional)

> **Contexto:** hasta ahora el scraper extrae todo el contenido disponible dentro del
> rango de fechas declarado, sin discriminar por relevancia temática. Esta tanda agrega
> un modo de operación orientado a **objetivo**: el usuario declara qué está buscando
> (términos, patrones, campos de interés) y el motor retiene, puntúa y ordena solo lo
> que coincide. El pipeline de extracción existente no cambia — se agrega una capa de
> filtrado + scoring **posterior** a la extracción, reutilizando `articles[]` y
> `content_blocks[]` ya producidos.

- [x] **`SearchTarget` — modelo de objetivo de búsqueda profesional.**
      Objeto que encapsula lo que el usuario quiere encontrar en una corrida:
      - `label` (string) — nombre legible del objetivo, aparece en logs y en el HTML
        de resultados (ej. `"Licitaciones construcción 2026-07"`).
      - `keywords[]` — términos que deben aparecer (coincidencia OR por defecto;
        `require_all: true` para AND estricto).
      - `exclude_keywords[]` — términos que descartan el artículo si aparecen.
      - `patterns[]` — expresiones regulares opcionales para casos avanzados
        (códigos de licitación, montos, RUC, etc.).
      - `match_in[]` — campos a inspeccionar: `headline`, `excerpt`,
        `content_blocks`, `outbound_links`, `authors`; por defecto todos.
      - `min_score` (float 0.0–1.0, default `0.3`) — umbral mínimo para incluir
        un artículo en `search_results[]`.
      - `date_range` — reutiliza `DateRangeFilter` existente; opcional, independiente
        del `--from-date`/`--to-date` global de la corrida.
      — módulo nuevo: `models/search_target.py`; integrado en `scraper-schema.json`
      como objeto opcional `crawl_metadata.search_target`.
      _(2026-07-06 — `SearchTarget` Pydantic + `load_search_target()`; 11 tests pytest)_

- [x] **Formato YAML de objetivo reutilizable (`config/targets/<nombre>.yaml`).**
      Permite guardar, versionar y reutilizar objetivos complejos entre corridas sin
      repetir flags en CLI. Estructura mínima validada:
      ```yaml
      label: "Licitaciones de construcción — Perú julio 2026"
      keywords:
        - licitación
        - concurso público
        - buena pro
        - OSCE
      exclude_keywords:
        - deportes
        - farándula
      patterns:
        - '\bN°\s*\d{3,6}-\d{4}\b'    # código de licitación OSCE
        - '\bS/\.\s*[\d,]+\b'          # monto en soles
      match_in:
        - headline
        - excerpt
        - content_blocks
        - outbound_links
      min_score: 0.4
      require_all: false
      date_range:
        from: "2026-07-01"
        to: "2026-07-06"
      ```
      — directorio: `config/targets/`; cargado con `--target-file <path>` en CLI.
      _(2026-07-06 — ejemplo `config/targets/licitaciones.yaml`)_

- [x] **Motor de coincidencias (`search/query_engine.py`) — 4 matchers combinables.**
      Cada matcher opera de forma independiente sobre los campos declarados en
      `SearchTarget.match_in[]` y devuelve una lista de `MatchResult`
      (`field`, `matched_term`, `snippet`):
      1. **Text matcher** — busca `keywords[]` en texto plano; normaliza tildes y
         mayúsculas; soporta coincidencia exacta o parcial por token.
      2. **Date matcher** — filtra por `SearchTarget.date_range` reutilizando
         `article_in_date_range()` existente; no duplica lógica.
      3. **Link matcher** — busca `keywords[]` y `patterns[]` en
         `outbound_links[].anchor_text` y `outbound_links[].url`; útil para rastrear
         dominios, secciones o slugs específicos enlazados desde el cuerpo.
      4. **Pattern matcher** — aplica `SearchTarget.patterns[]` (regex) sobre los
         mismos campos que Text matcher; emite el fragmento que captura el grupo
         (o el match completo si no hay grupo).
      Resultado combinado: `List[MatchResult]` por artículo, deduplicado por
      `(field, matched_term)`.
      _(2026-07-06 — `search/matchers.py` + `search/query_engine.py`; text/date/link/pattern)_

- [x] **Scorer de relevancia (`search/scorer.py`) — `score` por artículo.**
      Calcula un float 0.0–1.0 por artículo a partir de los `MatchResult[]`:
      - Peso por campo: `headline` ×3, `excerpt` ×2, `content_blocks` ×1,
        `outbound_links` ×0.5.
      - Frecuencia: repeticiones del mismo término en el mismo campo suman con
        rendimiento decreciente (log-scale) para no inflar artículos repetitivos.
      - Penalización por `exclude_keywords`: si aparece alguno, score → 0.0
        y el artículo se descarta antes de comparar con `min_score`.
      - Normalización final al rango 0.0–1.0 relativa al score máximo de la corrida
        (para que `min_score: 0.4` sea siempre interpretable como "top 60%").
      — módulo: `search/scorer.py`.
      _(2026-07-06 — pesos por campo, exclude_keywords, normalización relativa)_

- [x] **Campo `search_results[]` en el JSON de salida.**
      Cuando se usa el modo `targeted-search`, el JSON de corrida incluye una sección
      `search_results[]` paralela a `articles[]`, ordenada por `score` descendente.
      Cada entrada:
      ```json
      {
        "article_id": "<hash>",
        "score": 0.87,
        "matched_fields": ["headline", "content_blocks"],
        "matched_terms": ["licitación", "buena pro"],
        "matched_snippets": [
          {
            "field": "headline",
            "text": "Gobierno convoca [[licitación]] para obra vial en Cusco"
          },
          {
            "field": "content_blocks",
            "text": "El proceso de [[buena pro]] se realizará el 15 de julio"
          }
        ]
      }
      ```
      Los fragmentos coincidentes se marcan con `[[…]]` — sin HTML, para que sean
      procesables desde cualquier consumidor del JSON.
      — schema: `scraper-schema.json` (`$defs.search_result`,
      campo `search_results[]` en root); módulo: `search/query_engine.py`.
      _(2026-07-06 — snippets con marcadores `[[…]]`; validado con Draft202012Validator)_

- [x] **CLI `scraper-agent search` — comando de entrada para búsqueda por objetivo.**
      Acepta objetivo inline (flags) o desde archivo YAML (`--target-file`):
      ```
      # Objetivo inline
      scraper-agent search \
        --url https://gestion.pe \
        --keywords "licitación,concurso público,buena pro" \
        --exclude "deportes,espectáculos" \
        --from-date 2026-07-01 --to-date 2026-07-06 \
        --min-score 0.4 \
        --match-in headline,content_blocks,outbound_links \
        --out output/busqueda_licitaciones.json

      # Objetivo desde archivo (reutilizable)
      scraper-agent search \
        --url https://gestion.pe \
        --target-file config/targets/licitaciones.yaml \
        --out output/busqueda_licitaciones.json
      ```
      Genera `output/<nombre>.json` + `output/<nombre>.html` automáticamente.
      — módulo: `cli.py`.
      _(2026-07-06 — flags inline + `--target-file`; auto-detecta config por dominio)_

- [x] **`run-all` + `--target-file` — búsqueda por objetivo en todos los sitios.**
      Aplica el mismo `SearchTarget` a todos los dominios del manifiesto en una sola
      ejecución. Genera JSON+HTML por sitio (igual que `run-all` actual) más un
      archivo consolidado `output/busqueda_<label>.json` con todos los
      `search_results[]` de todos los sitios, ordenados globalmente por `score`.
      — módulo: `crawler/batch_runner.py` + `search/persist.py`.
      _(2026-07-06 — consolidado `output/busqueda_<label>.json`)_

- [x] **Export HTML de resultados de búsqueda (extensión de `html_writer.py`).**
      Cuando el JSON tiene `search_results[]`, el HTML generado incluye:
      - Tabla resumen al inicio: columnas `score`, `titular`, `fecha`, `sitio`,
        `términos coincidentes` — ordenada por score descendente.
      - Detalle de cada artículo coincidente con los snippets resaltados:
        los marcadores `[[…]]` se convierten en `<mark>…</mark>` para resaltar
        visualmente los términos en el navegador.
      - Artículos sin coincidencia (`score < min_score`) se omiten del HTML de
        resultados (siguen presentes en `articles[]` del JSON completo).
      — módulo: `storage/html_writer.py` (extensión del writer existente,
      sin breaking change para HTMLs sin `search_results[]`.
      _(2026-07-06 — tabla resumen + `<mark>` en snippets)_

- [x] **Agregar `search_result` y `search_target` a `scraper-schema.json`.**
      - `$defs.search_result` — objeto con `article_id`, `score`, `matched_fields[]`,
        `matched_terms[]`, `matched_snippets[]` (cada snippet: `field` + `text`).
      - `$defs.search_target` — reflejo del modelo `SearchTarget` para que quede
        registrado en `crawl_metadata.search_target` de cada corrida y sea auditable.
      - `search_results[]` como array opcional en root (igual que `articles[]`).
      Cambio **aditivo** — no rompe corridas existentes sin `search_results[]`.
      — módulo: `scraper-schema.json`; validar con Draft202012Validator tras el cambio.
      _(2026-07-06 — cambio aditivo; 53 pytest OK)_

### README
- [x] Documentar comando `scraper-agent search`, flags disponibles y diferencia entre
      objetivo inline vs `--target-file` — sección nueva "Búsqueda por objetivo
      profesional".
      _(2026-07-06 — README sección "Búsqueda por objetivo profesional")_
- [x] Agregar tabla de campos de `SearchTarget` con tipo, default y descripción.
      _(2026-07-06 — README)_
- [x] Documentar los 4 tipos de matcher (text, date, link, pattern) con un ejemplo
      de caso de uso real por cada uno.
      _(2026-07-06 — README)_
- [x] Documentar formato de `search_results[]` en el JSON de salida y convención
      de marcadores `[[…]]` en `matched_snippets[].text`.
      _(2026-07-06 — README)_
- [x] Agregar ejemplos de objetivos profesionales listos para copiar (con comandos
      PowerShell): licitaciones públicas, convocatorias de empleo, precios de
      commodities, sentencias judiciales, decretos supremos.
      _(2026-07-06 — README, ejemplo licitaciones)_
- [x] Documentar cómo usar `run-all --target-file` para búsqueda cruzada sobre
      todos los medios y el archivo consolidado que genera.
      _(2026-07-06 — README)_

### Added (2026-07-06 — authorship y taxonomy)

- [x] **`_extract_authors()` enriquecido:** JSON-LD `Person`, enlaces `/autor/`,
      selectores Arc (`.story-body-author__name`), bylines "Por …" sin enlace.
      — módulo: `parser/article_extractor.py`; tests: `tests/test_authorship_taxonomy.py`.
- [x] **`_extract_taxonomy()` dedicado:** `primary_category`, `secondary_categories`
      (breadcrumbs), `tags` (`article:tag`, keywords, enlaces `/tag/`), `related_topics`
      (JSON-LD `about`). — mismo módulo; integrado en `extract_article()`.
- [x] **Búsqueda por `taxonomy`:** campo `match_in: taxonomy` en `SearchTarget` y
      peso ×1.5 en scorer. — módulos: `search/matchers.py`, `models/search_target.py`,
      `scraper-schema.json` (`$defs.search_target.match_in`).

### Added (2026-07-06 — JSONL incremental)

- [x] **Sidecar `articles.jsonl` en checkpoint:** cada artículo validado se persiste
      al instante en `output/checkpoints/<sitio>/articles.jsonl` (una línea JSON por
      artículo). — módulo: `storage/json_writer.py`; flag `output.incremental` (default
      `true`) en `config/config.yaml` y `OutputConfig`.
- [x] **Reanudación con artículos recuperados:** al reiniciar un crawl, `JsonWriter`
      recarga el JSONL existente y deduplica por `article_id` antes de seguir extrayendo.
      — integrado en `crawler/orchestrator.py`.
- [x] **Tests:** `tests/test_storage.py` (escritura sidecar, reload, dedupe, opt-out).
      _(2026-07-06 — 65 pytest OK en suite completa)_

---

### Added (2026-07-06 — cierre legacy v1.0)

- [x] **Eliminación de modelos legacy:** `PageRecord`, `CrawlResult`, `CrawlMetrics` y
      formato `pages[].data` / `total_records_extracted` removidos de `models/schemas.py`.
- [x] **`CONTRIBUTING.md`:** guía para añadir medios, targets de búsqueda, cambios al
      schema y checklist de PR.
- [x] **Tests** `tests/test_legacy_removed.py` — evita reintroducir tipos legacy.
- [x] **`AGENTS.md` v1.1:** ejemplo de salida alineado a `scraper-schema.json`.

---

- [x] **GitHub Actions** `.github/workflows/ci.yml`: matrix Python 3.11/3.12, `ruff check`,
      `pytest tests/`.
- [x] **Fixtures** `tests/fixtures/`: `crawl_minimal.json`, `crawl_with_search.json`,
      `consolidated_search.json` validados contra `scraper-schema.json`.
- [x] **Tests** `tests/test_schema_fixtures.py`: parametrizado por fixture + meta-validación
      del schema Draft 2020-12.
- [x] **README:** sección CI y reproducción local.

---

- [x] **`docs/troubleshooting-por-dominio.md`:** guía síntoma → causa → fix por cada uno
      de los 10 medios del manifiesto + checks globales (UTC, CF, selectores, JSONL).
- [x] **Objetivos en `config/targets/`:** `empleo.yaml`, `commodities.yaml`,
      `sentencias.yaml`, `decretos.yaml` (además de `licitaciones.yaml`).
- [x] **Test:** `test_all_predefined_targets_load` valida que todos los YAML cargan.
- [x] **README:** tabla de targets, ejemplos `search --input`, enlace a troubleshooting.

---

- [x] **`scraper-agent search --input`:** búsqueda sobre `output/*.json` sin re-crawlear;
      soporta `--out` para no sobrescribir el archivo fuente. — módulos: `cli.py`,
      `search/persist.py`; tests: `test_search_from_existing_json_*`.
- [x] **README anti-bot / discovery:** tablas y ejemplos para `prefer_playwright`,
      `article_link_pattern`, `expand_sitemaps`, síntomas Cloudflare/403 y referencia
      `config/sites/expreso_com_pe.yaml`. — `README.md`.

---

### Added (2026-07-06 — entorno Kali Linux + agente de seguridad/scraping vía chat)

> **Contexto:** hasta ahora el scraping corre en el entorno del propio proyecto
> (httpx/Playwright), sin un entorno de herramientas de seguridad dedicado. Esta
> entrada registra el pedido de: (1) un entorno **Kali Linux** (contenedor Docker)
> con su suite completa de herramientas, usable tanto para **scraping avanzado**
> como para **testing de seguridad**; (2) un **agente basado en LLM** que interpreta
> instrucciones en lenguaje natural del usuario y las traduce en operaciones
> ejecutadas dentro de ese entorno Kali; (3) todo expuesto detrás de **un único
> endpoint** de chat con **streaming** (una sola interfaz de entrada/salida para
> todo el sistema, no un panel con múltiples rutas). Ninguno de los ítems de abajo
> está implementado — quedan como pendientes (`[ ]`) hasta tener diseño y
> aprobación explícita de alcance.

- [~] **Contenedor Kali Linux como entorno de herramientas.** Imagen base
      `kalilinux/kali-rolling` (o `kali-last-release`) con el paquete de
      herramientas necesario instalado (`kali-linux-headless` como mínimo),
      aislado del resto del sistema (red y filesystem acotados), accesible
      solo desde el backend del proyecto — nunca expuesto directamente a
      internet. — módulo nuevo: `security_env/kali_runtime.py` (wrapper que
      levanta/gestiona el contenedor) + `docker/kali/Dockerfile`.
      _(2026-07-06 — Dockerfile + compose; exec vía docker.sock)_

- [x] **Capa de ejecución controlada (`security_env/tool_runner.py`).**
      El agente **no** debe tener acceso a una shell arbitraria dentro de Kali.
      Necesita una capa intermedia que exponga un **catálogo cerrado de
      comandos/herramientas permitidas** (allowlist explícita, no free-form
      bash), con:
      - parámetros validados y tipados por herramienta (no interpolación
        directa de texto del usuario en el comando),
      - timeout y límites de recursos por ejecución,
      - registro (log) de cada comando ejecutado, con quién lo pidió,
        contra qué objetivo y el resultado — auditable después.
      — módulo: `security_env/tool_runner.py`, `security_env/tool_catalog.yaml`.
      _(2026-07-06)_

- [x] **Verificación de autorización de objetivo antes de ejecutar.**
      Antes de correr cualquier herramienta de testing de seguridad (no de
      scraping) contra un dominio/IP, el sistema debe exigir que ese objetivo
      esté en una lista de "activos autorizados" declarada explícitamente por
      el usuario/operador del sistema (ej. `config/authorized_targets.yaml`,
      con dominio + evidencia de autorización). Si el objetivo no está en la
      lista, el agente **rechaza** la instrucción y lo informa, sin ejecutar
      nada. Esto extiende el principio ya declarado en `AGENTS.md` §9 ("uso
      autorizado") a la nueva capa de testing de seguridad. — módulo:
      `security_env/authorization_guard.py`.
      _(2026-07-06)_

- [x] **Agente LLM orquestador (`agent/security_scraping_agent.py`).**
      Recibe instrucciones en lenguaje natural ("scrapea todas las noticias de
      X sobre Y", "revisa qué puertos/servicios expone el dominio autorizado Z"),
      las interpreta y las traduce a llamadas contra:
      (a) el pipeline de scraping ya existente (`crawler/`, `parser/`, `search/`)
          para tareas de extracción de contenido, y
      (b) el catálogo de herramientas de Kali vía `tool_runner.py` para tareas
          de testing de seguridad — siempre pasando primero por
          `authorization_guard.py`.
      El agente debe poder encadenar pasos (plan → ejecutar → resumir) y
      explicar en lenguaje natural qué hizo y por qué antes de mostrar
      resultados crudos. — módulo nuevo: `agent/security_scraping_agent.py`.
      _(2026-07-06 — loop tool_calls + `tool_handlers.py` + `session_log.py`)_

- [x] **Endpoint único de chat con streaming (`api/chat_endpoint.py`).**
      Una sola ruta (`POST /chat` o WebSocket `/ws/chat`) como interfaz completa
      del sistema: el usuario escribe la instrucción, la respuesta se transmite
      en streaming (tokens del LLM + eventos intermedios tipo "ejecutando
      nmap contra X", "artículo 3/16 extraído") hasta el resultado final.
      No se exponen endpoints separados por herramienta — todo pasa por el
      agente orquestador de arriba. — módulo: `api/chat_endpoint.py`
      (FastAPI + `StreamingResponse` o WebSocket).
      _(2026-07-06 — POST /chat SSE; `scraper-agent serve`; GET /health)_

- [x] **Logging y trazabilidad de sesión completa.** Cada sesión de chat debe
      quedar registrada con: instrucción original del usuario, plan generado
      por el agente, comandos ejecutados (scraping y/o Kali), objetivos
      involucrados, y resultado — para poder auditar después qué hizo el
      agente y con qué autorización. — módulo: `storage/session_log.py`.
      _(2026-07-06 — JSONL en output/sessions/<session_id>.jsonl)_

### Seguridad
- [x] **Delimitar explícitamente el alcance de "testing de seguridad" permitido.**
      Definir, antes de implementar el catálogo de `tool_runner.py`, qué
      categorías de herramientas Kali se habilitan (ej. reconocimiento pasivo,
      escaneo de puertos, análisis de headers/TLS) y cuáles quedan **fuera** de
      alcance por defecto (explotación activa, fuerza bruta de credenciales,
      denegación de servicio), siguiendo el mismo criterio ético que
      `AGENTS.md` §9 ya aplica al scraping (uso autorizado, sin bypass de
      seguridad de terceros). Esta definición debe quedar en un documento propio
      (`docs/alcance-seguridad.md`) antes de escribir código del `tool_runner.py`.
      _(2026-07-06 — `docs/alcance-seguridad.md` v1.0 + `config/authorized_targets.yaml.example`)_

### Added (2026-07-06 — security_env 10a-c)

- [x] **`src/scraper_agent/security_env/`:** `authorization_guard.py`, `tool_runner.py`,
      `kali_runtime.py`, `tool_catalog.yaml`, `settings.yaml`, `param_validation.py`.
- [x] **Tests:** `test_authorization_guard.py` (9), `test_tool_runner.py` (8),
      `test_kali_runtime.py` (5); fixture `authorized_targets_test.yaml`.
      _(2026-07-06 — 97 pytest OK en suite completa)_


- [x] **`docs/alcance-seguridad.md`:** categorías permitidas/prohibidas, modelo de
      autorización, límites de ejecución, checklist pre-código y relación con
      `AGENTS.md` §9.
- [x] **`config/authorized_targets.yaml.example`:** plantilla de activos autorizados
      con evidencia, expiración y categorías permitidas.
- [x] **README:** sección "Agente de seguridad" con módulos `security_env/`.
      _(2026-07-06 — actualizado tras implementación 10a-c)_

### README
- [ ] Documentar el entorno Kali Linux, el catálogo de herramientas habilitado,
      el mecanismo de autorización de objetivos y el endpoint único de chat —
      sección nueva "Agente de seguridad y scraping (Kali Linux)".
      — o —
      README: no aplica — aún no implementado, se documenta cuando exista código.

### Added (2026-07-06 — LLM DeepSeek + despliegue único en docker-compose, puerto 1212)

> **Contexto:** se define el modelo concreto que interpretará las instrucciones
> del agente (`agent/security_scraping_agent.py`, entrada de más arriba) y se fija
> cómo se despliega **todo** el sistema (scraper + entorno Kali + agente + endpoint
> de chat) como una sola pila (`docker-compose`), expuesta al usuario en **un solo
> puerto externo: 1212**.

- [x] **Adoptar DeepSeek como LLM del agente orquestador.** El `agent/security_scraping_agent.py`
      (ítem pendiente de la entrada anterior) usará la API de DeepSeek (compatible
      con el formato de `chat/completions` estilo OpenAI) en vez de otro proveedor.
      Definir explícitamente: endpoint de la API, modelo exacto (`deepseek-chat` /
      `deepseek-reasoner`, a confirmar según necesidad de function-calling/tool-use
      para invocar `tool_runner.py` y el pipeline de scraping), y manejo de la
      API key vía `.env` (`DEEPSEEK_API_KEY`), nunca hardcodeada — mismo criterio
      que ya aplica el proyecto a `SCRAPER_USERNAME`/`SCRAPER_PASSWORD` en
      `AGENTS.md` §6. — módulo: `agent/llm_client.py` (wrapper del cliente DeepSeek,
      desacoplado del resto del agente para poder cambiar de proveedor a futuro
      sin tocar `security_scraping_agent.py`).
      _(2026-07-06 — `agent/llm_client.py`, `agent/config.py`, `agent/tools_schema.py`)_

- [x] **Confirmar soporte de tool-use/function-calling en DeepSeek antes de
      implementar el agente.** El diseño del agente asume que el LLM puede invocar
      el catálogo de `tool_runner.py` (scraping y herramientas Kali) de forma
      estructurada (tool calls), no solo generar texto libre a parsear. Validar
      esto contra la documentación oficial de DeepSeek como paso previo al ítem
      `agent/security_scraping_agent.py` — si no hay soporte nativo de tool-use,
      definir un formato de salida estructurado (ej. JSON) como alternativa.
      — módulo: `agent/llm_client.py`.
      _(2026-07-06 — confirmado: tool_calls nativo; fallback `json_plan` en `parse_json_plan`)_

- [x] **`docker-compose.yml` único para todo el proyecto.** Un solo archivo que
      levante todos los servicios de la pila como una unidad:
      - `scraper_agent` (API/backend Python: crawler, parser, search, agente LLM).
      - `kali` (entorno de herramientas de seguridad, ver entrada anterior;
        contenedor separado, red interna propia, sin puertos expuestos al host).
      Red interna de Docker para que `scraper_agent` hable con `kali` sin exponer
      este último al host. — `docker-compose.yml`, `docker/kali/Dockerfile`,
      `docker/scraper_agent/Dockerfile`, `security_env/docker_executor.py`.
      _(2026-07-06 — tests/test_docker_compose.py)_

- [x] **Un único puerto externo: 1212 → endpoint de chat.** Todo el sistema se
      consume desde afuera por un solo puerto host (**1212**), mapeado al puerto
      interno 8000 del servicio `scraper_agent`.
      _(2026-07-06 — `1212:8000` en docker-compose.yml)_

### Added (2026-07-06 — DeepSeek llm_client, ítem 11)

- [x] **`agent/llm_client.py`:** cliente httpx a `POST /chat/completions`, tools payload,
      `DeepSeekClient.tool_use_capability()`, fallback `parse_json_plan`.
- [x] **`agent/tools_schema.py`:** 4 tools (crawl, search, list/run security).
- [x] **Tests:** `tests/test_llm_client.py` (12); `.env.example` con `DEEPSEEK_*`.
      _(2026-07-06 — 109 pytest OK en suite completa)_

### Added (2026-07-06 — agente orquestador + chat, ítem 12)

- [x] **`agent/security_scraping_agent.py`:** loop tool_calls (max 5 rondas), SSE events.
- [x] **`agent/tool_handlers.py`:** dispatch crawl/search/security tools.
- [x] **`api/chat_endpoint.py`:** `POST /chat` (SSE), `GET /health`, FastAPI.
- [x] **`storage/session_log.py`:** auditoría JSONL por sesión.
- [x] **CLI:** `scraper-agent serve --port 8000`.
- [x] **Tests:** `test_security_scraping_agent.py`, `test_chat_endpoint.py` (115 pytest total).
      _(2026-07-06)_

### Added (2026-07-06 — docker-compose, ítem 13)

- [x] **`docker-compose.yml`:** `scraper_agent` (1212:8000) + `kali-tools` (sin ports).
- [x] **`docker/kali/Dockerfile`:** whois, dig, curl, nmap, wget.
- [x] **`docker/scraper_agent/Dockerfile`:** Python 3.12, Playwright, uvicorn, docker CLI.
- [x] **`security_env/docker_executor.py`:** `docker exec` cuando `KALI_CONTAINER` está definido.
- [x] **Tests:** `test_docker_compose.py`, `test_docker_executor.py`.
      _(2026-07-06 — 122 pytest OK)_

### README
- [x] Sección Despliegue Docker Compose (puerto 1212, variables, curl de prueba).
      _(2026-07-06)_

---

### Added (2026-07-06 — ampliar categorías de herramientas para objetivos ya autorizados)

> **Contexto:** `docs/alcance-seguridad.md` y `tool_catalog.yaml` (ítems 9 y 10b)
> definieron un catálogo inicial centrado en reconocimiento pasivo,activo  y análisis
> básico (whois, dig, curl, headers/TLS, nmap en modo intrusivo controlado para no ser detectado). Esta entrada
> registra el pedido de **ampliar las categorías de herramientas disponibles**
> (escaneo activo más profundo, pruebas de vulnerabilidades conocidas, fuzzing
> acotado, nmap (escaneo de puertos y servicios),netcat (pruebas de conexión), Escaneo de vulnerabilidades (nikto, OpenVAS),
> Consultas DNS directas (dig, dnsenum, fierce)
> Ping sweeps, traceroute, etc.) para que el pentesting sea más completo — **sin tocar**
> la política de rechazo previo a ejecución ni autorizar hosts no listados.

- [x] **Revisión de `docs/alcance-seguridad.md` — nuevas categorías propuestas.**
      §2.4 documenta `active_scanning`, `known_vuln_scanning`, `bounded_fuzzing`
      con herramientas, límites e intrusión acotada. — archivo: `docs/alcance-seguridad.md`.
      _(2026-07-06)_

- [x] **`allowed_categories` por objetivo en `authorized_targets.yaml`.**
      `config/authorized_targets.yaml.example` documenta las categorías ampliadas;
      `authorization_guard.py` valida contra la lista del objetivo (sin cambio de
      mecanismo). Fixture de tests incluye `full.example.com` con las 5 categorías.
      _(2026-07-06)_

- [x] **Ampliar `tool_catalog.yaml` con las herramientas de las nuevas categorías.**
      Añadidos `nmap_services`, `nikto_safe`, `gobuster_dir`; `categories.py`
      centraliza categorías; Dockerfile Kali incluye nikto, gobuster, seclists.
      Tests: rechazo si categoría no permitida + argv esperado en `full.example.com`.
      _(2026-07-06)_

### README
- [x] Sección "Categorías de pentesting disponibles" en Agente de seguridad;
      catálogo ampliado y tabla de categorías/herramientas.
      _(2026-07-06)_

---

### Fixed (2026-07-07 — pentest krapcom.net 6 fallas)

- [x] **`settings.yaml` — `max_runtime_seconds` 300 → 900.** Evita exit 124 en herramientas
      de fase 5b–5d que superaban el tope global de 300s. — `security_env/settings.yaml`.
- [x] **`gobuster_dir` — flag `--wildcard`.** Mitiga sitios que devuelven 200 para cualquier
      ruta. — `security_env/tool_catalog.yaml`.
- [x] **`nuclei_safe` — timeout 900s, tags acotados y `-max-host-error 10`.** Reduce ruido
      y evita timeout prematuro. — `security_env/tool_catalog.yaml`.
- [x] **`spiderfoot_passive` — módulos limitados y timeout 900s.** Reemplaza use case
      `passive` completo por `sfp_dnsresolve,sfp_whois,sfp_sslcert,sfp_hackertarget`.
      — `security_env/tool_catalog.yaml`.
- [x] **`dirb_small` / `ffuf_dir` — wordlists small, timeouts 600s, ffuf con `-ac` y
      sin código 200.** Evita falsos positivos en sitios wildcard. — `tool_catalog.yaml`.
- [x] **`wpscan_enum` — wrapper `wpscan_enum_safe`.** Ejecuta `--update` antes del scan;
      elimina `--no-update` que bloqueaba sin BD local. — `docker/kali/bin/wpscan_enum_safe`,
      `docker/kali/Dockerfile`, `tool_catalog.yaml`.
- [x] **`docker_executor.py` — inyección de claves Shodan/Censys al contenedor.** Pasa
      `SHODAN_API_KEY`, `CENSYS_API_ID`, `CENSYS_API_SECRET` vía `docker exec -e`.
      — `security_env/docker_executor.py`; tests `test_docker_executor.py`.
- [x] **`.env` — placeholders OSINT APIs (fase 5e).** Sin eliminar claves DeepSeek existentes.
- [x] **`docs/alcance-seguridad.md` §2.6–2.8** — límites corregidos (nuclei tags, amass,
      theHarvester duckduckgo, spiderfoot módulos, gobuster wildcard, wpscan wrapper).

### Fixed (2026-07-06 — endurecer pentest en contenedor Kali)

> **Contexto:** la PoC contra `krapcom.net` expuso fallos operativos en el runtime
> Docker: workspace inexistente, `curl` sin CA bundle y `whois` con error
> `getaddrinfo … ai_socktype` por preferencia IPv6 en contenedor minimal.

- [x] **`docker_executor.py` — crear workspace antes de `docker exec -w`.**
      `_ensure_workdir()` ejecuta `mkdir -p` en el contenedor Kali; evita exit 127
      por `chdir` fallido en `/tmp/<session_id>`. — módulo: `security_env/docker_executor.py`.
      _(2026-07-06)_

- [x] **`docker/kali/Dockerfile` — `ca-certificates` + `update-ca-certificates`.**
      Corrige `curl_headers` con exit 77 (`/etc/ssl/certs/ca-certificates.crt` ausente).
      Añade `netbase` y preferencia IPv4 en `/etc/gai.conf` para estabilizar resolución
      de servidores WHOIS. — archivo: `docker/kali/Dockerfile`.
      _(2026-07-06)_

- [x] **`docker-compose.yml` — `sysctls` IPv6 deshabilitado en servicio `kali`.**
      Mitiga fallo de `whois` (`Servname not supported for ai_socktype`) en imágenes
      rolling sin rutas IPv6. — archivo: `docker-compose.yml`.
      _(2026-07-06)_

- [x] **`scripts/run_pentest.py` — script de corrida repetible.**
      Ejecuta catálogo pasivo + nmap top 100; guarda JSON en `output/pentest_<host>.json`;
      exit code 1 si alguna herramienta falla. — archivo: `scripts/run_pentest.py`.
      _(2026-07-06)_

- [x] **Tests:** `test_docker_cli_executor_creates_workdir_before_exec` en
      `tests/test_docker_executor.py`.
      _(2026-07-06)_

- [~] **`nikto` en imagen Kali — mirror intermitente (499 AV).**
      Instalación movida a capa RUN separada con tolerancia a fallo; si el build
      omite nikto, instalar manualmente en el contenedor o usar mirror alterno.
      — archivo: `docker/kali/Dockerfile`.
      _(2026-07-06 — PoC pasiva OK sin depender de nikto)_

### README
- [x] Sección Agente de seguridad — nota de rebuild Kali tras cambios de imagen
      (`docker compose build kali && docker compose up -d kali`) y script `run_pentest.py`.
      _(2026-07-06)_

---

### Added (2026-07-06 — roadmap pentesting ampliado v0.5.x)

> **Contexto:** catálogo actual en `tool_catalog.yaml` (7 herramientas, categorías
> v1.1). Esta entrada registra la **hoja de ruta** para integrar el stack de
> pentesting profesional solicitado, en fases **básica → intermedia → avanzada**.
> Cada herramienta nueva exige, antes de codear: (1) fila en `docs/alcance-seguridad.md`
> con límites explícitos, (2) categoría en `allowed_categories`, (3) entrada en
> `tool_catalog.yaml` con argv acotado, (4) paquete en `docker/kali/Dockerfile`.
>
> **Leyenda:** `[x]` ya en catálogo · `[ ]` pendiente · `[⛔]` fuera de alcance
> por defecto (`docs/alcance-seguridad.md` §3 — explotación, fuerza bruta, DoS).

#### Reconocimiento (OSINT / recopilar información sin impacto directo)

| Nivel | Herramienta | Estado | Notas de integración |
|-------|-------------|--------|----------------------|
| Básica | `whois` | [x] | `tool_id: whois` — `passive_recon` |
| Básica | `dig` | [x] | `tool_id: dig_a` — registro A |
| Básica | `nslookup` | [x] | `tool_id: nslookup_a` — `passive_recon` |
| Básica | `curl` (headers) | [x] | `tool_id: curl_headers` — GET `-I` HTTPS |
| Intermedia | `dnsenum` | [x] | `tool_id: dnsenum_safe` — `dns_enumeration` |
| Intermedia | `dnsrecon` | [x] | `tool_id: dnsrecon_std` — `dns_enumeration` |
| Intermedia | `sublist3r` | [x] | `tool_id: sublist3r_safe` — `dns_enumeration` |
| Intermedia | `theHarvester` | [x] | `tool_id: theharvester_safe` — duckduckgo/google; límite 50 |
| Avanzada | **Amass** (OWASP) | [x] | `tool_id: amass_passive` — `-passive`; max 30 DNS queries |
| Avanzada | **Recon-ng** | [ ] | Framework modular OSINT; solo módulos pasivos en catálogo cerrado |
| Avanzada | **SpiderFoot** | [x] | `tool_id: spiderfoot_passive` — use case passive; 1 hilo |
| Avanzada | **Maltego** | [ ] | Visualización relaciones; **integración documental** (export/import JSON); no GUI en contenedor |

#### Escaneo (hosts, puertos, servicios, vulnerabilidades)

| Nivel | Herramienta | Estado | Notas de integración |
|-------|-------------|--------|----------------------|
| Básica | `nmap` (top ports) | [x] | `nmap_top100`, `nmap_services` — sin NSE ofensivo |
| Básica | `netdiscover` | [x] | `tool_id: netdiscover_passive` — solo CIDR autorizado; `-s 2 -c 5` |
| Intermedia | `masscan` | [x] | `tool_id: masscan_top_ports` — rate 50 pps; puertos fijos |
| Intermedia | `zenmap` | [⛔] | GUI; no aplica en runtime headless — usar solo `nmap` CLI |
| Intermedia | `nikto` | [x] | `nikto_safe` — `-Tuning x`, `-maxtime 120s` |
| Avanzada | `nmap` + NSE `--script vuln` | [ ] | Requiere categoría nueva `vuln_script_scanning`; scripts allowlist, no explotación |
| Avanzada | **Nessus / OpenVAS** | [x] | Documentado en `docs/integraciones-externas-5e.md` — export manual |
| Avanzada | **Nuclei** (ProjectDiscovery) | [x] | `tool_id: nuclei_safe` — severidad info/low/medium; rate-limit 15 |
| Avanzada | ~~**Shodan / Censys API**~~ | retirado | Retirado 2026-07-07 — ver "Removed (2026-07-07 — retiro de Shodan/Censys)" |

#### Explotación web (superficie y fuzzing acotado)

| Nivel | Herramienta | Estado | Notas de integración |
|-------|-------------|--------|----------------------|
| Básica | `dirb` | [x] | `tool_id: dirb_small` — wordlist common; sin recursión |
| Básica | `gobuster` | [x] | `gobuster_dir` — `bounded_fuzzing` |
| Intermedia | `sqlmap` | [⛔] | Solo detección (`--batch --level=1`) evaluable; **prohibido** `--dump` / extracción |
| Intermedia | `wpscan` | [x] | `tool_id: wpscan_enum` — `-e vp,vt`; sin brute credenciales |
| Avanzada | **Burp Suite Pro** | [⛔] | Herramienta manual externa; no invocable desde agente |
| Avanzada | **ffuf** | [x] | `tool_id: ffuf_dir` — common.txt; rate 10/s; 5 hilos |
| Avanzada | **OWASP ZAP** | [ ] | Modo API daemon opcional; spider pasivo acotado |
| Avanzada | **Metasploit** | [⛔] | Explotación — §3 fuera de alcance |
| Avanzada | **Commix** | [⛔] | Command injection automatizada — §3 fuera de alcance |

#### Cracking (contraseñas y hashes)

| Nivel | Herramienta | Estado | Notas de integración |
|-------|-------------|--------|----------------------|
| Básica | `john` (John the Ripper) | [⛔] | Fuerza bruta — §3 fuera de alcance |
| Intermedia | `hydra` / `medusa` | [⛔] | Ataque credenciales remotas — §3 |
| Avanzada | **Hashcat** (+ reglas) | [⛔] | Cracking offline — §3 |
| Avanzada | **CrackMapExec / NetExec** | [⛔] | Credenciales en AD/red — §3 |
| Avanzada | **Responder + hashcat** | [⛔] | Captura NTLM en red — §3 |

#### Orden de implementación sugerido (v0.5.x)

| Fase | Alcance | Entregables |
|------|---------|-------------|
| **5a** | Recon básico/intermedio | `nslookup`, `dnsenum`, `dnsrecon`, `sublist3r` en catálogo + § alcance |
| **5b** | Escaneo intermedio | `masscan` acotado, `netdiscover` (solo CIDR autorizado), integración **Nuclei** (templates safe) |
| **5c** | Recon avanzado OSINT | **Amass** (modo pasivo), **theHarvester**, **SpiderFoot** CLI |
| **5d** | Web acotado | `dirb`, **ffuf**, `wpscan` enumeración; ampliar `run_pentest.py` por categoría |
| **5e** | APIs externas | Shodan/Censys, OpenVAS/Nessus vía export — sin binarios ofensivos en agente |
| **—** | Explotación / cracking | Permanece **fuera de catálogo** salvo revisión legal y §3 del alcance |

- [x] **Implementar fase 5a — reconocimiento intermedio en `tool_catalog.yaml`.**
      Categoría `dns_enumeration`; herramientas `nslookup_a`, `dnsenum_safe`,
      `dnsrecon_std`, `sublist3r_safe`; §2.5 en `docs/alcance-seguridad.md`;
      tests `tests/test_tool_catalog_phase5a.py`; `run_pentest.py --phase 5a|full`.
      _(2026-07-06)_

### README
- [x] Roadmap pentesting v0.5.x — fases 5a–5e completadas; tabla categorías en README.
      _(2026-07-06)_
- [x] Tabla categorías — fila `osint_recon` y ejemplos `--phase 5c|full`.
      _(2026-07-06)_
- [x] Tabla categorías — filas `network_discovery`, `masscan_top_ports`, `nuclei_safe`; `--phase 5b|full`.
      _(2026-07-06)_
- [x] Tabla categorías — fila `dns_enumeration` y ejemplos `--phase 5a|full`.
      _(2026-07-06)_
      — mismos módulos; categorías nuevas en `authorized_targets.yaml.example`.

- [x] **Implementar fase 5b — escaneo intermedio en `tool_catalog.yaml`.**
      Categoría `network_discovery`; herramientas `masscan_top_ports`,
      `netdiscover_passive`, `nuclei_safe`; §2.6 en `docs/alcance-seguridad.md`;
      tipo param `cidr`; tests `tests/test_tool_catalog_phase5b.py`;
      `run_pentest.py --phase 5b|full` con resolución A→IP para masscan.
      _(2026-07-06)_

- [x] **Implementar fase 5c — OSINT avanzado en `tool_catalog.yaml`.**
      Categoría `osint_recon`; herramientas `amass_passive`, `theharvester_safe`,
      `spiderfoot_passive`; §2.7 en `docs/alcance-seguridad.md`;
      tests `tests/test_tool_catalog_phase5c.py`; `run_pentest.py --phase 5c|full`;
      claves API opcionales en `.env.example`.
      _(2026-07-06)_

- [x] **Implementar fase 5d — fuzzing web acotado en `tool_catalog.yaml`.**
      Herramientas `dirb_small`, `ffuf_dir`, `wpscan_enum`; tests sin flags ofensivos;
      `tests/test_tool_catalog_phase5d.py`; `run_pentest.py --phase 5d|full`.
      _(2026-07-06)_

- [x] **Implementar fase 5e — APIs externas Shodan/Censys + doc OpenVAS/Nessus.**
      Categoría `external_api_recon`; wrappers `docker/kali/bin/*`; §2.9 alcance;
      `docs/integraciones-externas-5e.md`; skip automático sin claves en `run_pentest.py`.
      _(2026-07-06)_

### README

---

> Ítems aún no implementados o parcialmente hechos (`[ ]` / `[~]`). Cada entrada
> describe **qué mejora en el aplicativo** y el módulo afectado. No arrancar desarrollo
> sin verificar que el ítem no exista ya aquí o arriba en `[Unreleased]`.

#### Extracción y calidad de datos (v0.2.x)

- [x] **Extracción completa de `authorship.authors[]` (nombre + URL de perfil).**
      **Mejora:** permite filtrar y agrupar noticias por autor real (no solo texto
      suelto), enriquecer `search_results[]` por firmante y auditar cobertura editorial.
      — módulo: `parser/article_extractor.py`; schema: `authorship.authors[]`.
      _(2026-07-06 — `_extract_authors()` con JSON-LD, `/autor/`, byline "Por …")_

- [x] **Extracción de `taxonomy` (sección, categoría, etiquetas).**
      **Mejora:** habilita búsqueda por rubro ("economía", "política"), segmentación en
      `scraper-agent search` sin depender solo de keywords en el titular, y reportes
      por vertical en el consolidado multi-sitio. — schema: `taxonomy`; módulo:
      `parser/article_extractor.py` (`_extract_taxonomy()`); búsqueda: `match_in: taxonomy`.
      _(2026-07-06 — `article:tag`, keywords meta/JSON-LD, breadcrumbs, tag links)_

- [~] **Selectores por sitio más robustos (10 medios peruanos).**
      **Mejora:** sube `extraction_quality.confidence_score` y reduce
      `articles_partial` en sitios con DOM distinto (ojo.pe, larepublica, elperuano);
      menos artículos vacíos o con sidebar mezclado. — módulos: `config/sites/*.yaml`,
      `parser/article_extractor.py`, `parser/selectors.py`.

- [x] **Soporte JSONL incremental para corridas largas.**
      **Mejora:** si el crawl se interrumpe (`max_pages` alto, Cloudflare, timeout), no
      se pierden artículos ya extraídos; permite reanudar y procesar datasets grandes sin
      cargar todo en memoria. — módulo: `storage/json_writer.py`
      _(2026-07-06 — sidecar `checkpoint_dir/articles.jsonl`, recarga al reanudar,
      dedupe por `article_id`, `output.incremental` en YAML; tests en `test_storage.py`)_

#### Operación, anti-bot y documentación (v0.2.x – v0.3.x)

- [x] **README: `prefer_playwright`, `article_link_pattern`, `expand_sitemaps` y nota
      expreso/Cloudflare.**
      **Mejora:** quien despliega el scraper en un servidor nuevo sabe configurar sitios
      bloqueados (403/CF) sin releer el CHANGELOG; reduce tiempo de onboarding y corridas
      en 0 artículos por mala config. — sección README: anti-bot / discovery.
      _(2026-07-06 — README ampliado con tablas y expreso.com.pe)_

- [x] **Documentación de selectores y troubleshooting por dominio.**
      **Mejora:** tabla "síntoma → causa → fix" por medio (feed roto, sitemap anidado,
      `max_depth`, UTC en filtro de fechas); acelera diagnóstico cuando un sitio baja de
      25 a 0 artículos tras un cambio del portal. — `docs/troubleshooting-por-dominio.md`
      + enlace en README.
      _(2026-07-06)_

#### Búsqueda y consumo de resultados (v0.3.x)

- [x] **Búsqueda sobre JSON ya generado (sin re-crawlear).**
      **Mejora:** reutilizar `output/*.json` existentes con `scraper-agent search
      --input output/gestion_pe.json --target-file ...` para iterar objetivos sin gastar
      red ni tiempo de crawl; útil para afinar `min_score` y keywords. — módulos:
      `cli.py`, `search/persist.py`.
      _(2026-07-06 — flag `--input` + tests)_

- [x] **Más objetivos predefinidos en `config/targets/`** (empleo, commodities,
      sentencias, decretos).
      **Mejora:** el usuario arranca con casos reales listos para copiar en lugar de
      inventar YAML desde cero; acelera adopción del modo `search` / `run-all
      --target-file`.
      _(2026-07-06 — 4 YAML nuevos + test de carga)_

#### Calidad y CI (v0.3.x)

- [x] **CI con pytest + validación de fixtures contra `scraper-schema.json`.**
      **Mejora:** cada cambio en extractor o schema rompe el build antes de merge, no en
      producción; protege las pruebas y el contrato de salida. — `.github/workflows/ci.yml`,
      `tests/fixtures/*.json`, `tests/test_schema_fixtures.py`.
      _(2026-07-06 — 75 pytest OK; ruff limpio)_

#### Release estable (v1.0)

- [x] **Eliminar código legacy (`PageRecord`, parsers viejos, formato `pages[].data`).**
      **Mejora:** menos superficie de bugs y confusión para contribuidores; el único
      contrato de salida es `scraper-schema.json`. — módulos: `models/schemas.py`,
      `models/__init__.py`, `tests/test_legacy_removed.py`.
      _(2026-07-06)_

- [x] **Guía de contribución y ejemplos multi-dominio.**
      **Mejora:** terceros pueden agregar un medio nuevo (`config/sites/`) o un matcher
      de búsqueda sin leer todo el repo. — `CONTRIBUTING.md`, enlace en README.
      _(2026-07-06)_

#### Agente de seguridad y entorno Kali Linux (v0.4.x — propuesto)

- [x] **`security_env/kali_runtime.py` — entorno Kali aislado y endurecido.**
      **Mejora:** ofrece un runtime de Kali Linux reproducible y seguro por diseño
      (no un contenedor con acceso total) como base para las herramientas de
      seguridad y scraping avanzado. Basado en las categorías definidas en
      `docs/alcance-seguridad.md`. Endurecimiento mínimo exigido: sin
      `--privileged`; `--cap-drop=ALL` + solo los capabilities que cada
      herramienta habilitada realmente requiera; filesystem raíz **read-only**
      (única ruta escribible: `/tmp/<session_id>`, borrada al cerrar sesión);
      límites de CPU/memoria/tiempo de vida por contenedor; red egress
      restringida por defecto a los hosts que ya pasaron `authorization_guard`.
      — módulos: `security_env/kali_runtime.py`, `docker/kali/Dockerfile` (Docker pendiente).
      **Criterio de aceptación (a implementar):** test que confirma que un
      intento de escritura fuera de `/tmp/<session_id>` falla, y que el
      contenedor no tiene egress hacia hosts fuera del allowlist de la sesión.
      _(2026-07-06 — `kali_runtime.py` + `tests/test_kali_runtime.py`; Docker en ítem 13)_

- [x] **`security_env/tool_runner.py` + `tool_catalog.yaml` — catálogo cerrado.**
      **Mejora:** permite invocar herramientas Kali de forma estructurada y
      auditable, sin exponer una shell libre al agente. El catálogo se deriva
      directamente de las categorías "permitidas" de `docs/alcance-seguridad.md`
      (no es una lista aparte que se pueda desincronizar del documento de
      alcance). Cada entrada define: nombre, binario, parámetros tipados (sin
      interpolación de string libre), timeout máximo, y a qué categoría de
      `alcance-seguridad.md` pertenece. — módulos: `security_env/tool_runner.py`,
      `security_env/tool_catalog.yaml`.
      **Criterio de aceptación (a implementar):** tests que confirman que
      (a) una herramienta no listada en el catálogo es rechazada, (b) un
      parámetro fuera del tipo/patrón esperado es rechazado antes de ejecutar
      nada, (c) toda ejecución exitosa o rechazada queda como entrada de log
      auditable (quién, objetivo, herramienta, resultado).
      _(2026-07-06 — 4 herramientas v1; `tests/test_tool_runner.py`)_

- [x] **`security_env/authorization_guard.py` — verificación de objetivo.**
      **Mejora:** evita que el agente ejecute cualquier herramienta de testing de
      seguridad contra un dominio no autorizado explícitamente; extiende
      `AGENTS.md` §9 a la nueva capa. Lee `config/authorized_targets.yaml` y
      rechaza la ejecución si el objetivo está ausente de la lista, si su
      autorización está expirada, o si la categoría de herramienta solicitada
      no está dentro de `allowed_categories` de esa entrada. — módulo:
      `security_env/authorization_guard.py`.
      **Criterio de aceptación (a implementar):** tests para los 3 casos de
      rechazo (objetivo ausente, autorización expirada, categoría no permitida)
      — los 3 deben bloquear la ejecución **antes** de que `tool_runner.py`
      reciba el comando.
      _(2026-07-06 — `tests/test_authorization_guard.py` + integración en tool_runner)_

- [x] **Agente orquestador único (scraping + seguridad) por chat.**
      **Mejora:** una sola interfaz conversacional para todo el sistema — el
      usuario pide en lenguaje natural, el agente decide si es tarea de scraping,
      de testing de seguridad, o ambas, y ejecuta con streaming de progreso.
      — módulos: `agent/security_scraping_agent.py`, `api/chat_endpoint.py`.
      _(2026-07-06)_

- [x] **Ampliar categorías de pentesting para objetivos ya autorizados.**
      **Mejora:** categorías v1.1 (`active_scanning`, `known_vuln_scanning`,
      `bounded_fuzzing`) y herramientas asociadas — ver ítems 14–16 y entrada
      **roadmap v0.5.x** (2026-07-06) para el stack ampliado pendiente.
      _(2026-07-06 — fases 5a–5e implementadas)_

#### Criterio de prioridad sugerido (para la siguiente tanda de desarrollo)

| Orden | Ítem | Por qué primero |
|-------|------|-----------------|
| 1 | ~~`authorship` + `taxonomy`~~ | ✅ 2026-07-06 |
| 2 | ~~JSONL incremental~~ | ✅ 2026-07-06 |
| 3 | ~~README anti-bot / troubleshooting~~ | ✅ 2026-07-06 (README; troubleshooting dominio pendiente) |
| 4 | ~~`search --input` (sin re-crawl)~~ | ✅ 2026-07-06 |
| 5 | ~~Troubleshooting por dominio~~ | ✅ 2026-07-06 |
| 6 | ~~Más `config/targets/`~~ | ✅ 2026-07-06 |
| 7 | ~~CI + fixtures schema~~ | ✅ 2026-07-06 |
| 8 | ~~Legacy removal + CONTRIBUTING~~ | ✅ 2026-07-06 |
| 9 | ~~`docs/alcance-seguridad.md`~~ | ✅ 2026-07-06 |
| 10a | ~~`security_env/kali_runtime.py`~~ | ✅ 2026-07-06 (Docker en ítem 13) |
| 10b | ~~`security_env/tool_runner.py` + `tool_catalog.yaml`~~ | ✅ 2026-07-06 |
| 10c | ~~`security_env/authorization_guard.py`~~ | ✅ 2026-07-06 |
| 11 | ~~Confirmar tool-use + `agent/llm_client.py`~~ | ✅ 2026-07-06 |
| 12 | ~~`security_scraping_agent.py` + `api/chat_endpoint.py` + session_log~~ | ✅ 2026-07-06 |
| 13 | ~~`docker-compose.yml` (1212, scraper_agent + kali)~~ | ✅ 2026-07-06 |
| 14 | ~~`docs/alcance-seguridad.md` — nuevas categorías~~ | ✅ 2026-07-06 |
| 15 | ~~`allowed_categories` ampliado + `.example`~~ | ✅ 2026-07-06 |
| 16 | ~~Herramientas nuevas en `tool_catalog.yaml` + Kali Dockerfile~~ | ✅ 2026-07-06 |
| 17 | ~~Roadmap fase 5a — recon DNS intermedio~~ | ✅ 2026-07-06 |
| 18 | ~~README — tabla `dns_enumeration`~~ | ✅ 2026-07-06 |
| 19 | ~~Roadmap fase 5b — masscan, netdiscover, Nuclei~~ | ✅ 2026-07-06 |
| 20 | ~~Roadmap fase 5c — Amass, theHarvester, SpiderFoot~~ | ✅ 2026-07-06 |
| 21 | ~~Roadmap fase 5d — dirb, ffuf, wpscan~~ | ✅ 2026-07-06 |
| 22 | ~~Roadmap fase 5e — Shodan/Censys + doc OpenVAS/Nessus~~ | ✅ 2026-07-06 |
| 23 | ~~Retiro Shodan/Censys + roadmap fase 6a–6f~~ | ✅ 2026-07-07 |

---

### Removed (2026-07-07 — retiro de Shodan/Censys)

> **Contexto:** se pide sacar del catálogo las herramientas que dependen de APIs
> de terceros de pago/cuota (Shodan, Censys) para que el catálogo quede enfocado
> en herramientas propias de Kali, sin necesidad de API keys externas.

- [x] **Quitar `shodan_dns` y `censys_hosts` del catálogo cerrado.** Elimina las
      2 entradas de `security_env/tool_catalog.yaml`, la categoría
      `external_api_recon` de `security_env/categories.py`, los wrappers
      `docker/kali/bin/shodan_dns_lookup` / `censys_hosts_lookup` y su `COPY`/
      `chmod` en `docker/kali/Dockerfile`, las variables `SHODAN_API_KEY` /
      `CENSYS_API_ID` / `CENSYS_API_SECRET` de `docker-compose.yml` y
      `.env.example`, y la inyección de env externo en
      `security_env/docker_executor.py` (`EXTERNAL_API_ENV_KEYS`). También la
      fase `"5e"` y `EXTERNAL_API_TOOLS` de `scripts/run_pentest.py`.
      — módulos: `tool_catalog.yaml`, `categories.py`, `docker_executor.py`,
      `docker-compose.yml`, `docker/kali/Dockerfile`, `run_pentest.py`.
      _(2026-07-07)_
- [x] **Retirar `tests/test_tool_catalog_phase5e.py`** y las referencias a
      `shodan_dns`/`censys_hosts` en `tests/test_tool_runner.py` y
      `tests/test_docker_executor.py`.
      _(2026-07-07)_
- [x] **Actualizar documentación.** `docs/alcance-seguridad.md` §2.9 (recon vía
      APIs externas) se elimina; `docs/integraciones-externas-5e.md` pierde su
      §1 (Shodan/Censys) y mantiene OpenVAS/Nessus; `README.md` pierde la fila
      `external_api_recon` de la tabla de categorías. La fila del roadmap
      "Avanzada | Shodan / Censys API | [x]" (más arriba, tabla de Escaneo)
      queda tachada con nota de retiro.
      _(2026-07-07)_

### README
- [x] Quitar sección/fila de Shodan/Censys y `external_api_recon` de la tabla
      "Categorías de pentesting disponibles".
      _(2026-07-07)_

---

### Added (2026-07-07 — roadmap pentesting ampliado v0.6.x — fases 6a–6f)

> **Contexto:** se pide ampliar el catálogo con herramientas adicionales de
> descubrimiento de hosts, fingerprint web, análisis TLS, DNS, detección de
> vulnerabilidades acotada e ICS/SCADA solo-lectura, para que un pedido de
> "escaneo" por chat pueda cubrir más superficie con el mismo modelo de
> catálogo cerrado + autorización por objetivo ya vigente. Mismo criterio que
> `docs/alcance-seguridad.md` §3: nada de explotación, fuerza bruta o DoS.

#### Herramientas agregadas

| Fase | Herramienta | Categoría | Notas de integración |
|------|-------------|-----------|----------------------|
| 6a | `zmap_safe` | `active_scanning` | 1 host/IP, 1 puerto fijo, sin barrido de rango (`-N 1`) |
| 6a | `unicornscan_safe` | `active_scanning` | TCP asíncrono acotado a top puertos comunes, 1 host |
| 6b | `whatweb_safe` | `passive_recon` | `-a 1` (agresividad mínima), 1 host |
| 6b | `httpx_probe` | `passive_recon` | binario Kali `httpx-toolkit` (evita choque con lib Python `httpx`); `-silent -tech-detect` |
| 6b | `wafw00f_safe` | `passive_recon` | detección de WAF, sin flags de bypass |
| 6c | `sslscan_safe` | `tls_analysis` (nueva) | configuración TLS/cipher suite |
| 6c | `sslyze_safe` | `tls_analysis` (nueva) | análisis TLS más profundo |
| 6c | `testssl_safe` | `tls_analysis` (nueva) | `--fast` + timeout acotado |
| 6c | `openssl_cert` | `tls_analysis` (nueva) | wrapper `docker/kali/bin/openssl_cert_check` (mismo patrón que `wpscan_enum_safe`); solo handshake, sin renegociación |
| 6d | `fierce_safe` | `dns_enumeration` | límites por defecto del paquete Kali |
| 6e | `nmap_vuln_scripts` | `vuln_script_scanning` (nueva) | **allowlist explícita** de scripts NSE no destructivos (`banner`, `ssl-cert`, `http-security-headers`, `ssh2-enum-algos`, `smb-os-discovery`) — **no** se habilita `--script vuln` completo |
| 6f | `modbus_s7_discover` | `ics_scada_recon` (nueva) | `nmap --script modbus-discover,s7-info`; **solo lectura/identificación**, sin scripts de escritura; requiere categoría habilitada explícitamente por objetivo — riesgo de estabilidad en PLCs/SCADA reales si se usa sin autorización del responsable industrial |

- [x] **Categorías nuevas en `security_env/categories.py`:** `tls_analysis`,
      `vuln_script_scanning`, `ics_scada_recon` + fila de ejemplo (comentada)
      en `config/authorized_targets.yaml.example`.
      _(2026-07-07)_
- [x] **12 entradas nuevas en `security_env/tool_catalog.yaml`** (tabla de
      arriba) con `argv_template` acotado y timeout por herramienta.
      _(2026-07-07 — 32 herramientas en catálogo tras el retiro de Shodan/Censys)_
- [x] **`docker/kali/Dockerfile`** — paquetes `zmap`, `unicornscan`, `whatweb`,
      `wafw00f`, `sslscan`, `sslyze`, `testssl.sh`, `fierce`, `httpx-toolkit`
      (capa `|| true` para mirrors inestables, mismo patrón que `nikto`/
      `masscan`); `nmap` y sus scripts NSE (`modbus-discover`, `s7-info`,
      subset `vuln` seguro) ya vienen con el paquete `nmap` existente.
      Wrapper nuevo `docker/kali/bin/openssl_cert_check`.
      _(2026-07-07 — build de imagen no verificado en este entorno, sin Docker
      disponible; sintaxis Dockerfile revisada manualmente contra el patrón
      existente)_
- [x] **`docs/alcance-seguridad.md`** — filas nuevas §2.9–2.10 con límites por
      herramienta, advertencia explícita de riesgo industrial para
      `ics_scada_recon`, y exclusiones documentadas en §3 (Legion, Angry IP
      Scanner, Wappalyzer, AutoRecon, categoría NSE `vuln` completa).
      _(2026-07-07)_
- [x] **`scripts/run_pentest.py`** — fases `"6a"`…`"6f"` + agregado a `"full"`.
      _(2026-07-07 — nota: en esta entrada `modbus_s7_discover` se dejó
      deliberadamente fuera de `"full"` por su categoría `ics_scada_recon`
      restringida; esa decisión se **revirtió** el mismo día — ver "Fixed
      (2026-07-07 — `--phase full` incompleto...)" más abajo, donde `"full"`
      pasa a incluir el catálogo completo y la protección industrial queda
      exclusivamente en `authorization_guard.py`, no en una exclusión de
      lista)_
- [x] **Tests** `tests/test_tool_catalog_phase6a.py` … `phase6f.py` (mismo
      formato que `test_tool_catalog_phase5a.py`): catálogo contiene el
      tool_id con la categoría esperada, y argv exacto contra
      `full.example.com` (`ics.example.com` para `modbus_s7_discover`, fixture
      nueva y dedicada).
      _(2026-07-07 — 169 pytest OK en suite completa, ruff limpio en archivos
      tocados)_

#### Fuera de alcance en esta tanda (decisión explícita, no se agregan)

| Herramienta | Motivo |
|-------------|--------|
| **Metasploit** | Ya excluida por `docs/alcance-seguridad.md` §3 (explotación); sin cambios |
| **Legion** | GUI que solo orquesta `nmap`/`nikto`, ya integrados vía catálogo |
| **Angry IP Scanner** | GUI/Java, redundante con `nmap`/`netdiscover` ya en catálogo |
| **Wappalyzer** | Extensión de navegador, no CLI; `whatweb`/`httpx_probe` cubren el mismo fingerprint headless |
| **AutoRecon** | Auto-orquesta sub-escaneos en runtime según servicios descubiertos — choca con el principio de catálogo cerrado/argv fijo (§5); `run_pentest.py --phase full` ya cumple ese rol de forma controlada |
| **PLCScan** (standalone) | Herramienta Python2 sin paquete apt, no mantenida — reemplazada por `modbus_s7_discover` (scripts NSE de `nmap`, ya empaquetado) |
| `nmap --script vuln` (categoría completa) | Incluye scripts con payloads tipo exploit; se habilita solo el subconjunto seguro vía `nmap_vuln_scripts` |

### README
- [x] Tabla "Categorías de pentesting disponibles" — agregar `tls_analysis`,
      `vuln_script_scanning`, `ics_scada_recon` y las 12 herramientas nuevas;
      quitar `external_api_recon`; actualizar conteo de catálogo (32) y
      comandos de ejemplo `--phase 6a`…`6f`.
      _(2026-07-07)_

---

### Fixed (2026-07-07 — `--phase full` incompleto y sin captura de errores)

> **Contexto:** un escaneo real contra `krapcom.net` (fase 6, ver entrada
> anterior) reveló que `--phase full` de `scripts/run_pentest.py` **no**
> corría el catálogo completo: era una lista escrita a mano que se había ido
> desincronizando — `nikto_safe`, `nmap_services`, `gobuster_dir` (ya
> existían en `tool_catalog.yaml` desde antes) y varias herramientas de fase
> 6 nunca se agregaron a esa lista. El usuario reportó desconfianza en los
> resultados por reportes incompletos sin aviso explícito. Esta entrada
> elimina la causa raíz: ya no existe una lista manual de "full".

- [x] **`scripts/run_pentest.py` — `PHASE_TOOLS["full"]` calculado desde el
      catálogo real, no hardcodeado.** `PHASE_TOOLS["full"] =
      sorted(load_tool_catalog())` — cualquier tool_id nuevo en
      `tool_catalog.yaml` aparece automáticamente en el próximo `full`, sin
      depender de que alguien recuerde actualizar una lista aparte.
      Herramientas no aplicables al objetivo (`netdiscover_passive` contra
      un dominio en vez de CIDR) o no autorizadas para la categoría del
      target (`modbus_s7_discover` sin `ics_scada_recon` explícito) **no se
      excluyen en silencio**: se intentan igual y quedan como entrada `FAIL`
      en el reporte con el motivo exacto — la única fuente de verdad sobre
      qué corre o no es `authorization_guard.py`, no una lista paralela.
      _(2026-07-07)_
- [x] **`--phase full` pasa a ser el default sin flags.** Antes el default
      era `"base"` (4 herramientas) y había que acordarse de pasar
      `--phase full` para un scan completo. Ahora correr
      `run_pentest.py <host>` sin argumentos adicionales corre las 32
      herramientas del catálogo. `--phase base`/`5a`.../`6f` siguen
      disponibles para pruebas puntuales rápidas.
      _(2026-07-07)_
- [x] **`run_pentest()` captura `SecurityEnvError` (clase base) en vez de
      solo `AuthorizationDenied`/`ToolNotFound`.** Con "full" ahora
      incluyendo herramientas como `netdiscover_passive` (requiere param
      `cidr`), una herramienta con parámetro inválido para el objetivo
      lanzaba `InvalidToolParams`, que **no** estaba en el catch original —
      eso crasheaba el script completo a mitad de un scan en vez de
      registrar esa herramienta puntual como `FAIL` y seguir con el resto.
      Bug real encontrado al ampliar la cobertura de "full", no hipotético.
      — módulo: `scripts/run_pentest.py`.
      _(2026-07-07)_
- [x] **Tests de auditoría genérica (sin listas de tool_ids a mano):**
      `tests/test_run_pentest_completeness.py` — verifica que
      `PHASE_TOOLS["full"]` sea exactamente el catálogo completo, que el
      default sin `--phase` sea `full`, que toda fase nombrada referencie
      tool_ids que existen de verdad, que cada entrada del catálogo tenga
      categoría/timeout/argv válidos, y que `InvalidToolParams`/
      `PolicyViolation` sean subclases de `SecurityEnvError` (regresión
      directa del bug de arriba).
      _(2026-07-07 — 184 pytest OK en suite completa, ruff limpio)_

### README
- [x] Documentar que `run_pentest.py <host>` sin `--phase` corre las 32
      herramientas por defecto (antes corría solo `base`); actualizar
      ejemplos de la sección "Pentest repetible".
      _(2026-07-07)_

---

### Fixed (2026-07-07 — bugs reales encontrados en la primera corrida `--phase full` de verdad contra krapcom.net)

> **Contexto:** con "full" ahora corriendo el catálogo completo (entrada
> anterior), se ejecutó por primera vez contra `krapcom.net`. De 32
> herramientas, 21 pasaron y 11 fallaron. Cada falla se investigó a mano
> (`docker exec` directo, sin depender del reporte) para separar bugs reales
> de limitaciones externas. No se marcó nada como "resuelto" sin verificarlo
> en vivo dentro del contenedor.

- [x] **`docker/kali/bin/wpscan_enum_safe` con CRLF — shebang roto.** En este
      host Windows, `git config core.autocrlf=true` convertía el wrapper a
      CRLF al hacer checkout; `#!/bin/sh\r` no resuelve como intérprete
      válido dentro del contenedor Linux, y `docker exec` fallaba con
      `exec ...: no such file or directory` — mensaje engañoso, el archivo
      sí existía. — Agregado `.gitattributes` (`docker/kali/bin/* text
      eol=lf`) para que ningún checkout futuro, en ninguna plataforma,
      vuelva a romperlo; normalizado el archivo existente a LF.
      **Criterio de aceptación:** `tests/test_kali_wrapper_scripts.py`
      (nuevo) falla si cualquier wrapper en `docker/kali/bin/` tiene CRLF o
      shebang inválido.
      _(2026-07-07 — verificado con `docker exec kali-tools wpscan_enum_safe`
      tras rebuild: banner de WPScan real, ya no falla)_
- [x] **`dirb_small` — ruta de wordlist inexistente.** El catálogo apuntaba a
      `/usr/share/wordlists/dirb/small.txt`; en la imagen `kali-rolling`
      mínima (`--no-install-recommends`) ese directorio no existe — el
      archivo real vive en `/usr/share/dirb/wordlists/small.txt` (sin el
      symlink que sí crean las metapaquetes completas de Kali). Corregido en
      `tool_catalog.yaml` y `tests/test_tool_catalog_phase5d.py`.
      _(2026-07-07 — verificado con `ls` dentro del contenedor)_
- [x] **`ffuf_dir` — wordlist renombrada en el paquete `seclists` actual.**
      El catálogo apuntaba a `directory-list-2.3-small.txt`; el paquete
      `seclists` 2025.3-0kali1 la distribuye como
      `DirBuster-2007_directory-list-2.3-small.txt`. Corregido en
      `tool_catalog.yaml` y el test correspondiente.
      _(2026-07-07 — verificado con `find` dentro del contenedor)_
- [x] **`gobuster_dir` — flag `--wildcard` ya no existe en gobuster 3.8.2.**
      Fallaba con `flag provided but not defined: -wildcard` (exit 1,
      inmediato, sin escanear nada). Se probó `--force` (documentado como
      "continue even if prechecks fail") como reemplazo — **no** funciona:
      sigue abortando por wildcard en ~1s. Se removió el flag sin reemplazo;
      contra sitios wildcard/SPA (`krapcom.net` devuelve 200 para cualquier
      ruta) `gobuster_dir` seguirá fallando de forma **honesta y explícita**
      (motivo claro en stderr) en vez de crashear por un flag inválido. Sin
      solución genérica de catálogo — documentado como limitación conocida
      en `docs/alcance-seguridad.md` §2.8.
      _(2026-07-07 — ambos flags probados en vivo dentro del contenedor)_
- [ ] **`masscan` y `nikto` ausentes del contenedor — bloqueo de CDN, no bug
      de este proyecto.** Verificado en vivo: `apt-get install masscan` →
      `403 Forbidden`; `apt-get install nikto` → `499 Request has been
      forbidden by antivirus` — ambos desde `kali.download`/`http.kali.org`
      (Cloudflare, IP `104.17.253.239`), persistente incluso tras
      `docker compose build --no-cache`. Ya documentado como riesgo conocido
      en comentarios del `Dockerfile` (`|| true`) desde antes de esta
      sesión; no es una regresión introducida hoy. Sin acción posible desde
      el proyecto (requeriría un mirror/proxy alternativo).
- [ ] **`nuclei_safe` sin plantillas — mismo bloqueo de red.**
      `find /root/.local/nuclei-templates -name '*.yaml' | wc -l` → `0`.
      `nuclei -update-templates` en el `Dockerfile` está envuelto en
      `|| true` (mismo criterio que masscan/nikto) y falla silenciosamente
      por la misma restricción de red del entorno de build.
- [ ] **`amass_passive` — `sudo: libpostal_data: command not found`.**
      Amass 5.1.1 invoca `libpostal_data` (helper de descarga de datos de
      `libpostal`) como parte de `enum -passive`; el paquete `amass` de Kali
      no lo trae ni lo declara como dependencia. Instalar `libpostal`
      agregaría varios cientos de MB a la imagen — fuera de alcance de este
      fix puntual, queda documentado como limitación conocida.
- [x] **`whatweb_safe` — crash intermitente de Ruby, confirmado no
      determinístico, sin acción de código.** Falló una corrida con
      `[BUG] Object ID seen, but not in mapping table: T_ARRAY` (bug de
      compatibilidad conocido de Ruby 3.3+ en el código de compactación de
      objetos de WhatWeb); en la corrida completa siguiente (misma sesión,
      mismo host, mismo argv) **pasó** con resultado real (`nginx/1.20.1`,
      título de la página). Confirmado como flakiness intermitente del
      binario, no un bug del catálogo — no hay fix de código posible desde
      este proyecto.
      _(2026-07-07 — segunda corrida completa: exit=0)_

### Resultado final verificado (segunda corrida completa, tras los 3 fixes)

23/32 herramientas OK (antes 21/32). Mejoras confirmadas en vivo:
`dirb_small` (exit 255 → 0), `wpscan_enum` (exit 255 "file not found" → exit 4
"Scan Aborted: not WordPress" — resultado **correcto**, krapcom.net no corre
WordPress, no es una falla real). `ffuf_dir` pasó de fallar instantáneo por
ruta inexistente a timeout real (600s) contra un sitio wildcard — la ruta ya
es correcta, el timeout es comportamiento esperado de ffuf contra un
catch-all sin `--exclude-length` específico del objetivo.

Fallas restantes, todas explicadas y con causa raíz verificada en vivo (no
hipotética): `amass_passive` (dependencia faltante), `ffuf_dir` (timeout por
wildcard), `gobuster_dir` (limitación de versión, sin flag de reemplazo),
`masscan_top_ports`/`nikto_safe`/`nuclei_safe` (bloqueo de CDN Kali, externo
al proyecto), `modbus_s7_discover`/`netdiscover_passive` (comportamiento
esperado por diseño — categoría no autorizada / tipo de param no aplica).

### README
- [x] `docs/alcance-seguridad.md` §2.8 — gobuster_dir, dirb_small, ffuf_dir
      actualizados con las rutas/flags reales y la limitación de wildcard.
      _(2026-07-07)_
- [ ] README: no aplica a masscan/nikto/nuclei/amass/whatweb — son
      limitaciones de entorno externo (red/CDN, paquete upstream), no
      comportamiento del proyecto a documentar como "uso".

---

### Added (2026-07-07 — administración remota SSH, fase 7 — EN DEFINICIÓN)

> **Contexto:** el usuario pidió conectividad SSH real hacia un dispositivo
> propio (distinto del banner grab pasivo que ya hace `nmap_vuln_scripts`).
> Esto es una categoría de riesgo nueva (acceso autenticado, no solo
> reconocimiento), así que se documentó el alcance en
> `docs/alcance-seguridad.md` §2.12 **antes** de escribir el catálogo —
> mismo criterio que el resto del proyecto. Falta un dato del usuario (qué
> comando remoto fijo correr) antes de poder cerrar los ítems marcados
> pendiente.

- [x] **Cliente OpenSSH en `docker/kali/Dockerfile`.** Solo el cliente
      (`openssh-client`) — nunca un servidor SSH dentro del contenedor Kali.
      _(2026-07-07 — no reconstruido aún; pendiente rebuild antes de usar)_
- [x] **Variables `.env` / `.env.example`:** `SSH_REMOTE_HOST`,
      `SSH_REMOTE_USER`, `SSH_REMOTE_KEY_PATH`. **Sin variable de
      contraseña** — solo autenticación por llave, por diseño (ver §2.12
      requisito 1).
      _(2026-07-07)_
- [x] **`config/ssh/` — directorio para la llave privada**, gitignored
      (`config/ssh/*` con excepción de `.gitkeep`/`README.md`), montado
      solo-lectura en el contenedor Kali vía `docker-compose.yml`
      (`./config/ssh:/run/secrets/ssh:ro`).
      _(2026-07-07)_
- [x] **`docs/alcance-seguridad.md` §2.12** — requisitos no negociables
      (solo llave, `BatchMode=yes`, `StrictHostKeyChecking` explícito,
      comando remoto fijo por `tool_id` sin parámetro de texto libre,
      timeout corto, categoría `ssh_remote_ops` en `authorized_targets.yaml`)
      y por qué esto no contradice la exclusión de "post-explotación" en §3.
      _(2026-07-07)_
- [ ] **`tool_id`(s) concretos en `tool_catalog.yaml`** — pendiente de que
      el usuario confirme qué comando(s) remoto(s) fijo(s) necesita (ej.
      `uptime`, `df -h`, chequeo de un servicio específico). Sin esto no hay
      `argv_template` que escribir.
- [ ] **Categoría `ssh_remote_ops` en `security_env/categories.py`** y fila
      de ejemplo en `config/authorized_targets.yaml.example` — se agrega
      junto con el/los `tool_id` de arriba.
- [ ] **Tests** `tests/test_tool_catalog_phase7.py` — mismo formato que las
      fases anteriores, más un test que confirme que ningún `tool_id` de
      esta categoría acepta un parámetro de comando libre.
- [ ] **`docker compose build kali`** — rebuild pendiente para que
      `openssh-client` quede disponible en el contenedor (Dockerfile ya
      actualizado, imagen corriendo todavía no).

### README
- [ ] Sección nueva "Administración remota SSH" — pendiente hasta cerrar
      los ítems de arriba.

---

### Added (2026-07-09 — capa defensiva `defense_env/`, fase 1 — FIM)

> **Contexto:** el usuario pidió comparar el proyecto contra Wazuh (SIEM/XDR
> defensivo) y agregar lo que falta para tener protección real ante un
> ataque. Aclaración honesta antes de listar lo hecho: "superar a Wazuh" no
> es alcanzable en una sesión — es una plataforma con años de desarrollo,
> miles de reglas de correlación y un motor de indexado a escala. Lo que
> **sí** es alcanzable y se arranca acá: un módulo defensivo real,
> incremental, con las mismas bases conceptuales que usa la industria
> (NIST SP 800-94 para el diseño de un IDS/IDPS host-based; formato de
> reglas Sigma + MITRE ATT&CK para que las alertas sean interpretables y
> portables a un SIEM real más adelante si se decide migrar).
>
> Separación deliberada de `security_env/` (capa **ofensiva**, pentesting
> contra objetivos externos autorizados): `defense_env/` es la capa
> **defensiva**, vigila el propio host/proyecto. Son dominios distintos —
> ver el balance completo entregado en la conversación del 2026-07-09.
>
> **Roadmap completo (4 fases) — las 4 quedaron implementadas entre el
> 2026-07-09 (esta entrada) y la entrada siguiente del mismo día:**
> 1. `[x]` **FIM (File Integrity Monitoring)** — baseline + detección de
>    drift sobre archivos críticos propios (`authorized_targets.yaml`,
>    `tool_catalog.yaml`, `docker-compose.yml`, etc.). Implementado en esta
>    entrada; vigilancia continua (sidecar) agregada en la entrada siguiente.
> 2. `[x]` **Motor de correlación de logs** — reglas tipo Sigma simplificado
>    (YAML, filtro de campos + umbral de frecuencia), sobre el audit log de
>    `tool_runner` (recién persistido a disco en esta misma iteración — antes
>    solo vivía en memoria). 2 reglas reales. Ver entrada siguiente.
> 3. `[x]` **Respuesta activa** — circuit breaker fail-closed (lockdown):
>    alerta `critical` bloquea TODA ejecución ofensiva hasta que un humano
>    lo levante explícitamente. Ver entrada siguiente.
> 4. `[x]` **Gestión de casos** — equivalente acotado a TheHive: alerta
>    `critical` abre un caso automáticamente; CLI para listar/crear/cerrar
>    casos manualmente. Ver entrada siguiente.
>
> Fuentes de diseño: [NIST SP 800-94, Guide to Intrusion Detection and
> Prevention Systems](https://csrc.nist.gov/pubs/sp/800/94/final) (categoría
> host-based IDPS: vigilancia de un host individual, no de red);
> [SigmaHQ/sigma](https://github.com/SigmaHQ/sigma) (formato abierto de
> reglas de detección, portable entre SIEMs); MITRE ATT&CK (taxonomía de
> técnicas para que cada alerta declare qué técnica de ataque detecta, no
> solo "algo cambió").

- [x] **`defense_env/models.py`** — Pydantic: `FimBaselineEntry` (ruta,
      hash SHA-256, tamaño, mtime), `FimWatchConfig` (paths + excludes +
      algoritmo de hash), `Alert` (id, timestamp UTC, `severity`
      `low|medium|high|critical`, `mitre_technique` opcional, `rule_id`,
      `description`, `evidence`), `DriftType`
      (`added|modified|deleted|permissions_changed`).
      _(2026-07-09 — `tests/test_defense_fim.py`)_
- [x] **`defense_env/fim.py`** — `compute_baseline(paths)` hashea (SHA-256)
      cada archivo bajo los paths vigilados (respeta `exclude_patterns`,
      usa `fnmatch`) y devuelve un `dict[str, FimBaselineEntry]`;
      `scan_for_drift(baseline, paths)` recalcula el estado actual y
      compara contra el baseline, generando un `Alert` por cada archivo
      agregado, modificado, borrado o con cambio de permisos de escritura
      (`os.access(path, os.W_OK)` más laxo de lo esperado). Severidad:
      `critical` si el archivo modificado es `authorized_targets.yaml` o
      `tool_catalog.yaml` (son los dos archivos que, si se alteran,
      amplían el alcance ofensivo autorizado — la brecha más peligrosa
      posible en este proyecto específico); `high` para el resto de
      archivos vigilados; `medium` para archivos nuevos no vigilados
      previamente que aparecen dentro de un path vigilado.
      _(2026-07-09)_
- [x] **`defense_env/alert_sink.py`** — `append_alert(alert, path)` escribe
      JSONL (mismo patrón que `output/sessions/*.jsonl` del agente LLM,
      por consistencia); `read_alerts(path)` para lectura/tests.
      _(2026-07-09)_
- [x] **`config/defense/fim_watch.yaml`** — vigila por defecto:
      `config/authorized_targets.yaml`, `security_env/tool_catalog.yaml`,
      `security_env/categories.py`, `docker-compose.yml`,
      `docker/kali/Dockerfile` — los archivos cuya alteración silenciosa
      ampliaría el alcance ofensivo o abriría una puerta trasera en el
      contenedor Kali. **No vigila `.env`** (contiene secretos; FIM
      registraría su hash igual, pero no su contenido — se excluye por
      ahora para no complejizar la Fase 1 con manejo de secretos en el
      propio baseline; queda como ítem pendiente explícito abajo).
      _(2026-07-09)_
- [x] **CLI `scraper-agent fim-baseline`** — crea/actualiza
      `output/security/fim_baseline.json` desde `config/defense/
      fim_watch.yaml`. **`scraper-agent fim-scan`** — compara el estado
      actual contra ese baseline, imprime alertas a stdout (severidad +
      técnica MITRE si aplica) y las persiste en
      `output/security/fim_alerts.jsonl`; exit code `1` si hay alguna
      alerta `high`/`critical` (para poder engancharlo a un cron/CI sin
      parsear stdout).
      _(2026-07-09 — `tests/test_defense_fim.py`, casos: sin baseline
      previo, archivo modificado, archivo agregado, archivo borrado, sin
      drift)_
- [x] **Ítem pendiente explícito:** `.env` fuera del alcance de FIM por
      ahora (ver nota arriba) — evaluar hash-only (sin loguear contenido)
      en una iteración siguiente si el usuario lo pide.
      _(2026-07-09 — resuelto, ver entrada ".env sumado a FIM, hash-only")_
- [x] **Ejecución periódica de `fim-scan`** — resuelto en la entrada
      siguiente (sidecar `fim_watcher` en `docker-compose.yml`).

### README
- [x] Sección "Capa defensiva (FIM)" — ver más abajo.

---

### Added (2026-07-09 — capa defensiva `defense_env/`, fases 2-4: correlación, respuesta activa, casos)

> Continuación directa de la entrada anterior (Fase 1 — FIM). El usuario
> pidió seguir con las 4 fases del roadmap. Resumen de lo que se agregó acá,
> en orden de dependencia:

- [x] **Fase 1 (cierre) — vigilancia continua.** Servicio nuevo
      `fim_watcher` en `docker-compose.yml`: reusa la imagen de
      `scraper_agent` (mismo build, sin Dockerfile nuevo), corre
      `fim-baseline` una vez si no existe baseline y después `scraper-agent
      fim-scan` en loop (`sleep "$FIM_SCAN_INTERVAL_SECONDS"`, default 300s,
      configurable por variable de entorno). El `|| true` en el loop es
      deliberado: un exit code 1 (drift detectado) no debe tumbar el
      contenedor ni disparar `restart: unless-stopped` en bucle — el
      watcher tiene que seguir vigilando después de reportar una alerta,
      no reiniciarse. Validado con `docker compose config --quiet`.
      _(2026-07-09)_
- [x] **Fase 2a — gap real encontrado: el audit log de `tool_runner` nunca
      se persistía a disco.** `ToolRunner._audit_log` solo vivía en memoria
      del proceso — se perdía al reiniciar, y sin un log real en disco la
      Fase 2 (correlación) no tenía nada contra qué correlacionar. Fix:
      nuevo parámetro opcional `audit_sink_path` en `ToolRunner.__init__`;
      `_record_audit()` ahora también escribe cada `AuditLogEntry.to_dict()`
      como una línea JSONL en esa ruta (si se configuró), sin tocar el
      comportamiento existente cuando no se pasa (backward-compatible,
      default `None`). Wireado en producción: `agent/tool_handlers.py`
      `_resolve_tool_runner()` ahora pasa
      `audit_sink_path=Path("output/security/tool_audit.jsonl")` — cubre
      tanto la chat API como `scripts/run_pentest.py` (ambos pasan por el
      mismo punto de construcción).
      _(2026-07-09 — `tests/test_tool_runner.py::TestAuditLogPersistence`,
      3 casos: ejecución permitida, rechazo, sin sink configurado)_
- [x] **Fase 2b — motor de correlación tipo Sigma simplificado.**
      `defense_env/models.py` — `CorrelationRule` (id, title, severity,
      logsource, `filter` [igualdad exacta por campo; una lista de valores
      = "campo in lista"], `group_by` opcional, `threshold_count`,
      `window_seconds`, `mitre_technique` opcional). `Alert.drift_type` se
      relajó a opcional (antes solo tenía sentido para FIM; una alerta de
      correlación no tiene "tipo de drift" — `rule_id` identifica el
      origen). `defense_env/correlation.py`: `load_events()` (JSONL),
      `load_rules()` (todos los `*.yaml` de un directorio),
      `evaluate_rule()` — dos modos: `threshold_count<=1` genera una alerta
      por cada evento que matchea (regla de visibilidad, sin agrupar);
      `threshold_count>1` agrupa por `group_by` y busca una ráfaga dentro de
      una ventana deslizante de `window_seconds`, una alerta por grupo en la
      primera ráfaga que cruza el umbral (no una por evento, para no
      inundar de alertas ante un ataque sostenido). `run_correlation()`
      corre varias reglas contra sus logsources respectivos.
      No es una reimplementación del formato Sigma completo
      ([SigmaHQ/sigma](https://github.com/SigmaHQ/sigma)) ni de un motor de
      correlación de producción — es lo suficiente para las reglas de hoy;
      migrar al formato Sigma real sería el siguiente paso si esto crece.
      _(2026-07-09 — `tests/test_defense_correlation.py`, 12 casos)_
- [x] **2 reglas reales** en `defense_env/rules/builtin/`:
      `repeated_authorization_denied.yaml` (3+ rechazos de
      `AuthorizationGuard` del mismo `requested_by` en 5 min → `high`; sin
      `mitre_technique` forzado a propósito — ATT&CK modela técnicas de un
      atacante contra una víctima externa, no alguien sondeando el propio
      guard, y se prefirió dejarlo sin etiquetar antes que forzar un encaje
      que no aplica limpio) y `high_risk_category_executed.yaml`
      (ejecución exitosa en `bounded_fuzzing`/`active_scanning`/
      `known_vuln_scanning`/`ics_scada_recon` → `medium`, regla de
      visibilidad/auditoría). CLI `scraper-agent defense-correlate`
      (`--rules-dir`, `--tool-audit`, `--alerts-out`; exit code 1 si hay
      alerta high/critical).
      _(2026-07-09 — `tests/test_cli_defense_correlate.py`)_
- [x] **Fase 3 — respuesta activa, MVP deliberadamente conservador.**
      `defense_env/active_response.py`: `trigger_lockdown(reason, path)`
      escribe un flag JSON (no sobreescribe un lockdown ya activo — se
      conserva el motivo ORIGINAL, no la última alerta que llegó mientras
      alguien investigaba); `is_locked_down()`, `read_lockdown_reason()`,
      `clear_lockdown()` (acción humana explícita, sin auto-recuperación:
      un lockdown que se levanta solo no protege de nada).
      `AuthorizationGuard.__init__` acepta `lockdown_path` opcional (default
      `None`, backward-compatible); si está seteado y el flag existe,
      `authorize()` deniega TODO antes de mirar `entries` — ni siquiera
      llega a evaluar si el target/categoría normalmente estarían
      autorizados. **Deliberadamente NO se implementó** ninguna acción más
      agresiva (revocar una entrada específica de `authorized_targets.yaml`,
      modificar config automáticamente): un circuit breaker fail-closed es
      seguro por diseño (en el peor caso, bloquea de más); una edición
      automática de la config de autorización podía, en el peor caso,
      dejarla en un estado inconsistente sin que nadie lo note. Wireado:
      `tool_handlers.py` pasa `lockdown_path=Path("output/security/
      LOCKDOWN.json")` (mismo punto que Fase 2a — cubre chat API y
      `run_pentest.py`); `fim-scan` y `defense-correlate` disparan el
      lockdown automáticamente ante cualquier alerta `critical`
      (`--auto-lockdown/--no-auto-lockdown`, default `True`). CLI nuevas:
      `defense-status` (exit 1 si hay lockdown activo, para scripts),
      `defense-clear-lockdown` (requiere `--yes` explícito — no se levanta
      un lockdown por accidente con un flag por defecto).
      _(2026-07-09 — `tests/test_defense_active_response.py` +
      `TestLockdown` en `tests/test_authorization_guard.py` +
      `tests/test_cli_lockdown.py`, 21 casos en total)_
- [x] **Fase 4 — gestión de casos, equivalente acotado a TheHive.**
      `defense_env/models.py` — `Case` (id, title, status
      `open|investigating|closed`, severity, created_at/updated_at,
      `alert_ids[]`, `notes[]`). `defense_env/cases.py`: almacenamiento en
      un único JSON (`output/security/cases.json`, lista completa
      leída/reescrita en cada operación — suficiente al volumen de alertas
      de hoy; si crece, el siguiente paso sería SQLite, no un rediseño).
      `create_case()`, `list_cases()` (filtro por status), `close_case()`
      (nota opcional), `add_note()`, `auto_create_case_from_alert()` — abre
      un caso SOLO para alertas `critical` (el resto queda en el JSONL de
      alertas crudo, visible pero sin abrir una investigación por evento
      menor — eso sería ruido, no gestión de casos). Wireado en `fim-scan` y
      `defense-correlate`: alerta `critical` → caso + lockdown, en ese
      orden. CLI: `defense-case-list` (filtro `--status`),
      `defense-case-create` (manual), `defense-case-close` (acepta prefijo
      de id, exige id no ambiguo).
      _(2026-07-09 — `tests/test_defense_cases.py` + `tests/test_cli_cases.py`
      + casos de auto-creación en `tests/test_cli_lockdown.py`, 14 casos)_
- [x] **Bug de aislamiento de tests encontrado y corregido en el camino:**
      `tests/test_cli_fim.py::test_fim_scan_exits_nonzero_when_critical_drift`
      (escrito en la Fase 1, antes de que existieran Fases 3/4) no pasaba
      `--lockdown-path`/`--cases-path` — al agregar el auto-lockdown/
      auto-caso, ese test empezó a escribir en el `output/security/
      LOCKDOWN.json` y `cases.json` **reales** del proyecto en cada corrida
      de la suite (contaminación confirmada y limpiada: ambos archivos
      contenían rutas de `tmp_path` de pytest, no cambios reales del
      proyecto). Fix: el test ahora aísla ambas rutas en `tmp_path`, igual
      que el resto de los tests de este archivo.
      _(2026-07-09)_
- [x] Suite completa re-verificada tras las 4 fases: `pytest -q` → **250/250
      passed**; `ruff check src tests` → limpio; smoke test manual contra el
      proyecto real (`fim-baseline`, `fim-scan`, `defense-correlate`,
      `defense-status`, `defense-case-list`) confirmando que
      `output/security/` queda limpio después de correr la suite.

### README
- [x] Sección "Capa defensiva (FIM)" ampliada con Fases 2-4 (correlación,
      lockdown, casos) — ver más abajo.

---

### Added (2026-07-09 — `fim_watcher` en producción: 2 bugs reales encontrados y corregidos)

> Al levantar `docker compose up -d fim_watcher` por primera vez (pedido
> explícito del usuario tras cerrar las 4 fases), el propio watcher expuso
> dos bugs reales que ningún test había cubierto porque los tests corren
> todos en la misma plataforma/mismo filesystem — recién se vieron al
> correr el contenedor de verdad.

- [x] **Bug 1 — claves de FIM no portables entre SO.** `_snapshot()` en
      `fim.py` usaba `str(path)`, que renderiza con el separador nativo del
      SO (`\` en Windows, `/` en Linux). El baseline se había generado a
      mano en el host (Windows) y el watcher corre en el contenedor
      (Linux) — mismo archivo, dos claves distintas, así que CADA archivo
      vigilado aparecía como "borrado" (clave vieja con `\`) Y "agregado"
      (clave nueva con `/`) al mismo tiempo (8 alertas falsas en el primer
      log). Fix: todas las claves (y `FimBaselineEntry.path`) usan
      `.as_posix()` sin importar el SO.
      _(2026-07-09 — `tests/test_defense_fim.py::test_keys_are_platform_independent_posix_style`)_
- [x] **Bug 2 — `docker-compose.yml` y `docker/kali/Dockerfile` invisibles
      dentro del contenedor, en silencio.** El servicio `fim_watcher` solo
      montaba `./output` y `./config` — los otros 2 de los 5 paths de
      `config/defense/fim_watch.yaml` viven fuera de `config/`, así que
      `_iter_watched_files()` los salteaba (ni error ni advertencia: el
      baseline "funcionaba" con 3 de 5 archivos). Fix: `docker-compose.yml`
      y `docker/` ahora se montan explícitamente en `fim_watcher` a la
      misma ruta relativa que usa la config. **Además**, se agregó
      `missing_watched_paths()` en `fim.py` (y se cableó en `fim-baseline`/
      `fim-scan`) para que una ruta vigilada ausente se reporte como
      ADVERTENCIA explícita en vez de desaparecer en silencio — la próxima
      vez que un mount falte, se va a notar de inmediato.
      _(2026-07-09 — `tests/test_defense_fim.py::TestComputeBaseline::test_missing_watched_paths_*`)_
- [x] **Verificación en vivo tras ambos fixes:** `docker compose stop
      fim_watcher` → limpiar baseline/alertas viejos → `docker compose up
      -d --build fim_watcher` → logs confirmando `Baseline generado: 5
      archivo(s)` (antes: 3) y `Sin drift` en los siguientes 2-3 ciclos de
      5 minutos, sin advertencias de rutas faltantes.
      Suite completa re-verificada: `pytest -q` → **253/253 passed**;
      `ruff check src tests` → limpio; `docker compose config --quiet` → OK.

---

### Added (2026-07-09 — `defense-correlate` sumado al loop continuo)

> Gap identificado al preguntar "¿algo por implementar?": `fim_watcher`
> vigilaba archivos cada 5 min, pero la Fase 2 (correlación) solo corría si
> alguien la disparaba a mano — un patrón de rechazos repetidos podía pasar
> un fin de semana entero sin que nadie se enterara.

- [x] **Servicio `fim_watcher` renombrado a `defense_watcher`** en
      `docker-compose.yml` — ahora corre `fim-scan` **y**
      `scraper-agent defense-correlate` en el mismo loop (ambas son
      comandos livianos de la misma imagen; dos contenedores separados no
      se justificaban). Variable de entorno renombrada
      `FIM_SCAN_INTERVAL_SECONDS` → `DEFENSE_SCAN_INTERVAL_SECONDS` (mismo
      default, 300s).
      _(2026-07-09)_
- [x] **Migración del contenedor viejo:** `docker stop`/`rm
      tarea1-fim_watcher-1` (compose ya no reconoce el nombre de servicio
      viejo tras el rename, hay que bajarlo por nombre de contenedor
      directo) → `docker compose up -d --build defense_watcher`.
      Verificado en logs: primer ciclo corrió `fim-scan` (detectó,
      correctamente, que `docker-compose.yml` había cambiado por este mismo
      rename — no un falso positivo, un drift real) y `defense-correlate`
      ("Sin coincidencias", esperado con `tool_audit.jsonl` sin actividad
      reciente). Baseline regenerado dentro del contenedor
      (`docker exec ... scraper-agent fim-baseline`) para capturar el
      cambio legítimo.
      _(2026-07-09)_
- [x] `README.md` actualizado: sección 1 (FIM) y sección 2 (correlación)
      reflejan que ambas corren en `defense_watcher`, sin necesidad de
      disparar `defense-correlate` a mano en producción.
      Suite re-verificada: `pytest -q` → **253/253 passed**; `ruff check
      src tests` → limpio.

---

### Added (2026-07-09 — `.env` sumado a FIM, hash-only)

> Último ítem pendiente explícito de la entrada original de FIM (2026-07-09).
> El usuario pidió cerrarlo. Reconsiderando el motivo original ("no
> complejizar la Fase 1 con manejo de secretos"): resultó ser una
> preocupación infundada — FIM nunca leyó ni almacenó contenido de ningún
> archivo desde el día 1, solo `hashlib.sha256` sobre los bytes. No hacía
> falta ningún modo especial "hash-only" nuevo: ya era así para todos los
> archivos vigilados. Un SHA-256 de un archivo `.env` completo (múltiples
> líneas `KEY=VALUE`) no es reversible al contenido original.

- [x] **`config/defense/fim_watch.yaml`**: `.env` agregado a `paths` y a
      `critical_files` (junto a `authorized_targets.yaml`/`tool_catalog.yaml`
      — tampering en `.env` puede cambiar `DEEPSEEK_API_KEY`, `PROXY_LIST`,
      `SSH_REMOTE_*`, tan sensible como los otros dos).
      _(2026-07-09)_
- [x] **Mount nuevo en `defense_watcher`** (`docker-compose.yml`):
      `./.env:/app/.env:ro`. Necesario porque `env_file:` de Compose solo
      **inyecta las variables ya resueltas** al proceso — no monta el
      archivo en el filesystem del contenedor. Sin este mount, `.env`
      hubiera sido otra "ruta vigilada no encontrada" silenciosa (mismo bug
      que `docker-compose.yml`/`docker/` de una entrada anterior). No es una
      exposición nueva: los VALORES de `.env` ya estaban en el entorno de
      ese contenedor por `env_file:` desde el principio — este mount solo
      expone los BYTES crudos del archivo para que FIM los pueda hashear.
      _(2026-07-09)_
- [x] **Verificado en vivo, no solo en tests:** `fim-baseline` regenerado
      (host, 6 archivos ahora) → confirmado que `output/security/
      fim_baseline.json` solo tiene `path`/`sha256`/`size_bytes`/`mtime`
      para `.env`, cero contenido → `docker stop`/`rm` +
      `docker compose up -d --build defense_watcher` → `docker exec ...
      ls -la /app/.env` confirma el mount → logs: `Sin drift` / `Sin
      coincidencias` (mismo SHA-256 en host y contenedor — el hash de
      contenido nunca dependió del SO, solo la CLAVE del diccionario lo
      necesitaba, ya arreglado en la entrada de los 2 bugs de producción).
      Suite completa: `pytest -q` → **253/253 passed**; `ruff check src
      tests` → limpio.
- [x] `README.md` actualizado: sección 1 (FIM) documenta la cobertura de
      `.env` y el mount necesario; quitada de "Limitaciones honestas" (ya
      no aplica).

---

### Añadido — plan: aislar al atacante real (no solo a `tarea1`) + 5 detectores

> **Corrección importante señalada por el usuario:** el lockdown de la Fase 3
> detiene la ejecución ofensiva **del propio `tarea1`** — tiene sentido si
> `tarea1` mismo fue comprometido y alguien lo usa de arma, pero **no hace
> nada contra un atacante externo** atacando la infraestructura de `tarea1`
> (host, contenedores). No lo aísla, no lo expulsa, no le corta nada. Gap
> real, no un matiz — se corrige acá con una respuesta activa nueva y
> distinta (aislamiento de red del contenedor comprometido), que convive con
> el lockdown existente (cada uno resuelve un escenario distinto).
>
> El usuario también pidió cubrir 5 capacidades que hoy `tarea1` NO tiene
> (tabla de balance entregada en la conversación): fugas de información,
> backdoors, botnets, exploits, ransomware. Se cubren con MVPs honestos y
> acotados — no con la promesa de un EDR/XDR completo (eso sigue sin ser
> alcanzable, mismo techo que la comparación contra Wazuh del inicio).
>
> **Plan (5 piezas) — las 5 quedaron implementadas el mismo día (2026-07-09),
> detalle completo en la entrada siguiente:**
> 1. `[x]` **Aislamiento de red del contenedor comprometido**
>    (`container_isolation.py`) — `docker network disconnect` real vía el
>    `docker.sock` ya montado en `scraper_agent`. Disparado por cualquiera
>    de los detectores nuevos (no por el lockdown de Fase 3, que sigue
>    siendo un mecanismo distinto). Acción humana requerida para reconectar
>    (mismo criterio que `defense-clear-lockdown`: sin auto-recuperación).
> 2. `[x]` **Ransomware — detector de ráfaga de cambios de archivo.**
>    Extiende `fim.py`: si N+ archivos cambian en una ventana corta, alerta
>    `critical` (patrón de cifrado masivo). Nota de alcance: FIM solo vigila
>    los paths de `fim_watch.yaml`, no toda la máquina — ver limitación
>    explícita en la sección de esa pieza.
> 3. `[x]` **Backdoors — cobertura de FIM ampliada.** `src/scraper_agent/`
>    completo (recursivo) además de los archivos puntuales de hoy — cualquier
>    `.py` nuevo o modificado fuera de un commit/despliegue legítimo es
>    señal de código insertado.
> 4. `[x]` **Fugas de información — canary files (honeytokens).** Archivos
>    señuelo en ubicaciones creíbles; si alguien los toca (modifica/mueve/
>    borra), alerta `critical`. Técnica establecida (canarytokens.org usa la
>    misma idea), acotada a filesystem — no detecta una fuga que nunca toque
>    un señuelo, y la detección de solo-lectura (`atime`) se evaluó y se
>    descartó a propósito por no ser confiable entre filesystems.
> 5. `[x]` **Exploits — self-scan defensivo.** Reusa el catálogo de
>    `security_env/` (ya construido, ofensivo) contra los propios
>    contenedores (IP real resuelta vía `docker inspect`) en vez de
>    objetivos externos — mismas herramientas, target distinto.
> 6. `[ ]` **Botnets — NO se implementa en este ciclo.** Requiere análisis
>    de tráfico de red (beaconing C2, DNS) para el que no hay visibilidad
>    de red real en este entorno (Docker Desktop en Windows, sin acceso a
>    la interfaz de red del host). Declarado explícitamente como fuera de
>    alcance en vez de simular una detección que no sería honesta — ver
>    nota de cierre de esta entrada.

---

### Added (2026-07-09 — 5 detectores implementados: aislamiento, ransomware, backdoors, canary, self-scan)

> Continuación directa de la entrada anterior. Las 5 piezas del plan
> quedaron implementadas y verificadas contra la infraestructura real
> (no solo tests) en la misma sesión.

- [x] **`defense_env/container_isolation.py`** — `isolate_container()` /
      `reconnect_container()` / `is_isolated()`. `docker network disconnect`
      real vía subprocess sobre el binario `docker` (mismo patrón que
      `security_env/docker_executor.py`, sin agregar el SDK de Python de
      Docker). Idempotente (no repite la desconexión ni pisa el motivo
      original) y sin auto-recuperación (reconectar es una acción humana
      explícita, mismo criterio que `clear_lockdown`). Runner inyectable
      para tests (mismo patrón `FakeExecutor` que el resto del proyecto).
      _(2026-07-09 — `tests/test_defense_container_isolation.py`, 9 casos)_
- [x] **`defense_env/ransomware_detector.py`** — `detect_ransomware_pattern()`:
      si 5+ (default) alertas MODIFIED/DELETED aparecen en el MISMO ciclo de
      `scan_for_drift()`, emite una alerta meta `critical` etiquetada MITRE
      `T1486` (Data Encrypted for Impact — mapeo real y directo, a
      diferencia de la regla de correlación anterior donde se evitó forzar
      un mapeo que no encajaba limpio). Alertas ADDED no cuentan (ransomware
      cifra/borra, no agrega). Cableado en `fim-scan`: al detectarse, abre
      un caso automático Y (`--auto-isolate`, default on) aísla de red el
      contenedor configurado (`--isolation-container`, default el
      contenedor con puerto expuesto al host) — **distinto** del lockdown
      de Fase 3: esto responde al atacante externo, no autobloquea a
      `tarea1`. Comandos nuevos: `defense-isolation-status`,
      `defense-reconnect --yes`.
      _(2026-07-09 — `tests/test_defense_ransomware.py` (6 casos) +
      `tests/test_cli_ransomware_isolation.py` (7 casos, con contenedor/red
      falsos a propósito para no tocar infraestructura real al testear)_
- [x] **`config/defense/fim_watch.yaml`** ampliado: `src/scraper_agent`
      completo (recursivo) reemplaza las 2 entradas puntuales de
      `tool_catalog.yaml`/`categories.py` (ya cubiertas por el path
      recursivo). Deliberadamente NO se agregó a `critical_files` — el
      código cambia legítimamente todo el tiempo en desarrollo activo,
      forzar `critical` ahí sería puro ruido. `exclude_patterns` nuevo:
      `*.pyc`/`*.pyo` (bytecode regenerado en cada corrida). Verificado:
      87 archivos en el baseline, cero `.pyc` filtrados, `fim-scan` limpio.
      _(2026-07-09)_
- [x] **`defense_env/canary.py`** — honeytokens. `deploy_canaries()` crea
      archivos señuelo con contenido de cebo realista (credenciales/targets
      falsos pero con formato creíble) en ubicaciones sin ningún uso
      legítimo; `check_canaries()` reusa `fim.scan_for_drift()` sobre ese
      scope reducido (no reimplementa detección de integridad) y retagea
      CUALQUIER drift como `critical` + MITRE `T1005` (Data from Local
      System) — a diferencia de FIM normal, un canary no tiene ningún
      cambio legítimo posible. Comandos: `defense-canary-deploy` /
      `defense-canary-check`. **Limitación declarada y no implementada a
      propósito**: detección de solo-LECTURA vía `atime` — evaluada y
      descartada porque muchos filesystems/montajes (`noatime`, overlay de
      Docker, NTFS por defecto) no actualizan `atime` de forma confiable en
      cada lectura; implementarla hubiera dado una falsa sensación de
      cobertura.
      _(2026-07-09 — `tests/test_defense_canary.py` (7 casos) +
      `tests/test_cli_canary.py` (3 casos))_
- [x] **`defense_env/self_scan.py`** — self-scan defensivo. Reusa el
      catálogo OFENSIVO de `security_env/` (mismas herramientas del
      pentest) contra la propia infraestructura: `resolve_container_ip()`
      resuelve la IP real del contenedor objetivo vía `docker inspect`
      (dinámica -- Docker reasigna IPs al recrear la red, así que NO se
      hardcodea un CIDR en config estático); `build_self_scan_guard()`
      construye una autorización efímera EN MEMORIA (nunca toca
      `config/authorized_targets.yaml`, la lista real de objetivos externos
      del usuario), acotada a categorías livianas (`passive_recon`,
      `light_active_scan`). `run_self_scan()` corre cada tool_id y no aborta
      si una falla. Comando `defense-self-scan`.
      _(2026-07-09 — `tests/test_defense_self_scan.py`, 6 casos con
      `FakeExecutor`, sin tocar Kali real)_

#### 3 bugs reales encontrados corriendo `defense-self-scan` de verdad (no en tests)

- [x] **Nombre de contenedor por defecto incorrecto.** `DEFAULT_ISOLATION_CONTAINER`
      era `"scraper_agent"` (nombre de *servicio* de compose) — pero
      `docker inspect`/`network disconnect` necesitan el nombre de
      *contenedor* real, que Compose v2 arma como
      `<proyecto>-<servicio>-<réplica>` (acá: `tarea1-scraper_agent-1`).
      Afectaba tanto a `defense-self-scan` como al aislamiento por
      ransomware — ambos hubieran fallado con "no such object" en
      producción. Fix: constante corregida, con nota explícita de que
      asume que nadie corrió `docker compose -p <otro-nombre>`.
      _(2026-07-09)_
- [x] **Fallback silencioso a `FakeExecutor` — el más serio de los tres.**
      `defense-self-scan` usaba `resolve_command_executor()` (pensado para
      producción normal: cae a `FakeExecutor` si falta `KALI_CONTAINER` en
      el entorno). Corriendo el comando desde el host sin esa variable
      seteada, el self-scan **"funcionaba"** — exit code 0, sin error — pero
      devolvía resultados de prueba fabricados (`stdout: "ok"`) en vez de
      ejecutar algo real contra Kali. Una falsa sensación de seguridad
      **peor** que un error explícito: alguien podría correr un self-scan,
      ver "todo OK" y confiar en eso sin saber que nunca se ejecutó nada de
      verdad. Fix: `defense-self-scan` ahora construye `DockerCliExecutor`
      directo (nunca `resolve_command_executor()`) — si Kali no está
      disponible, falla ruidosamente.
      _(2026-07-09)_
- [x] **`curl_headers` no aplica bien contra `scraper_agent`** (no es un
      bug de esta entrega, es un hallazgo real y documentado): esa
      herramienta del catálogo asume `https://{host}` fijo
      (`tool_catalog.yaml`), pero `scraper_agent` sirve HTTP plano en el
      puerto 8000 (sin TLS propio). El self-scan lo reporta como
      `exit_code 7` / "Failed to connect... port 443" — resultado correcto
      y esperado, no un fallo del self-scan; queda como ejemplo de por qué
      "revisión humana" es parte del contrato del comando (no interpreta
      el hallazgo, lo entrega crudo).

- [x] **Verificación en vivo, extremo a extremo:** `defense-self-scan`
      corrido de verdad contra `tarea1-scraper_agent-1` (IP resuelta
      `192.168.16.3`) → `nmap_top100` confirma exactamente `8000/tcp open
      http-alt` y nada más (superficie de ataque real, sin sorpresas).
      Suite completa: `pytest -q` → **291/291 passed**; `ruff check src
      tests` → limpio.

---

### Añadido — plan: defensa activa a nivel de sistema operativo (Linux, servidor real)

> **Corrección de alcance señalada por el usuario, dos vueltas seguidas:**
> 1. El lockdown/aislamiento de las entradas anteriores solo actúan sobre
>    contenedores Docker propios de `tarea1` — nunca tocan el sistema
>    operativo del host. El usuario preguntó explícitamente qué pasa si
>    atacan el sistema operativo (no solo el contenedor), y la respuesta
>    honesta fue: nada, no hay ninguna capacidad ahí.
> 2. El usuario aclaró el objetivo real: su entorno de desarrollo es
>    Windows, pero el sistema operativo que necesita defender de verdad es
>    **Linux (CentOS/RHEL) en su servidor de producción** — no Windows.
>    Pidió además que la detección de sistema operativo y de qué
>    herramientas de firewall/proceso hay disponibles sea **automática**
>    (no asumir una herramienta fija), porque no tiene la lista de qué
>    puede haber instalado.
>
> **Alcance de esta pieza**: `defense_env/host_defense.py` — detección de
> distro + herramienta de firewall disponible, y 3 acciones defensivas
> concretas pedidas explícitamente por el usuario ("cerrar puerto y cerrar
> conexión, matar aplicaciones"): `block_ip`, `close_port`, `kill_process`.
> Prioridad de firewall: `firewalld` (default en RHEL/CentOS 7+) →
> `nftables` → `iptables` — se detecta cuál está REALMENTE instalado en
> ese host, no se asume ninguna.
>
> **Limitación honesta declarada desde el arranque, no descubierta
> después**: este entorno de desarrollo es Windows — no hay un CentOS/RHEL
> real disponible en esta sesión para probar contra infraestructura real
> (a diferencia de FIM/aislamiento/self-scan, que sí se verificaron contra
> los contenedores Docker reales de este proyecto). El código se desarrolla
> con TDD y runners inyectables/falsos (mismo patrón que el resto de
> `defense_env/`), pero **sin el smoke test real** que valida las otras
> piezas. Antes de confiar en esto en producción: correr
> `defense-host-detect` en el servidor real primero y revisar el resultado.
>
> **Riesgo declarado explícitamente**: a diferencia de todo lo anterior
> (que actúa sobre contenedores descartables), estas acciones corren con
> privilegios de root/sudo sobre el sistema operativo REAL de producción.
> No hay reversión automática de `block_ip`/`close_port`/`kill_process` —
> son irreversibles por diseño salvo que un humano deshaga la regla de
> firewall a mano (mismo criterio de "sin auto-recuperación" que el resto
> de `defense_env/`, pero acá el radio de impacto es mayor).

- [x] **`defense_env/host_defense.py`** — `detect_os()` (parsea
      `/etc/os-release`; `is_linux=False` sin fallar si no existe, ej.
      corriendo en Windows); `detect_firewall_tool()` (prioridad
      `firewalld` → `nftables` → `iptables`, detecta cuál está REALMENTE
      instalado vía `which`); `block_ip()` / `close_port()` (usan la
      herramienta detectada, cada una con su sintaxis real: `firewall-cmd
      --zone=drop --add-source`, `nft add rule ... drop`, `iptables -I
      INPUT ... -j DROP`); `kill_process()` (`kill -9` por pid, `pkill -9
      -f` por nombre — coincide contra la línea de comando completa);
      `list_connections()` (`ss` preferido sobre `netstat`, deprecado en
      RHEL/CentOS modernos — devuelve líneas crudas, sin parser
      estructurado por columnas: no se pudo verificar el formato exacto
      contra un RHEL real desde este entorno Windows, y un parser
      "aproximado" sin verificar sería peor que ninguno). Mismo patrón de
      runner inyectable que el resto de `defense_env/` (`FakeExecutor`
      equivalente para tests, subprocess real por default).
      _(2026-07-09 — `tests/test_defense_host_defense.py`, 18 casos)_
- [x] **CLI**: `defense-host-detect` (corre primero, sin acción — solo
      diagnóstico), `defense-host-block-ip <ip> --yes`,
      `defense-host-close-port <puerto> --yes`,
      `defense-host-kill-process --pid/--name --yes`,
      `defense-host-connections` (solo lectura, sin confirmación). Las 3
      acciones destructivas exigen `--yes` explícito (mismo criterio que
      `defense-clear-lockdown`/`defense-reconnect` — no se ejecuta una
      acción irreversible sobre el sistema operativo real por accidente).
      _(2026-07-09 — `tests/test_cli_host_defense.py`, 8 casos con
      `detect_os`/`detect_firewall_tool`/acciones mockeadas a nivel de
      módulo — correrlas reales hubiera ejecutado `which`/`firewall-cmd`
      de verdad contra esta máquina Windows de desarrollo)_
- [x] **Verificado en esta máquina (Windows, no el objetivo real)**:
      `defense-host-detect` corrido de verdad — reporta correctamente
      "no parece un host Linux" y "sin firewalld/nftables/iptables
      disponibles", sin excepción no controlada. **No sustituye** una
      verificación contra un CentOS/RHEL real — pendiente explícito antes
      de usar esto en producción.
      Suite completa: `pytest -q` → **317/317 passed**; `ruff check src
      tests` → limpio.

### Pendiente

- [ ] **Verificación contra un CentOS/RHEL real** — todo lo de esta
      entrada se validó con runners falsos, nunca contra un servidor Linux
      de verdad. Antes de usar `defense-host-block-ip`/`close-port`/
      `kill-process` en producción: correr `defense-host-detect` primero
      y confirmar que detecta la herramienta de firewall esperada.
- [ ] **`list_connections()` sin parser estructurado** — devuelve líneas
      crudas de `ss`/`netstat`; parsear columnas (IP, puerto, PID, proceso)
      de forma confiable requiere verificar el formato exacto contra un
      RHEL real primero.
- [ ] **Sin integración automática con los detectores existentes** (FIM,
      ransomware, canary) — hoy `defense-host-*` son comandos manuales,
      no se disparan solos ante una alerta `critical`. Evaluar si conviene
      antes de automatizar una acción irreversible a nivel de sistema
      operativo real.

---

### Añadido — plan: cerrar la brecha de SO continuo + candidatos a pybind11 + framework de "% de cobertura"

> **Contexto**: comparación explícita Wazuh vs. `tarea1` a nivel de sistema
> operativo (conversación del usuario). Conclusión honesta: tenemos las
> *acciones* (`block_ip`/`close_port`/`kill_process`) pero no la
> *detección continua* que las dispararía sola — es un extintor colgado en
> la pared, no un sistema de detección de humo conectado a los aspersores.
>
> **Objetivo declarado del usuario**: antes de subir `tarea1` a una máquina
> virtual real que quiere proteger de ataques activos, identificar al
> atacante, y usar pentesting si hace falta. Pidió además migrar las
> piezas que tenga sentido a C/C++ vía `pybind11` para que `tarea1` sea
> más liviano/eficiente.

#### Framework de "% de cobertura aceptable" (para saber cuándo subir a la VM)

No existe un número mágico único — se define como una lista de
capacidades concretas, cada una con su propio estado. "Aceptable para
subir a una VM real" significa, como mínimo, los ítems marcados
**[mínimo para producción]** resueltos — el resto son mejoras
incrementales que pueden seguir después de subir el sistema.

| # | Capacidad | Estado antes de esta entrada | Prioridad |
|---|---|---|---|
| 1 | FIM sobre archivos críticos del SO (no solo el proyecto) | `[ ]` | **mínimo para producción** |
| 2 | Detección de fuerza bruta SSH (logs de autenticación) | `[ ]` | **mínimo para producción** |
| 3 | Agente continuo (loop 24/7, no CLI bajo demanda) | `[ ]` | **mínimo para producción** |
| 4 | Respuesta activa automática (fuerza bruta → `block_ip` solo) | `[ ]` | **mínimo para producción** |
| 5 | Identificación de atacante (recon pasivo automático sobre la IP de origen) | `[ ]` | **mínimo para producción** |
| 6 | Detección de rootkits | `[ ]` | deseable, no bloqueante |
| 7 | SCA / CIS Benchmarks (hardening del SO) | `[ ]` | deseable, no bloqueante |
| 8 | Auditoría a nivel de syscall (`auditd` profundo) | `[ ]` | deseable, no bloqueante |
| 9 | Dashboard centralizado / multi-host | `[ ]` | fuera de alcance (un solo host, un solo operador) |

Esta entrada cubre los ítems 1-5 (el "mínimo para producción" completo).
6-8 quedan documentados como roadmap explícito, no implementados en este
ciclo — ver sección "Pendiente" al final.

#### Candidatos a migración C/C++ + pybind11

Evaluados los módulos de `defense_env/` uno por uno:

| Módulo | ¿Candidato? | Por qué |
|---|---|---|
| `fim.py` (hashing + snapshot) | **Sí — implementado en esta entrada** | Es el único hot-path real: hashear cientos/miles de archivos del SO completo (a diferencia del scope actual de ~87 archivos del proyecto) implica I/O + CPU repetido. Ganancia real: evitar el overhead de crear un objeto Pydantic `FimBaselineEntry` por archivo en el loop caliente de escaneo, y usar lectura de buffer fija en C++ en vez de `Path.open("rb")` + `iter()` de Python. |
| `correlation.py` (motor de reglas) | No, todavía | El volumen de eventos hoy (audit log de `tool_runner`, logs de auth) es bajo (cientos, no millones de líneas) — Python alcanza. Reevaluar si el volumen de logs de auditd/journald en producción resulta ser mucho mayor. |
| `container_isolation.py` / `host_defense.py` (acciones) | No | Son wrappers de subprocess sobre binarios externos (`docker`, `firewall-cmd`, `kill`) — el costo real está en el binario externo, no en Python. Migrar el wrapper a C++ no cambia nada. |
| `canary.py` / `cases.py` (I/O de archivos JSON chicos) | No | Volumen y frecuencia bajos — no hay overhead medible que migrar. |

**Decisión**: un solo candidato real, `fim.py`. Se implementa como extensión
`pybind11` opcional con **fallback automático a la implementación Python
pura** si la extensión compilada no está disponible (ej. este entorno de
desarrollo Windows, sin toolchain de C++ instalado, o un servidor de
producción sin `gcc`/herramientas de build) — nunca un requisito duro.

**Limitación honesta**: este entorno de desarrollo (Windows) no tiene
compilador de C/C++ ni `pybind11` instalados (`cl.exe`/`gcc`/`g++`: no
encontrados). La extensión se compila y verifica **dentro del contenedor
Docker** (que sí tiene un toolchain Linux real vía `build-essential`) —
más representativo del destino real de producción (Linux) que intentar
instalar un compilador en Windows para algo que nunca correrá ahí.

---

### Añadido — implementación completa: FIM del SO, fuerza bruta SSH, agente continuo, identificación de atacante, pybind11

> Continuación directa de la entrada anterior. Los 5 ítems "mínimo para
> producción" del framework de cobertura quedaron implementados y
> **verificados de verdad** (no solo con runners falsos) donde fue posible.

- [x] **#1 FIM del SO** — `config/defense/host_fim_watch.yaml` (nuevo,
      separado de `fim_watch.yaml` de proyecto): `/etc/passwd`,
      `/etc/shadow`, `/etc/ssh/sshd_config`, `/etc/sudoers`, `/etc/crontab`,
      `/etc/cron.d`, `/etc/cron.daily`, `/etc/cron.hourly`,
      `/root/.ssh/authorized_keys` — todos `critical`. Reusa el motor de
      `fim.py` sin ningún cambio de código (ya era genérico sobre paths).
      **Cómo correrlo de verdad**: documentado en el propio YAML — nativo
      en la VM funciona directo; dentro de un contenedor necesita bind-
      mount explícito del `/etc` REAL del host (no el del contenedor).
      Verificado en este entorno Windows: `missing_watched_paths()` reporta
      correctamente las 9 rutas como ausentes (comportamiento esperado,
      no hay `/etc/passwd` en Windows), sin crashear.
      _(2026-07-09)_
- [x] **#2 Fuerza bruta SSH** — `defense_env/auth_log_parser.py`:
      `parse_ssh_auth_line()`/`parse_ssh_auth_log()` parsean el formato
      syslog estándar de `sshd` (RHEL/CentOS: `/var/log/secure`) a eventos
      que el motor de correlación YA EXISTENTE consume directo (sin
      reimplementar umbral/ventana). Regla nueva
      `rules/builtin/ssh_brute_force.yaml`: 5+ fallos desde la misma IP en
      2 min → `critical`, MITRE `T1110` (Brute Force — mapeo directo y
      correcto, a diferencia de `repeated_authorization_denied.yaml` que
      deliberadamente no tiene técnica asignada). Verificado con un smoke
      test real: 6 líneas de log sintéticas → dispara en la 5ta,
      `evidence.source_ip` correcto.
      _(2026-07-09 — `tests/test_defense_auth_log.py`, 8 casos)_
- [x] **#5 Identificación de atacante** — `defense_env/attacker_recon.py`:
      mismo patrón que `self_scan.py` pero autorizando la IP del ATACANTE
      (no la propia infraestructura), acotado a `passive_recon` únicamente
      (`whois`/`dig_a`) — nunca nada más agresivo contra esa IP, porque
      eso sería contraatacar sin autorización legal sobre un objetivo que
      no es nuestro (fuera de alcance a propósito).
      _(2026-07-09 — `tests/test_defense_attacker_recon.py`, 4 casos)_
- [x] **#3 + #4 Agente continuo + respuesta automática** —
      `defense_env/host_agent.py`: `run_host_agent_cycle()` une FIM del
      host + correlación de fuerza bruta SSH + `block_ip` AUTOMÁTICO
      (cierra el gap "100% manual" señalado en el balance contra Wazuh) +
      identificación de atacante, en un solo ciclo. Deliberadamente: **solo**
      la regla `ssh_brute_force` dispara bloqueo automático — una alerta
      `critical` de FIM abre caso pero no bloquea nada sola (no trae una
      IP de origen confiable para actuar). CLI `defense-host-agent-cycle`
      (un ciclo, pensado para cron/systemd). Dos formas de correrlo en
      loop: `scripts/host_agent_loop.sh` (bash, cualquier Linux) o
      `scripts/tarea1-host-agent.service` (systemd, RHEL/CentOS — usa
      `Restart=always` de systemd como el loop, no un script propio).
      _(2026-07-09 — `tests/test_defense_host_agent.py` (6 casos) +
      `tests/test_cli_host_agent.py` (2 casos))_
- [x] **pybind11 — extensión nativa de FIM, COMPILADA Y VERIFICADA de
      verdad dentro de Docker** (no solo diseñada): `_fim_native/fim_hash.cpp`
      (SHA-256 vía la API EVP de OpenSSL — no las funciones `SHA256_*` de
      bajo nivel, deprecadas en OpenSSL 3.x). `fim.py` detecta la extensión
      con try/except + `hasattr(..., "hash_files")` y cae a `hashlib` puro
      si no está. `setup.py` nuevo (build opcional, nunca bloquea
      `pip install -e .` si pybind11/el compilador faltan). Dockerfile:
      `build-essential`/`libssl-dev`/`python3-dev` + paso de build en un
      `RUN` separado con `|| true` (un fallo ahí nunca tumba la imagen
      completa).
      _(2026-07-09)_

#### 3 bugs reales encontrados compilando/verificando esto de verdad

- [x] **Namespace package falso positivo.** `_fim_native/` sin
      `__init__.py` se importa SIN ERROR como paquete de namespace vacío
      (PEP 420) — el `try/except ImportError` solo no alcanzaba para
      detectar si la extensión estaba de verdad compilada. Fix:
      `hasattr(_fim_native, "hash_files")` además del import exitoso.
      Encontrado corriendo los tests de FIM en Windows tras agregar la
      extensión (10 de 16 tests fallaron con `AttributeError`).
- [x] **`setuptools` no queda instalado tras `pip install -e .`.**
      `python setup.py build_ext --inplace` corre FUERA del entorno de
      build aislado que usa `pip install` (PEP 517) — ese aislamiento
      instala `setuptools` temporalmente y lo descarta, así que el
      `RUN` separado del Dockerfile no lo encontraba
      (`ModuleNotFoundError: No module named 'setuptools'`). Fix:
      `pip install setuptools pybind11` explícito antes del build.
      Encontrado en el primer intento real de build Docker (el build
      completo NO se rompió, gracias al `|| true` — exactamente el
      comportamiento diseñado, pero la extensión no se compiló hasta el
      segundo intento).
- [x] **Verificación de corrección, no solo "compila":** dentro del
      contenedor, `_fim_native.hash_files()` sobre `pyproject.toml`
      comparado byte a byte contra `hashlib.sha256()` de Python —
      **hash idéntico, tamaño idéntico, mtime idéntico**. `fim-baseline`/
      `fim-scan` corridos de verdad con la extensión activa contra los
      archivos reales del proyecto (94-95 archivos): `Sin drift` en la
      segunda corrida, sin discrepancias.

#### Framework de "% de cobertura aceptable" — actualizado

| # | Capacidad | Estado |
|---|---|---|
| 1 | FIM sobre archivos críticos del SO | `[x]` implementado, no verificado contra RHEL/CentOS real |
| 2 | Detección de fuerza bruta SSH | `[x]` implementado, parser no verificado contra `/var/log/secure` real |
| 3 | Agente continuo (loop 24/7) | `[x]` implementado (script + unidad systemd), no corrido en producción real todavía |
| 4 | Respuesta activa automática (fuerza bruta → `block_ip`) | `[x]` implementado y testeado |
| 5 | Identificación de atacante (recon pasivo automático) | `[x]` implementado y testeado |
| 6 | Detección de rootkits | `[ ]` no implementado (deseable, no bloqueante) |
| 7 | SCA / CIS Benchmarks | `[ ]` no implementado (deseable, no bloqueante) |
| 8 | Auditoría a nivel de syscall (`auditd`) | `[ ]` no implementado (deseable, no bloqueante) |
| 9 | Dashboard centralizado / multi-host | Fuera de alcance (un solo host) |

**Los 5 ítems "mínimo para producción" están implementados y testeados
(337/337 tests, ruff limpio).** La brecha que queda antes de considerar
esto "verificado en producción" no es de código, es de **entorno**: nada
de esto corrió todavía contra un CentOS/RHEL real con `/var/log/secure`,
`firewalld`, y tráfico SSH de verdad. Recomendación honesta antes de subir
la VM a exposición real: correr `defense-host-detect` primero, después
`defense-host-agent-cycle` manualmente una vez y revisar la salida, recién
después activar el loop continuo (systemd o script).

Suite completa: `pytest -q` → **337/337 passed**; `ruff check src tests` →
limpio; `docker compose config --quiet` → OK; ambos contenedores
(`scraper_agent`, `defense_watcher`) reconstruidos y verificados sanos
(`/health` responde OK) tras los cambios de Dockerfile.

### Pendiente

- [ ] Verificación contra un CentOS/RHEL real de las piezas 1-4 de esta
      entrada (host FIM, parser de auth log, agente continuo).
- [ ] Rootkit detection, SCA/CIS Benchmarks, auditoría `auditd` (ítems
      6-8 del framework de cobertura) — no implementados, deseables.
- [ ] Evaluar migrar `correlation.py` a la extensión nativa si el volumen
      real de eventos en producción resulta mucho mayor al estimado hoy.

---

### Pendiente consolidado — `defense_env/` (todo en un solo lugar)

> El usuario pidió juntar todos los pendientes sueltos de `defense_env/`
> en un solo lugar — solo agregar acá, sin desarrollar todavía. Esto
> reúne ítems ya mencionados en entradas anteriores (no duplicados, son
> los mismos, referenciados) más ítems que hasta ahora solo se habían
> mencionado en la conversación con el usuario y nunca se habían escrito
> formalmente en este archivo.

#### FIM

- [ ] **Verificación contra un CentOS/RHEL real** — FIM de proyecto, FIM
      del SO, parser de `/var/log/secure`, agente continuo: todo
      desarrollado y testeado con runners falsos / archivos sintéticos,
      nunca corrido contra un servidor Linux real. (Ya mencionado arriba
      — consolidado acá para que quede en un solo lugar.)
- [ ] **`list_connections()` sin parser estructurado** — devuelve líneas
      crudas de `ss`/`netstat`; parsear columnas (IP, puerto, PID, proceso)
      requiere verificar el formato exacto contra un RHEL real primero.

#### Correlación

- [ ] **Más reglas de correlación** — hoy solo 2 (`repeated_authorization_denied`,
      `high_risk_category_executed`) más `ssh_brute_force`. Faltan reglas
      sobre otras fuentes de log ya generadas por el proyecto pero nunca
      correlacionadas: sesiones del chat agent (`output/sessions/*.jsonl`),
      logs de Docker/Kali.
- [ ] **Migrar a formato Sigma real** ([SigmaHQ/sigma](https://github.com/SigmaHQ/sigma))
      si el motor simplificado actual (filtro de campos + umbral) se queda
      corto — hoy alcanza para las reglas que hay.
- [ ] **Migrar `correlation.py` a la extensión nativa de C++** si el
      volumen real de eventos en producción resulta mucho mayor al
      estimado hoy (ver evaluación en la entrada de pybind11 — hoy NO es
      candidato porque el volumen es bajo).

#### Respuesta activa

- [ ] **Notificaciones reales** (webhook/email/Slack) ante lockdown,
      aislamiento, o caso `critical` — hoy todo queda en archivos locales
      (`LOCKDOWN.json`, `ISOLATED.json`, `cases.json`); nadie se entera a
      menos que corra los comandos `defense-status`/`defense-isolation-status`/
      `defense-case-list` a mano.
- [ ] **Integración automática más amplia entre `defense-host-*` y los
      detectores de proyecto** (FIM de proyecto, ransomware, canary) — hoy
      `host_agent.py` solo dispara `block_ip` automático desde
      `ssh_brute_force`; una alerta `critical` de FIM/ransomware/canary a
      nivel de proyecto no dispara ninguna acción de `host_defense.py`
      todavía (solo lockdown/aislamiento de contenedor, que son mecanismos
      Docker-only).

#### Gestión de casos

- [ ] **Casos más ricos**: asignación de responsable, adjuntos, fecha
      límite — hoy `Case` solo tiene título/status/severidad/notas.

#### Sistema operativo (host_defense.py / host_agent.py)

- [ ] Rootkit detection.
- [ ] SCA / CIS Benchmarks (hardening del SO).
- [ ] Auditoría a nivel de syscall (`auditd` profundo, más allá del parseo
      de `/var/log/secure` que ya existe).

#### Infraestructura / calidad

- [ ] **Test automatizado del script del sidecar** (`defense_watcher` en
      `docker-compose.yml`, `scripts/host_agent_loop.sh`) — ambos
      validados corriendo el contenedor/script de verdad una vez, pero sin
      un test que los cubra si alguien los edita mal después.

#### Fuera de alcance declarado (no es "pendiente", es una decisión ya tomada)

- **Botnets** — requiere análisis de tráfico de red (beaconing C2, DNS)
  para el que no hay visibilidad real en este entorno de desarrollo
  (Docker Desktop en Windows). No es un pendiente a resolver acá, es un
  límite del entorno.
- **Dashboard centralizado / multi-host** — el alcance de este proyecto es
  un solo host con un solo operador, no una flota. Ver comparación
  completa contra Wazuh en las entradas anteriores.

---

### Añadido — REGLA DURA: remediación siempre pregunta antes de aplicar (nunca auto-aplica)

> **Contexto**: tras la pregunta del usuario "¿podemos identificar
> vulnerabilidades y repararlas?", la respuesta fue honesta: identificar,
> parcial; reparar, no existía nada. El usuario pidió que, antes de
> construir "reparar", quedara **en la médula de `tarea1`** que cualquier
> cambio real (no detección, un CAMBIO) siempre informa, sugiere la
> solución exacta, y pregunta antes de continuar — nunca se aplica solo.
>
> **Aclaración de alcance, resuelta explícitamente con el usuario antes de
> tocar código** (por las dudas de que esto contradijera lo ya construido):
> esta regla aplica a la **remediación nueva** (parchear, cambiar
> configuración) — NO a la contención rápida ya existente (`trigger_lockdown`,
> `isolate_container`, el `block_ip` automático de `host_agent.py` ante
> fuerza bruta SSH), que sigue siendo automática a propósito: son reflejos
> de emergencia que no pueden esperar una confirmación humana sin dejar
> avanzar un ataque activo. Reparar una vulnerabilidad nunca es así de
> urgente, y el efecto de un cambio mal aplicado es menos predecible que
> bloquear una IP — por eso la regla ahí es la opuesta: nunca sin humano.

- [x] **`defense_env/remediation.py`** — `RemediationSuggestion`
      (issue, explanation, `suggested_command`, `risk_level`, `source`).
      `suggest_remediation(pattern_id, finding)` — busca en un catálogo de
      patrones conocidos (`outdated_openssh`, `weak_sshd_config` por ahora,
      extensible vía `@_register`) y devuelve la sugerencia SIN ejecutar
      nada — función pura. Si el patrón no se reconoce, devuelve `None` en
      vez de inventar un fix incorrecto.
      `apply_remediation(suggestion, *, confirmed, runner)` — **rechaza
      con `ValueError` si `confirmed` no es `True` explícito, sin llamar
      al `runner`** (cero efectos secundarios). No es una convención de
      CLI (`--yes`) nada más — está forzado a nivel de función: llamarla
      desde cualquier lado, de cualquier forma, sin `confirmed=True`
      explícito, falla. `confirmed` tampoco tiene default `True` posible
      (el test lo verifica: llamarla sin el kwarg es `TypeError`).
      _(2026-07-10 — `tests/test_defense_remediation.py`, 8 casos —
      incluye un test que confirma que `suggest_remediation` nunca ejecuta
      nada por sí sola)_
- [x] **CLI**: `defense-remediate-suggest <pattern_id> [opciones del
      hallazgo]` — informa y sugiere, exit code 0, nunca aplica nada, ni
      con todos los flags puestos. `defense-remediate-apply <pattern_id>
      ... --yes` — repite la sugerencia (informa) y recién después aplica,
      solo si `--yes` está. Sin `--yes`: exit code 1, no toca el sistema.
      _(2026-07-10 — `tests/test_cli_remediation.py`, 3 casos)_
- [x] **Catálogo inicial** (2 patrones, extensible — no es exhaustivo a
      propósito, mejor 2 sugerencias correctas que 20 inventadas):
      `outdated_openssh` (sugiere `dnf/yum/apt update openssh-server`),
      `weak_sshd_config` (sugiere desactivar una directiva insegura de
      `sshd_config` vía `sed`, ej. `PermitRootLogin`).
      Suite completa: `pytest -q` → **348/348 passed**; `ruff check src
      tests` → limpio.

### Pendiente

- [ ] **Catálogo de remediaciones muy chico** (2 patrones) — falta mapear
      más hallazgos reales (ej. salida de `nuclei_safe`/`nmap_vuln_scripts`
      contra CVEs específicos) a sugerencias concretas. Ver también
      "Identificación automática de findings" abajo.
- [ ] **Sin conexión automática entre `defense-self-scan` y
      `defense-remediate-suggest`** — hoy el operador tiene que leer el
      resultado crudo del self-scan y decidir a mano qué `pattern_id`
      corresponde. El flujo ideal (self-scan detecta OpenSSH viejo →
      sugiere automáticamente `outdated_openssh` con el detalle ya
      completado) no está armado todavía.
- [ ] **Sin registro persistente de remediaciones sugeridas/aplicadas** —
      a diferencia de alertas (JSONL) o casos (JSON), hoy una sugerencia o
      una aplicación de `defense-remediate-*` no queda guardada en ningún
      lado más allá de la salida de consola — no hay auditoría histórica
      de "qué se sugirió, qué se aplicó, cuándo, quién confirmó".

## Plantilla para nuevas entradas (copiar al agregar algo nuevo)

```markdown
## [Unreleased]

### Added
- [ ] <descripción del cambio> — campo/módulo afectado: `<ruta.en.el.schema>`

### Changed
- [ ] <descripción del cambio>

### Fixed
- [ ] <descripción del bug y cómo se corrige>

### README
- [ ] README actualizado — sección: `<nombre de la sección tocada>`
      — o —
- [ ] README: no aplica — <razón>
```

> ⚠️ Ningún cambio se marca `[x]` en `Added`/`Changed`/`Fixed` si su línea
> correspondiente en `README` sigue en `[ ]`. Son dependientes entre sí.