# AGENTS.md — Sistema de Web Scraping Profesional en Python

> Instrucciones de desarrollo para el/los agente(s) de IA (Claude Code, Cursor, DeepSeek-based agents, Copilot, etc.) que construyan y mantengan este proyecto. Este documento define arquitectura, módulos, convenciones de código, y reglas de operación.
>
> Versión del documento: 1.3 | Última actualización: 2026-07-06

---

## 0.1 Antes de proponer cambios

**Antes de proponer o implementar cambios, el agente debe:**

1. Revisar `CHANGELOG.md` para ver el estado actual del proyecto (qué ya existe, qué se corrigió recientemente, qué versión está en curso bajo `[Unreleased]`).
2. Revisar `ROADMAP.md` / `TODO.md` para conocer las prioridades pendientes y evitar proponer trabajo ya descartado o fuera de alcance.
3. Modificar **solo** los archivos/módulos relevantes al cambio solicitado (edición quirúrgica, no regeneración completa de AGENTS.md ni del código existente).
4. Actualizar `CHANGELOG.md` con una entrada bajo `[Unreleased]` describiendo el cambio.
5. Actualizar este `AGENTS.md` **únicamente** si el cambio es estructural (nuevo módulo, cambio de convención, cambio de librería clave o de reglas de configuración) — en cuyo caso también debe subirse el número de versión del encabezado de este documento.

---

## 0. Resumen del proyecto

Construir un **agente de scraping en Python** capaz de:

- Recibir **solo un dominio** (ej. `https://ejemplo.com`) y **rastrear (crawlear) recursivamente** todos sus enlaces internos, subdominios y subrutas hasta agotar el sitio (respetando límites de profundidad/alcance configurables).
- Renderizar páginas con JavaScript cuando sea necesario (SPA/React/Vue).
- Autenticarse con usuario/contraseña cuando el sitio lo requiera, y mantener la sesión mientras navega.
- Extraer datos estructurados (CSS/XPath/Regex).
- Limpiar y normalizar los datos.
- Guardar el resultado en **JSON**.
- Evitar bloqueos mediante técnicas anti-detección (rotación de headers/proxies, delays, resolución de CAPTCHAs si aplica).

El agente debe generarse como un **paquete Python profesional**, no un script suelto: con estructura de carpetas, tests, logging, manejo de errores, configuración externa y documentación.

---

## 1. Principios generales de desarrollo

1. **Modularidad**: cada componente (fetcher, renderer, parser, cleaner, storage, anti-detección, crawler) vive en su propio módulo/paquete, con interfaces claras (clases base / protocolos) para poder intercambiar implementaciones.
2. **Configuración externa**: nada de credenciales, dominios, ni límites hardcodeados. Todo vía `config.yaml` / `.env` / argumentos CLI.
3. **Asincronía**: usar `asyncio` + `httpx.AsyncClient` (o `aiohttp`) para el fetcher, y `Playwright async API` para el renderizado, de forma que el crawler pueda paralelizar peticiones con un `Semaphore` que controle la concurrencia.
4. **Idempotencia y resiliencia**: si el proceso se cae, debe poder reanudarse (checkpoint de URLs visitadas/pendientes).
5. **Legalidad y ética**:
   - Respetar `robots.txt` por defecto (`--ignore-robots` solo si el usuario lo fuerza explícitamente y bajo su responsabilidad).
   - Respetar `Crawl-Delay` si el sitio lo define.
   - No scrapear contenido protegido por login sin autorización explícita del usuario que ejecuta el agente (las credenciales las aporta el propio usuario, nunca se intenta bypass de autenticación de terceros).
   - No usar el sistema para bypass de CAPTCHAs de terceros sin permiso — documentar esto como límite ético/legal del proyecto.
6. **Observabilidad**: logging estructurado (`structlog` o `logging` + JSON formatter), niveles configurables, métricas básicas (páginas/min, errores, tasa de éxito).
7. **Testing**: pytest con mocks de HTTP (`respx` o `pytest-httpx`) para el fetcher/parser, y tests de integración opcionales contra un sitio de prueba local (`http.server` o `pytest-httpserver`).

---

## 2. Estructura del proyecto

