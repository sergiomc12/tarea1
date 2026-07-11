# Llaves SSH para administración remota

Poné acá tu llave **privada** (ej. `id_ed25519`) para que el contenedor Kali
la use al conectarse al dispositivo remoto declarado en `.env`
(`SSH_REMOTE_HOST`, `SSH_REMOTE_USER`, `SSH_REMOTE_KEY_PATH`).

- Este directorio está en `.gitignore` — nada de lo que pongas acá (salvo
  este README) se sube al repositorio.
- Se monta como **solo lectura** dentro del contenedor Kali
  (`./config/ssh:/run/secrets/ssh:ro` en `docker-compose.yml`).
- Permisos recomendados en el host: `chmod 600 config/ssh/id_ed25519` (el
  cliente SSH rechaza llaves con permisos demasiado abiertos).
- No se soporta autenticación por contraseña por diseño — ver
  `docs/alcance-seguridad.md` §2.11.
