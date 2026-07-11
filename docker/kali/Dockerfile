# syntax=docker/dockerfile:1

FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive

# Herramientas alineadas a security_env/tool_catalog.yaml (§2 alcance-seguridad)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        whois \
        bind9-dnsutils \
        curl \
        nmap \
        gobuster \
        seclists \
        wget \
        netbase \
        dnsenum \
        dnsrecon \
        sublist3r \
        netdiscover \
    && update-ca-certificates \
    && printf 'precedence ::ffff:0:0/96  100\n' >> /etc/gai.conf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# nikto: el mirror principal puede devolver 499 (AV); no debe bloquear el resto del catálogo
RUN apt-get update \
    && apt-get install -y --no-install-recommends nikto \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# nuclei + plantillas (ProjectDiscovery); fallo de red no debe bloquear la imagen base
RUN apt-get update \
    && apt-get install -y --no-install-recommends nuclei \
    && nuclei -update-templates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# masscan: mirror Kali puede devolver 403; capa opcional
RUN apt-get update \
    && apt-get install -y --no-install-recommends masscan \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# OSINT avanzado (fase 5c)
RUN apt-get update \
    && apt-get install -y --no-install-recommends amass theharvester \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

RUN apt-get update \
    && apt-get install -y --no-install-recommends spiderfoot \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# Fuzzing web acotado (fase 5d)
RUN apt-get update \
    && apt-get install -y --no-install-recommends dirb ffuf wpscan \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

COPY docker/kali/bin/wpscan_enum_safe /usr/local/bin/wpscan_enum_safe
RUN chmod +x /usr/local/bin/wpscan_enum_safe

# Escaneo de puertos ampliado (fase 6a): zmap requiere sockets raw, mismo
# nivel de capabilities que masscan (ya funcional sin cap_add adicional)
RUN apt-get update \
    && apt-get install -y --no-install-recommends zmap unicornscan \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# Recon web / fingerprint (fase 6b): paquete httpx-toolkit evita choque con
# la librería Python httpx
RUN apt-get update \
    && apt-get install -y --no-install-recommends whatweb wafw00f httpx-toolkit \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# Análisis TLS/SSL (fase 6c)
RUN apt-get update \
    && apt-get install -y --no-install-recommends sslscan sslyze testssl.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# DNS adicional (fase 6d)
RUN apt-get update \
    && apt-get install -y --no-install-recommends fierce \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

# nmap_vuln_scripts (6e) y modbus_s7_discover (6f) reutilizan el binario
# nmap ya instalado y sus scripts NSE incluidos en el paquete (nmap-common)

# Cliente OpenSSH (fase 7 — administración remota autenticada, ver
# docs/alcance-seguridad.md §2.11). Solo el cliente, nunca un servidor SSH
# dentro del contenedor Kali.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    || true

COPY docker/kali/bin/openssl_cert_check /usr/local/bin/openssl_cert_check
RUN chmod +x /usr/local/bin/openssl_cert_check

# Sin puertos expuestos; scraper_agent invoca vía docker exec
CMD ["sleep", "infinity"]