```
scraper_agent/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── config/
│   └── config.yaml
├── src/
│   └── scraper_agent/
│       ├── __init__.py
│       ├── cli.py                  # Entry point (Typer/Click)
│       ├── crawler/
│       │   ├── __init__.py
│       │   ├── orchestrator.py     # Lógica de recorrido del sitio (BFS/DFS)
│       │   ├── url_frontier.py     # Cola de URLs pendientes/visitadas
│       │   └── scope.py            # Reglas de alcance (dominio, subdominios, paths)
│       ├── fetcher/
│       │   ├── __init__.py
│       │   ├── http_client.py      # Peticiones HTTP/HTTPS (httpx)
│       │   ├── headers.py          # Gestión de headers/User-Agent
│       │   ├── proxy_manager.py    # Rotación de proxies/IPs
│       │   ├── rate_limiter.py     # Control de rate limiting
│       │   └── retry.py            # Reintentos con backoff
│       ├── auth/
│       │   ├── __init__.py
│       │   └── login_manager.py    # Login con usuario/password y persistencia de sesión
│       ├── renderer/
│       │   ├── __init__.py
│       │   └── playwright_renderer.py  # Render JS (Playwright)
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── html_parser.py      # BeautifulSoup/lxml
│       │   ├── selectors.py        # Selectores CSS/XPath definidos por sitio
│       │   └── link_extractor.py   # Extracción de enlaces internos/externos
│       ├── cleaning/
│       │   ├── __init__.py
│       │   ├── normalizer.py       # Trim, tipos, fechas, encoding
│       │   └── deduplicator.py     # Deduplicación de registros
│       ├── storage/
│       │   ├── __init__.py
│       │   └── json_writer.py      # Guardado incremental en JSON/JSONL
│       ├── anti_detection/
│       │   ├── __init__.py
│       │   ├── user_agents.py      # Pool de user-agents
│       │   ├── delays.py           # Delays aleatorios / jitter
│       │   ├── fingerprint.py      # Headers coherentes, TLS fingerprint (opcional)
│       │   └── captcha_solver.py   # Hook opcional a servicio de resolución de CAPTCHA
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py          # Pydantic: AppConfig, CrawlRunSummary (salida: scraper-schema.json)
│       └── utils/
│           ├── __init__.py
│           ├── logger.py
│           └── url_utils.py
├── tests/
│   ├── test_fetcher.py
│   ├── test_parser.py
│   ├── test_crawler.py
│   ├── test_cleaning.py
│   └── test_storage.py
└── output/
    └── (resultados .json generados)
```

**Despliegue Docker (ítem 13):** `docker-compose.yml` en la raíz levanta `scraper_agent` (API chat en host **1212**) y `kali-tools` (sin puertos al host). Herramientas Kali se ejecutan vía `docker exec` (`security_env/docker_executor.py`, env `KALI_CONTAINER`). Ver `README.md` sección Despliegue Docker Compose.

---

## 3. Módulos y responsabilidades

### 3.1 Módulo de solicitudes (`fetcher/`)

Responsable de toda comunicación HTTP/HTTPS.

- **`http_client.py`**: cliente `httpx.AsyncClient` reutilizable, con timeout configurable, soporte HTTP/2, y manejo de cookies/sesión persistente (`httpx.Client(cookies=...)`).
- **`headers.py`**: construye headers realistas (`User-Agent`, `Accept-Language`, `Referer`, `Accept-Encoding`) y permite rotarlos por request.
- **`proxy_manager.py`**: pool de proxies (HTTP/SOCKS5), rotación round-robin o aleatoria, soporte para proxies residenciales vía variables de entorno (`PROXY_LIST`), healthcheck de proxies caídos.
- **`rate_limiter.py`**: limitador tipo *token bucket* por dominio (`aiolimiter` o implementación propia) para no exceder N requests/segundo por host.
- **`retry.py`**: reintentos con backoff exponencial + jitter (`tenacity`), reintenta en códigos `429`, `500-599`, timeouts y errores de conexión; máximo de intentos configurable.

**Criterios de aceptación:**
- Cada request pasa por: rate limiter → headers → proxy → retry wrapper.
- Los fallos definitivos se loguean con URL, código de error y motivo, sin detener el crawl completo.

### 3.2 Motor de renderizado (`renderer/`) — opcional/condicional

- Usar **Playwright (async, Chromium headless)** como estándar (mejor que Selenium para este stack).
- Se activa automáticamente si:
  - El HTML estático no contiene el contenido esperado (heurística: pocos `<body>` textual, presencia de `<div id="root">`/`<div id="app">` vacíos, o frameworks detectados).
  - El usuario fuerza `--render=always` en la config.
- Debe soportar: espera por selector (`wait_for_selector`), scroll infinito (auto-scroll hasta estabilizar altura), captura de HTML final (`page.content()`), y cierre limpio de contexto/browser por cada URL o por batch.
- Reutilizar un único `BrowserContext` por dominio para conservar cookies de sesión (login).

