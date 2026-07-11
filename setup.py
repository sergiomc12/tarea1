"""Build de la extensión OPCIONAL de C++ (pybind11) para el motor de
hashing nativo de FIM -- ver CHANGELOG.md "candidatos a migración C/C++ +
pybind11" y src/scraper_agent/defense_env/_fim_native/fim_hash.cpp.

Nunca un requisito duro: si `pybind11` o un compilador de C++ no están
disponibles (ej. Windows sin toolchain, o un servidor sin build-essential),
`pip install -e .` sigue funcionando -- `defense_env/fim.py` hace su
propio try/except al importar la extensión compilada y cae a la
implementación Python pura si no está.
"""

from setuptools import setup

try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext

    ext_modules = [
        Pybind11Extension(
            "scraper_agent.defense_env._fim_native",
            ["src/scraper_agent/defense_env/_fim_native/fim_hash.cpp"],
            libraries=["ssl", "crypto"],
            cxx_std=17,
        ),
    ]
    cmdclass = {"build_ext": build_ext}
except ImportError:
    # pybind11 no instalado -- setup() sin ext_modules, instalación
    # puramente Python (fim.py usa el fallback automáticamente).
    ext_modules = []
    cmdclass = {}

setup(ext_modules=ext_modules, cmdclass=cmdclass)
