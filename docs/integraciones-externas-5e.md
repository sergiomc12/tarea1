# Integraciones externas

Escáneres **fuera del contenedor Kali** (integración documental, sin binario
invocable desde el agente). Alineado a `docs/alcance-seguridad.md` §2.9.

> **2026-07-07:** Shodan y Censys fueron **retirados** del catálogo (eran las
> únicas integraciones de "APIs de terceros" de este documento — ver
> `CHANGELOG.md`, "Removed 2026-07-07 — retiro de Shodan/Censys"). Este
> archivo ahora documenta solo OpenVAS/GVM y Nessus, que nunca tuvieron
> `tool_id` invocable.

---

## 1. OpenVAS / GVM (sin binario en Kali)

OpenVAS/GVM **no** se instala en la imagen Kali (tamaño, licencia, daemon aparte).

**Flujo recomendado:**

1. Ejecutar escaneo en instancia OpenVAS/GVM autorizada (ventana acordada).
2. Exportar informe (XML/HTML/CSV) desde la consola GVM.
3. Guardar en `output/openvas/<host>_<fecha>.xml`.
4. Correlacionar manualmente o con scripts propios fuera de `tool_runner.py`.

No hay `tool_id` para lanzar escaneos GVM desde el agente — evita DoS y explotación
automática contra terceros.

---

## 2. Nessus / Tenable (sin binario en Kali)

Nessus Professional requiere licencia Tenable; no se empaqueta en el contenedor.

**Flujo recomendado:**

1. Crear política de escaneo **no destructivo** en Nessus (credenciales en vault del operador).
2. Limitar alcance al host de `authorized_targets.yaml`.
3. Exportar `.nessus` o PDF a `output/nessus/`.
4. Revisión humana antes de compartir hallazgos en el chat.

Variables opcionales documentadas en `.env.example` (`NESSUS_URL`, `NESSUS_ACCESS_KEY`)
para integraciones futuras vía API REST; **no** forman parte del catálogo cerrado.

---

## 3. Cuotas y ética

| Proveedor | Límite operativo |
|-----------|------------------|
| OpenVAS/Nessus | Ventana de mantenimiento acordada; solo activos autorizados |

Si la fuente devuelve 429/rate-limit, el agente debe informar al usuario y **no**
reintentar en bucle.

---

## 4. Relación con otros documentos

| Documento | Rol |
|-----------|-----|
| `docs/alcance-seguridad.md` §2.9–2.10 | Retiro Shodan/Censys; categorías `tls_analysis`, `vuln_script_scanning`, `ics_scada_recon` |
| `security_env/tool_catalog.yaml` | Wrappers permitidos |
| `CHANGELOG.md` | Estado de implementación |
