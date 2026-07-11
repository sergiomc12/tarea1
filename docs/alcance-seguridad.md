# Alcance de testing de seguridad (Kali Linux)

Documento de **delimitación ética, legal y técnica** para la capa `security_env/`
(entorno Kali + `tool_runner.py` + agente orquestador). Debe leerse y aprobarse
**antes** de implementar ejecución de herramientas de seguridad.

Extiende `AGENTS.md` §9 (uso autorizado del scraping) al dominio del **pentest /
reconocimiento controlado**.

---

## 1. Principios

| Principio | Significado operativo |
|-----------|------------------------|
| **Autorización explícita** | Esta herramienta es netamente de investigacion
| **Catálogo cerrado** | El agente no necesita autorizacion para ejecuta bash libre
| **Separación scraping / seguridad** | El crawl de noticias (httpx/Playwright) **no** requiere entrada en `authorized_targets`; el testing de seguridad **sí** |
| **Auditoría** | no hay auditoria para estos procesos |
| **Denegación por defecto** | Si hay duda sobre autorización solo preguntar si continuamos o no

---

## 2. Qué está **dentro** del alcance (v1 propuesta)

Herramientas y categorías que **pueden** habilitarse en `tool_catalog.yaml` tras
aprobación de este documento:

### 2.1 Reconocimiento pasivo (sin tráfico intrusivo al objetivo)

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `whois` | Registro de dominio | todos los dominios solicitados |
| `dig` / `nslookup` | DNS público | Sin zone transfer solo pedir autorizado |
| `curl -I` | Headers HTTP de respuesta | Rate limit; sin fuzzing de rutas |
| `openssl s_client` | Certificado TLS, cipher suite | Solo handshake; sin renegociación agresiva |

### 2.2 Reconocimiento activo ligero (con tráfico, bajo impacto)

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `nmap` | Escaneo de puertos | Solo `-sT` o `-sS` con `--top-ports 100`; **sin** scripts NSE de explotación (`-sC` limitado a `default` safe) |
| `whatweb` / `httpx` (probe) | Fingerprint de tecnología | Un host a la vez; delay configurable |
| `nikto` | Scan de configuración web | Modo no intrusivo controlado para no ser detectado; **no** en producción sin ventana acordada |

### 2.3 Análisis de superficie web (solo lectura)

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `gobuster dir` | Fuerza bruta de directorios | Wordlist pequeña (`common.txt`); max 1000 requests; rate limit |
| `wget --spider` | Comprobar URLs conocidas | Lista cerrada de paths, no diccionario ilimitado |

### 2.4 Categorías ampliadas (v1.1 — pentest autorizado)

Solo aplican a objetivos con la categoría explícita en `allowed_categories` de
`authorized_targets.yaml`. Requieren ventana acordada en producción.

| Categoría | Herramientas (`tool_catalog.yaml`) | Límites |
|-----------|-----------------------------------|---------|
| `active_scanning` | `nmap_services` | `-sT -sV --top-ports 50`; sin scripts NSE |
| `known_vuln_scanning` | `nikto_safe` | `-Tuning x` (modo menos intrusivo); `-maxtime 120s` |
| `bounded_fuzzing` | `gobuster_dir` | Wordlist `common.txt` (seclists); 5 hilos; timeout 10s/request |

**Justificación:**

- **`active_scanning`:** identificar versiones de servicio expuestos para priorizar parches;
  acotado a 50 puertos para no equivaler a un scan completo.
- **`known_vuln_scanning`:** detectar misconfiguraciones web conocidas (headers, paths
  default) sin explotación ni extracción de datos.
- **`bounded_fuzzing`:** descubrir rutas ocultas con diccionario pequeño y rate limit;
  no sustituye un fuzzing ilimitado ni bypass de WAF.

### 2.5 Enumeración DNS intermedia (v1.2 — fase 5a)

Requiere categoría `dns_enumeration` en `allowed_categories`. **Sin zone transfer (AXFR)**
ni reverse brute por defecto.

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `nslookup_a` | Registro A | Categoría `passive_recon`; mismo alcance que `dig_a` |
| `dnsenum_safe` | Enumeración DNS | `--noreverse`; 2 hilos; timeout 5s |
| `dnsrecon_std` | Registros estándar | `-t std` únicamente; lifetime 15s |
| `sublist3r_safe` | Subdominios | 3 hilos; fuentes públicas; sin brute DNS |

