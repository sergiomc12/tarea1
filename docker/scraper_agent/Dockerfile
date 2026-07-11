# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Playwright Chromium + cliente docker CLI para exec en contenedor kali +
# build-essential/libssl-dev/python3-dev para la extensión OPCIONAL de C++
# (defense_env/_fim_native, ver CHANGELOG.md "candidatos a migración
# C/C++ + pybind11") -- si esto llegara a faltar en una imagen base
# distinta, el paso de build de la extensión más abajo está diseñado para
# no tumbar el resto de la imagen (`|| true`).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        docker.io \
        build-essential \
        libssl-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md setup.py ./
COPY src ./src
COPY config ./config
COPY scraper-schema.json ./

RUN pip install --upgrade pip \
    && pip install -e ".[api]" \
    && playwright install --with-deps chromium

# Extensión OPCIONAL de C++ -- deliberadamente en un RUN separado con
# "|| true": si pybind11/el compilador fallan por cualquier motivo, la
# imagen sigue construyéndose igual (defense_env/fim.py cae a hashlib puro
# en runtime). Nunca debe poder tumbar el build completo.
# `setuptools` explícito: `pip install -e .` lo usa en un entorno de build
# AISLADO temporal (PEP 517) y no queda instalado en el entorno real --
# `python setup.py build_ext` corre fuera de ese aislamiento y necesita su
# propia instalación. Bug real, encontrado en el primer intento de build.
RUN pip install setuptools pybind11 \
    && (python setup.py build_ext --inplace \
        && echo "[build] extensión nativa de FIM compilada OK" \
        || echo "[build] extensión nativa de FIM NO se pudo compilar -- fim.py usará el fallback Python puro")

RUN mkdir -p output output/sessions output/checkpoints

EXPOSE 8000

CMD ["uvicorn", "scraper_agent.api.chat_endpoint:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
