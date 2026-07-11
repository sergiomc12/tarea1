"""Categorías de herramientas alineadas a docs/alcance-seguridad.md."""

from __future__ import annotations

PASSIVE_RECON = "passive_recon"
LIGHT_ACTIVE_SCAN = "light_active_scan"
ACTIVE_SCANNING = "active_scanning"
KNOWN_VULN_SCANNING = "known_vuln_scanning"
BOUNDED_FUZZING = "bounded_fuzzing"
DNS_ENUMERATION = "dns_enumeration"
NETWORK_DISCOVERY = "network_discovery"
OSINT_RECON = "osint_recon"
TLS_ANALYSIS = "tls_analysis"
VULN_SCRIPT_SCANNING = "vuln_script_scanning"
ICS_SCADA_RECON = "ics_scada_recon"

ALL_CATEGORIES: frozenset[str] = frozenset(
    {
        PASSIVE_RECON,
        LIGHT_ACTIVE_SCAN,
        ACTIVE_SCANNING,
        KNOWN_VULN_SCANNING,
        BOUNDED_FUZZING,
        DNS_ENUMERATION,
        NETWORK_DISCOVERY,
        OSINT_RECON,
        TLS_ANALYSIS,
        VULN_SCRIPT_SCANNING,
        ICS_SCADA_RECON,
    }
)