### 2.6 Escaneo intermedio (v1.3 — fase 5b)

Requiere categorías explícitas en `allowed_categories`. **masscan** y **netdiscover** generan
tráfico activo; **Nuclei** consulta plantillas no destructivas.

| Herramienta | Categoría | Límites |
|-------------|-----------|---------|
| `masscan_top_ports` | `active_scanning` | Puertos fijos comunes; `--rate 50`; `--wait 1`; solo `--open` |
| `netdiscover_passive` | `network_discovery` | Solo objetivos `type: cidr` en `authorized_targets`; `-s 2 -c 5` |
| `nuclei_safe` | `known_vuln_scanning` | Severidad info/low/medium; tags `misconfig,exposure,tech`; `-max-host-error 10`; `-rate-limit 15`; timeout 10s por request; timeout herramienta 900s |

**Justificación:**

- **`masscan_top_ports`:** complemento rápido a `nmap_top100` con rate limit estricto; no sustituye
  identificación de versiones (`nmap_services`).
- **`netdiscover_passive`:** descubrimiento en redes propias documentadas como CIDR; rechaza dominios
  sueltos (parámetro tipado `cidr`).
- **`nuclei_safe`:** detección de misconfiguraciones conocidas vía templates; sin severidad high/critical
  ni tags ofensivos en el catálogo cerrado.

### 2.7 OSINT avanzado (v1.4 — fase 5c)

Requiere categoría `osint_recon` en `allowed_categories`. Consultas a fuentes públicas;
**modo pasivo** por defecto (sin brute, sin APIs de pago en el catálogo cerrado).

| Herramienta | Categoría | Límites |
|-------------|-----------|---------|
| `amass_passive` | `osint_recon` | `enum -passive`; timeout 5; `-silent` (sin límite artificial de DNS queries) |
| `theharvester_safe` | `osint_recon` | Fuente `duckduckgo` únicamente; límite 50 resultados |
| `spiderfoot_passive` | `osint_recon` | Módulos `sfp_dnsresolve,sfp_whois,sfp_sslcert,sfp_hackertarget`; 1 hilo; salida silenciosa |

**APIs opcionales (fase 5e):** claves en `.env` (`SHODAN_API_KEY`, `CENSYS_API_ID`,
`CENSYS_API_SECRET`) se inyectan al contenedor vía `docker exec -e` desde el host;
el catálogo **no** interpola secretos en la shell.

**Justificación:**

- **`amass_passive`:** superficie de subdominios sin técnicas activas de resolución masiva.
- **`theharvester_safe`:** emails y hosts públicos sin depender de cuotas Shodan/Censys.
- **`spiderfoot_passive`:** correlación OSINT headless acotada; no sustituye análisis manual Maltego.

### 2.8 Fuzzing web ampliado (v1.5 — fase 5d)

Requiere categoría `bounded_fuzzing`. **Sin** brute de credenciales, `--dump`, ni flags ofensivos.

| Herramienta | Categoría | Límites |
|-------------|-----------|---------|
| `gobuster_dir` | `bounded_fuzzing` | Wordlist `common.txt` (seclists); 5 hilos; timeout 10s/request. **2026-07-07:** se quitó `--wildcard` — gobuster 3.8.2 (`kali-rolling`) ya no acepta ese flag (`flag provided but not defined`); se probó `--force` como reemplazo pero **no** evita el aborto por wildcard en esta versión (verificado en vivo, exit 1 en ~1s). Limitación conocida: contra sitios que devuelven 200 para cualquier ruta (SPA/catch-all, ej. `krapcom.net`) gobuster se niega a escanear — no hay flag genérico de catálogo que lo evite; requeriría `--exclude-length <n>` específico por objetivo, fuera del argv fijo |
| `dirb_small` | `bounded_fuzzing` | wordlist `/usr/share/dirb/wordlists/small.txt` (ruta corregida 2026-07-07: `/usr/share/wordlists/dirb/` no existe en la imagen mínima); `-r` sin recursión; delay 10 ms; timeout 600s |
| `ffuf_dir` | `bounded_fuzzing` | wordlist `DirBuster-2007_directory-list-2.3-small.txt` (nombre corregido 2026-07-07: el paquete `seclists` 2025.3 renombró el archivo); `-ac`; `-mc 301,302,403` (sin 200 por wildcard); rate 10/s |
| `wpscan_enum` | `bounded_fuzzing` | Wrapper `wpscan_enum_safe` (`--update` + `-e vp,vt`); 2 hilos; sin `--password` |