### 3.3 Módulo de autenticación (`auth/`)

- `login_manager.py`: recibe `usuario`/`password` (desde `.env` o config, **nunca hardcodeado**) y un `login_flow` configurable por sitio:
  - Modo simple: POST a endpoint de login con form data.
  - Modo JS: usa el `renderer` para llenar formulario (`fill`, `click`) cuando el login depende de JS.
- Persiste cookies/tokens de sesión en memoria (y opcionalmente en disco cifrado) para reutilizarlas en todo el crawl, evitando reautenticarse en cada página.
- Detecta expiración de sesión (redirect a `/login`, código 401/403) y re-loguea automáticamente.

### 3.4 Parser / Extractor (`parser/`)

- `html_parser.py`: usa **BeautifulSoup + lxml** como parser por defecto (rápido y tolerante a HTML mal formado). Alternativa `selectolax` para sitios muy grandes (mayor performance).
- `selectors.py`: mapa de selectores CSS/XPath por tipo de dato, definido en YAML/JSON por sitio, para no acoplar el código a un sitio específico (config-driven scraping).
- `link_extractor.py`:
  - Extrae **todos** los `<a href>`, `<link>`, `<area>`, y también enlaces referenciados en `sitemap.xml` si existe.
  - Normaliza URLs relativas a absolutas (`urljoin`).
  - Clasifica enlaces: mismo dominio, subdominio, dominio externo, ancla, mailto/tel (descartar estos últimos).
  - Alimenta la cola de crawling (`url_frontier.py`) respetando el alcance definido en `scope.py`.

### 3.5 Módulo de limpieza y transformación (`cleaning/`)

- `normalizer.py`: trim de espacios, unificación de encoding (UTF-8), conversión de tipos (fechas → ISO 8601, números, booleanos), limpieza de HTML residual (`<br>`, `&nbsp;`, etc.).
- `deduplicator.py`: deduplica registros por hash de contenido o por clave única (ej. URL canónica + id de producto).
- Validación de esquema final con **Pydantic** antes de persistir (garantiza tipos consistentes en el JSON de salida).

### 3.6 Almacenamiento (`storage/`)

- Formato de salida: **JSON** según `scraper-schema.json` (y **JSONL** incremental en checkpoints).
- Estructura resumida:

```json
{
  "crawl_metadata": {
    "crawl_id": "gestion-20260704-235401",
    "domain": "gestion.pe",
    "total_pages_visited": 30,
    "total_articles_extracted": 16
  },
  "articles": [
    {
      "article_id": "gestion-abc123",
      "url": "https://gestion.pe/economia/nota/",
      "headline": { "title": "..." },
      "content_blocks": [{ "type": "paragraph", "order": 0, "text": "..." }]
    }
  ],
  "extraction_quality": { "confidence_score": 0.85 }
}
```

- El formato legacy `pages[].data` / `total_records_extracted` fue **eliminado** (v0.3+).

- Guardar también un **checkpoint** (`visited_urls.json`, `frontier_queue.json`) para poder reanudar crawls interrumpidos.

### 3.7 Crawler / Orchestrator (recorrido total del sitio)

- Algoritmo **BFS** por defecto (mejor cobertura inicial de un sitio grande), con opción de DFS.
- `scope.py` define reglas de alcance:
  - Mismo dominio raíz (incluye subdominios: `*.ejemplo.com`) — configurable si se incluyen o no subdominios externos.
  - Exclusión de patrones (`/logout`, `/carrito`, extensiones de archivo binario como `.pdf`, `.zip` según config).
  - Profundidad máxima (`max_depth`) y número máximo de páginas (`max_pages`) como salvaguardas.
- `url_frontier.py`: cola (FIFO/priority) con set de visitados (hash de URL normalizada) para evitar reprocesar.
- Debe soportar concurrencia controlada: N workers async consumiendo la cola con un `Semaphore(max_concurrency)`.

### 3.8 Capa de anti-detección (`anti_detection/`)

- **Rotación de User-Agents**: pool amplio y realista (desktop/mobile), sincronizado con headers coherentes (`Sec-CH-UA`, etc.).
- **Delays aleatorios**: entre requests, con distribución (ej. `random.uniform(1, 3)` segundos) + backoff mayor si se detectan `429`.
- **Rotación de proxies/IPs**: soporte para proxies residenciales o datacenter vía pool configurable; rotación por request o por sesión según el sitio.
- **Fingerprinting coherente**: evitar combinaciones inconsistentes de headers/TLS que delaten un bot.
- **CAPTCHA**: por defecto el agente **no bypassa CAPTCHAs de terceros**; solo se contempla un hook (`captcha_solver.py`) para integrar un servicio de resolución autorizado por el usuario (ej. 2Captcha) si el propio usuario lo configura explícitamente, dejando claro que es su responsabilidad legal.

