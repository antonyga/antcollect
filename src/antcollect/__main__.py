"""Punto de entrada: ``uv run python -m antcollect``."""

from __future__ import annotations

from . import config
from .db import inicializar
from .ui.app import lanzar


def main() -> None:
    config.configurar_logging()
    inicializar()
    lanzar()


if __name__ == "__main__":
    main()