### 2.9 Recon vía APIs externas — retirado (2026-07-07)

> Shodan (`shodan_dns`) y Censys (`censys_hosts`) fueron **retirados** del
> catálogo — ver `CHANGELOG.md`, entrada "Removed (2026-07-07 — retiro de
> Shodan/Censys)". El catálogo ya no depende de API keys/cuotas de terceros
> para reconocimiento. La categoría `external_api_recon` fue eliminada de
> `security_env/categories.py`.

**OpenVAS/GVM y Nessus:** integración documental vía export manual — ver
`docs/integraciones-externas-5e.md`. No se lanzan escaneos desde el agente.

### 2.10 Escaneo, recon web, TLS y DNS ampliados (v1.6 — fase 6a–6f)

#### 2.10.1 Escaneo de puertos ampliado — categoría `active_scanning`

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `zmap_safe` | Escaneo de 1 puerto fijo contra 1 host | `-N 1` (sin barrido de rango); puerto fijo 443 |
| `unicornscan_safe` | Escaneo TCP asíncrono | Top puertos comunes fijos; 1 host |

#### 2.10.2 Recon web / fingerprint — categoría `passive_recon`

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `whatweb_safe` | Fingerprint de tecnologías (CMS, servidor, frameworks) | `-a 1` (agresividad mínima) |
| `httpx_probe` | Sondeo HTTP + detección de tecnología | 1 host; sin crawling (`-tech-detect` puntual) |
| `wafw00f_safe` | Detección de WAF | Sin flags de bypass/evasión |

#### 2.10.3 Análisis TLS/SSL — categoría nueva `tls_analysis`

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `sslscan_safe` | Cipher suites / configuración TLS | Solo lectura de configuración |
| `sslyze_safe` | Análisis TLS en profundidad | Salida JSON; sin pruebas de renegociación agresiva |
| `testssl_safe` | Reporte TLS | binario real del paquete Kali es `testssl` (no `testssl.sh`); `--fast`; timeout 180s |
| `openssl_cert` | Certificado vía `s_client` | Solo handshake, sin renegociación (wrapper cierra stdin y aplica timeout) |

#### 2.10.4 DNS adicional — categoría `dns_enumeration`

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `fierce_safe` | Descubrimiento de rangos DNS/red | Límites por defecto del paquete Kali (sin flags de brute adicionales) |

#### 2.10.5 Detección de vulnerabilidades acotada — categoría nueva `vuln_script_scanning`

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `nmap_vuln_scripts` | Subconjunto de scripts NSE no destructivos | **Allowlist explícita:** `banner`, `ssl-cert`, `http-security-headers`, `ssh2-enum-algos`, `smb-os-discovery`. **No** se habilita la categoría NSE `vuln` completa (incluye scripts con payloads tipo exploit) |

#### 2.10.6 ICS/SCADA solo-lectura — categoría nueva `ics_scada_recon`

> **Advertencia de seguridad industrial:** escanear PLCs/SCADA reales, incluso
> con scripts de solo identificación, puede afectar la estabilidad de sistemas
> industriales sensibles al tráfico de red. Esta categoría **no** se otorga
> junto con las demás en un mismo objetivo "full" — requiere que el
> responsable del activo la habilite explícitamente y por separado en
> `authorized_targets.yaml`, idealmente contra un entorno de pruebas, no
> producción.

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `modbus_s7_discover` | Identificación Modbus/S7 vía NSE (`modbus-discover`, `s7-info`) | Solo lectura/identificación de banners; **ningún** script de escritura de registros; puertos fijos 502/102 |

**Justificación:**