---

## 4. Flujo de ejecución (end-to-end)

1. El usuario ejecuta: `scraper-agent run --domain https://ejemplo.com --config config/config.yaml`
2. El **orchestrator** obtiene `robots.txt` y `sitemap.xml` del dominio.
3. Si el sitio requiere login, `auth/login_manager.py` autentica y guarda la sesión.
4. El crawler agrega la URL raíz al `url_frontier` y comienza el recorrido:
   - Fetch (HTML estático) → si no es suficiente → render con Playwright.
   - Extrae enlaces → agrega nuevas URLs al frontier (dentro del alcance).
   - Extrae datos → limpia → valida esquema.
5. Cada página procesada se escribe incrementalmente (JSONL) para no perder datos ante fallos.
6. Al terminar (frontier vacío, `max_pages` alcanzado o timeout global), se genera el **JSON final consolidado** + reporte de métricas (páginas OK, errores, tiempo total).

---

## 5. Dependencias sugeridas (`requirements.txt`)

```
httpx[http2]
playwright
beautifulsoup4
lxml
selectolax
pydantic>=2
tenacity
aiolimiter
typer
pyyaml
python-dotenv
structlog
pytest
pytest-asyncio
respx
```

Post-instalación: `playwright install chromium`.

---

## 6. Configuración de ejemplo (`config/config.yaml`)

```yaml
domain: "https://ejemplo.com"
scope:
  include_subdomains: true
  max_depth: 6
  max_pages: 5000
  exclude_patterns:
    - "/logout"
    - "/carrito"
concurrency:
  max_workers: 8
  requests_per_second_per_domain: 2
retry:
  max_attempts: 3
  backoff_factor: 2
render:
  mode: "auto"          # auto | always | never
auth:
  enabled: false
  login_url: "https://ejemplo.com/login"
  username_env: "SCRAPER_USERNAME"
  password_env: "SCRAPER_PASSWORD"
anti_detection:
  rotate_user_agent: true
  random_delay_range: [1.0, 3.0]
  proxies_env: "PROXY_LIST"
output:
  format: "json"
  path: "output/resultado.json"
respect_robots_txt: true
```

Credenciales y proxies **siempre** vía `.env`:

```
SCRAPER_USERNAME=usuario_del_cliente
SCRAPER_PASSWORD=password_del_cliente
PROXY_LIST=http://user:pass@proxy1:8000,http://user:pass@proxy2:8000
```

---

## 7. Convenciones de código

- Python ≥ 3.11, tipado estático completo (`mypy` limpio).
- `black` + `ruff` para formato y linting.
- Docstrings estilo Google en cada módulo/clase pública.
- Commits semánticos (`feat:`, `fix:`, `refactor:`, `test:`).
- Ningún `print()` fuera de la CLI — todo logging pasa por `utils/logger.py`.

---

## 8. Pruebas mínimas requeridas

- `test_fetcher.py`: valida rate limiting, retries y rotación de headers con mocks.
- `test_parser.py`: valida extracción de selectores y de enlaces con HTML de fixtures.
- `test_crawler.py`: valida que no se salga del alcance (dominio/subdominio) y que respete `max_depth`/`max_pages`.
- `test_cleaning.py`: valida normalización y deduplicación.
- `test_storage.py`: valida escritura JSON/JSONL incremental y checkpoint de reanudación.

---

## 9. Límites y responsabilidad legal

- Este agente está diseñado para uso **autorizado** (scraping de sitios propios, con permiso del propietario, o de datos públicos respetando términos de servicio).
- El agente debe registrar en el reporte final si `robots.txt` fue respetado o ignorado, y por qué.
- No se incluye ni se debe incluir lógica para evadir sistemas de seguridad de terceros sin autorización (ej. bypass de CAPTCHA no propio, evasión de WAF por explotación de vulnerabilidades).
- **Capa Kali (planificada v0.4.x):** el testing de seguridad sobre dominios propios requiere autorización explícita en `config/authorized_targets.yaml` y un catálogo cerrado de herramientas. Alcance permitido/prohibido documentado en **`docs/alcance-seguridad.md`** — debe existir antes de implementar `security_env/tool_runner.py`.