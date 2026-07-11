#!/bin/sh
# Loop continuo del agente de defensa a nivel de sistema operativo.
# Corre EN EL SERVIDOR REAL (no en un contenedor) -- ver CHANGELOG.md
# "defensa activa a nivel de sistema operativo".
#
# Uso:
#   chmod +x scripts/host_agent_loop.sh
#   HOST_AGENT_INTERVAL_SECONDS=60 ./scripts/host_agent_loop.sh &
#
# Para producción real, preferir un servicio systemd en vez de nohup/&
# (reinicio automático, logs vía journald) -- ver scripts/tarea1-host-agent.service
# de referencia (documentado, no instalado automáticamente).
#
# El "|| true" es deliberado: un ciclo que encuentra un ataque (exit code 1)
# no debe tumbar el loop -- tiene que seguir vigilando después de responder,
# no reiniciarse.
set -e

INTERVAL="${HOST_AGENT_INTERVAL_SECONDS:-60}"

if [ ! -f output/security/host_fim_baseline.json ]; then
  echo "[host_agent_loop] sin baseline de FIM del host, generando uno nuevo"
  scraper-agent fim-baseline --config config/defense/host_fim_watch.yaml --output output/security/host_fim_baseline.json
fi

while true; do
  scraper-agent defense-host-agent-cycle || true
  sleep "$INTERVAL"
done