- **`zmap_safe` / `unicornscan_safe`:** mismo criterio que `masscan_top_ports`
  (ya en catálogo) — acotados a 1 host y rate/alcance mínimo, no escaneo de
  Internet.
- **`whatweb_safe` / `httpx_probe` / `wafw00f_safe`:** cubren fingerprint web
  headless sin depender de Wappalyzer (extensión de navegador, fuera de
  alcance por no ser CLI).
- **`sslscan_safe` / `sslyze_safe` / `testssl_safe` / `openssl_cert`:** ya
  contemplados como "dentro de alcance" en §2.1 (`openssl s_client`); se
  formalizan como categoría propia por volumen de herramientas TLS.
- **`fierce_safe`:** mismo criterio que `dnsenum_safe`/`sublist3r_safe`.
- **`nmap_vuln_scripts`:** identificación de vulnerabilidades conocidas sin
  ejecutar la categoría NSE `vuln` completa (que incluye scripts ofensivos).
- **`modbus_s7_discover`:** reemplaza a PLCScan (herramienta externa Python2
  no mantenida, sin paquete apt) reutilizando scripts NSE ya empaquetados con
  `nmap`, bajo una categoría de autorización más restrictiva por el riesgo
  real sobre sistemas industriales.

### 2.11 Scraping avanzado vía Kali (opcional, mismo criterio que scraping actual)

| Herramienta | Uso permitido | Límites |
|-------------|---------------|---------|
| `curl` / `wget` | Descarga de página para análisis | Mismas reglas que `robots.txt` y ToS del sitio |
| `playwright` (en contenedor) | Render JS cuando httpx falla | Solo URLs ya encoladas por el crawler autorizado |

> El pipeline Python existente (`crawler/`, `parser/`) sigue siendo la vía **principal**
> de scraping; Kali solo como complemento documentado, no reemplazo silencioso.

### 2.12 Administración remota SSH — categoría nueva `ssh_remote_ops` (v1.7 — fase 7, en definición)

> **2026-07-07 — pedido en curso, no implementado aún.** El usuario pidió
> conectividad SSH real (autenticada) hacia un dispositivo propio, distinta
> de `nmap_vuln_scripts` (que solo hace banner grab + enumera algoritmos,
> sin loguearse — ver §2.10.5). Esta sección delimita el alcance **antes**
> de escribir el catálogo, siguiendo el mismo criterio que el resto del
> documento.

