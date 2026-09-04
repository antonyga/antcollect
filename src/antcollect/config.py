"""Configuración de AntCollect.

Carga ``.env`` (si existe) y expone rutas y ajustes. La clave de API y demás
valores se leen del entorno; nada se hardcodea (RNF-5).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Raíz del repo: .../src/antcollect/config.py -> subir dos niveles.
RAIZ = Path(__file__).resolve().parents[2]


def _ruta(variable: str, defecto: str) -> Path:
    """Resuelve una ruta de config: relativa se ancla a la raíz del repo."""
    valor = os.getenv(variable, defecto)
    ruta = Path(valor).expanduser()
    return ruta if ruta.is_absolute() else RAIZ / ruta


DB_PATH: Path = _ruta("ANTCOLLECT_DB", "antcollect.db")
IMAGENES_DIR: Path = _ruta("ANTCOLLECT_IMAGENES", "imagenes")
LOG_PATH: Path = _ruta("ANTCOLLECT_LOG", "antcollect.log")

MODELO_IA: str = os.getenv("ANTCOLLECT_MODELO", "claude-sonnet-5")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
RESIZE_LADO_LARGO: int = int(os.getenv("ANTCOLLECT_RESIZE_LADO_LARGO", "1568"))
RESIZE_ALMACENAMIENTO: int = int(os.getenv("ANTCOLLECT_RESIZE_ALMACENAMIENTO", "2000"))
PUERTO: int = int(os.getenv("ANTCOLLECT_PUERTO", "7860"))


def hay_ia() -> bool:
    """True si hay clave de API configurada para la lectura por IA."""
    return bool(ANTHROPIC_API_KEY)


def asegurar_directorios() -> None:
    """Crea la carpeta de imágenes si no existe."""
    IMAGENES_DIR.mkdir(parents=True, exist_ok=True)


_logging_configurado = False


def configurar_logging() -> None:
    """Registra coste/errores de la app en ``antcollect.log`` (RNF-4). Idempotente."""
    global _logging_configurado
    if _logging_configurado:
        return
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _logging_configurado = True