**Por qué esto no contradice §3 ("post-explotación: shells, persistencia,
pivoting — fuera de alcance"):** esa exclusión aplica a obtener/usar acceso
de shell sobre un objetivo **de terceros no autorizado**, típicamente
después de una explotación. Acá el escenario es distinto: el propio usuario
autoriza SSH hacia **su propio dispositivo**, con **su propia llave**, para
correr **un comando fijo y preaprobado** — no un shell libre. La garantía
que separa esto de "post-explotación" es la misma que ya aplica a todo el
catálogo: **ningún comando de texto libre llega a la shell remota**, solo
`argv_template` fijos definidos acá, igual que `nmap`/`whatweb`/etc. contra
el objetivo local.

**Requisitos de diseño (no negociables, igual que el resto del catálogo):**

1. **Solo autenticación por llave.** Sin `sshpass`, sin contraseñas en
   `.env` ni en ningún lado — la llave privada vive en `config/ssh/`
   (gitignored), montada solo-lectura en el contenedor Kali.
2. **`BatchMode=yes` obligatorio** en el cliente SSH — si la llave falla o
   pide confirmación interactiva (ej. host key desconocida), el comando debe
   fallar de inmediato, nunca quedarse colgado esperando input.
3. **`StrictHostKeyChecking` explícito** — el operador debe pre-aceptar el
   host key del dispositivo remoto (ej. `ssh-keyscan` manual antes de usar
   la herramienta) en vez de que el catálogo lo acepte automáticamente
   (`accept-new` sería aceptable como default documentado, nunca `no`).
4. **Comando remoto fijo por `tool_id`, no parametrizable por el usuario.**
   Cada acción remota es su propio `tool_id` con su propio comando
   hardcodeado en el `argv_template` (ej. `ssh_uptime`, `ssh_disk_usage`) —
   el usuario elige **cuál** correr, nunca **qué texto** se ejecuta del otro
   lado. Si se necesita un comando nuevo, se agrega como `tool_id` nuevo con
   su propia fila acá, no como parámetro libre de uno genérico.
5. **Timeout corto** (ej. 15-30s) — un comando de diagnóstico no debería
   tardar más que eso; si tarda, algo anda mal y debe cortar.
6. **Objetivo autorizado igual que el resto** — el host SSH debe estar en
   `config/authorized_targets.yaml` con la categoría `ssh_remote_ops`
   explícita, igual que `ics_scada_recon` para modbus.

| Herramienta (`tool_id`) | Comando remoto fijo | Estado |
|---|---|---|
| _(a definir con el usuario)_ | _(a definir)_ | pendiente |

**Fuera de alcance dentro de esta categoría (sin excepción):** cualquier
`tool_id` cuyo `argv_template` permita texto libre del usuario en el comando
remoto (ej. `ssh_run` con un parámetro `{command}` arbitrario) — eso sí
sería el shell libre que §3 excluye, sin importar que la llave sea propia.

---

## 3. Qué está **fuera** del alcance (prohibido por defecto)

Estas categorías **no** deben aparecer en `tool_catalog.yaml` ni ser invocables por el agente:

| Categoría | Ejemplos | Motivo |
|-----------|----------|--------|
| **Explotación** | `metasploit`, payloads, `sqlmap --dump` | Daño / extracción de datos |
| **Fuerza bruta** | `hydra`, `medusa`, `john` contra servicios remotos | Ataque de credenciales |
| **DoS / stress** | `hping3` flood, `slowloris` | Denegación de servicio |
| **MITM / sniffing en red ajena** | `ettercap`, `bettercap` en LAN no propia | Interceptación ilegal |
| **Evasión WAF / bypass CF** | Técnicas para saltar Cloudflare en terceros | Ya excluido en `AGENTS.md` §9 para scraping |
| **Post-explotación** | shells, persistencia, pivoting | Fuera de alcance del proyecto |
| **Wireless** | `aircrack-ng`, deauth | Requiere autorización y hardware específico |
| **Social engineering** | phishing kits | No automatizable de forma ética |
| **Orquestadores GUI** | `Legion`, `Angry IP Scanner` | Solo envuelven `nmap`/`nikto`/`netdiscover` ya integrados vía catálogo; sin binario headless con valor propio |
| **Extensiones de navegador** | `Wappalyzer` | No es CLI; `whatweb_safe`/`httpx_probe` cubren el mismo fingerprint headless |
| **Auto-orquestadores sin argv fijo** | `AutoRecon` | Decide en runtime qué sub-escaneos lanzar según servicios descubiertos — choca con el principio de catálogo cerrado (§5: "prohibido interpolar texto libre"); `run_pentest.py --phase full` cumple el mismo rol de forma controlada |
| **Categoría NSE `vuln` completa** | `nmap --script vuln` sin allowlist | Incluye scripts con payloads tipo exploit; solo se habilita el subconjunto seguro (`nmap_vuln_scripts`, §2.10.5) |

Si un usuario pide una acción de esta lista, el agente debe **rechazar**, citar este
documento y sugerir un pentest manual con equipo autorizado.

---

## 4. Modelo de autorización de objetivos

Archivo operativo: `config/authorized_targets.yaml` (ver `.example`).

```yaml
authorized_targets:
  - target: "midominio.com"
    type: domain          # domain | ip | cidr
    scope: "*.midominio.com"   # opcional
    authorized_by: "Juan Pérez / CISO"
    authorization_date: "2026-07-06"
    evidence: "ticket JIRA-1234 / contrato pentest"
    expires_at: "2026-12-31"   # null = revisar manualmente cada 90 días
    allowed_categories:
      - passive_recon
      - light_active_scan
    notes: "Solo horario 09:00-18:00 America/Lima"
```

**Reglas del `authorization_guard.py` (a implementar):**

1. Normalizar objetivo (dominio punycode, IP sin puerto salvo que el catálogo lo permita).
2. Comprobar que `target` o `scope` cubre el host solicitado.
3. Comprobar `expires_at` no vencido.
4. Comprobar que la categoría de la herramienta está en `allowed_categories` (si se define).
5. Si falla cualquier check → HTTP 403 / mensaje al chat; **cero ejecución**.

El **scraping de medios peruanos** en `config/sites/` **no** sustituye esta lista para
herramientas de seguridad.

---

## 5. Límites por ejecución (`tool_runner.py`)

Parámetros globales propuestos (configurables en `security_env/settings.yaml`):

| Parámetro | Valor propuesto | Motivo |
|-----------|-----------------|--------|
| `max_runtime_seconds` | 300 | Evitar scans colgados |
| `max_concurrent_jobs` | 2 | Proteger red y CPU |
| `default_rate_limit_rps` | 2 | No saturar objetivo |
| `max_output_bytes` | 5_000_000 | Evitar logs gigantes en chat |
| `require_authorization` | `true` | Siempre para categorías ≠ scraping |

Cada entrada del catálogo define: `id`, `category`, `binary`, `argv_template` con
placeholders tipados (`{host}`, `{port}`), `allowed_flags`, `timeout_seconds`.

**Prohibido:** interpolar texto libre del usuario en la shell (`f"nmap {user_input}"`).

---

## 6. Flujo agente (referencia)

```
Usuario (chat :1212)
    → security_scraping_agent (DeepSeek)
        → ¿Scraping? → pipeline existente (orchestrator, search)
        → ¿Seguridad? → authorization_guard → tool_runner → Kali (red interna Docker)
    → streaming de progreso + resumen en lenguaje natural
    → session_log (auditoría)
```

---

## 7. Despliegue (referencia)

- Un solo puerto host: **1212** → API de chat (`api/chat_endpoint.py`).
- Contenedor `kali`: **sin** puertos publicados; solo red Docker interna.
- `DEEPSEEK_API_KEY` en `.env`; nunca en código.

Detalle en CHANGELOG → entrada "docker-compose, puerto 1212".

---

## 8. Checklist antes de implementar código

- [x] Este documento revisado (`docs/alcance-seguridad.md`)
- [ ] Aprobación explícita del operador / responsable legal del despliegue
- [ ] `config/authorized_targets.yaml` creado a partir del `.example`
- [x] `security_env/tool_catalog.yaml` alineado solo con §2
- [x] Tests que verifiquen rechazo sin autorización (`tests/test_authorization_guard.py`)
- [x] Confirmar tool-use en DeepSeek (`agent/llm_client.py`)

---

## 9. Relación con otros documentos

| Documento | Rol |
|-----------|-----|
| `AGENTS.md` §9 | Uso autorizado del scraping |
| `CONTRIBUTING.md` | Cómo contribuir al scraper |
| `docs/troubleshooting-por-dominio.md` | Diagnóstico de medios peruanos |
| `CHANGELOG.md` `[Unreleased]` | Estado de implementación |
| `docs/integraciones-externas-5e.md` | OpenVAS/Nessus (export manual) |

---

## 10. Historial

| Fecha | Versión | Cambio |
|-------|---------|--------|
| 2026-07-07 | 1.6 | Retiro Shodan/Censys (`external_api_recon`); fases 6a–6f: escaneo ampliado (zmap, unicornscan), recon web (whatweb, httpx, wafw00f), TLS (`tls_analysis`), DNS (fierce), NSE seguro (`vuln_script_scanning`), ICS/SCADA solo-lectura (`ics_scada_recon`) |
| 2026-07-06 | 1.5 | Fases 5d–5e: fuzzing web (dirb, ffuf, wpscan) + APIs Shodan/Censys |
| 2026-07-06 | 1.4 | Categoría `osint_recon` + fase 5c (Amass pasivo, theHarvester, SpiderFoot) |
| 2026-07-06 | 1.3 | Categoría `network_discovery` + fase 5b (masscan, netdiscover, nuclei) |
| 2026-07-06 | 1.2 | Categoría `dns_enumeration` + fase 5a (nslookup, dnsenum, dnsrecon, sublist3r) |
| 2026-07-06 | 1.1 | Categorías `active_scanning`, `known_vuln_scanning`, `bounded_fuzzing` + herramientas |
| 2026-07-06 | 1.0 | Documento inicial; delimita alcance pre-`tool_runner` |
