"""Normalización de campos del tipo para comparación exacta (RF-2, RF-14).

Política (ver CLAUDE.md §4 y Docs/AntCollect-Arquitectura-y-Requisitos.md §2.2):

- ``pais`` / ``ceca`` / ``variante``: minúsculas, sin acentos, espacios
  colapsados. ``None`` o vacío se normaliza a ``''`` (ceca/variante vacías
  cuentan como el mismo valor a efectos de unicidad).
- ``valor_texto``: misma normalización de texto (forma canónica para comparar).
- ``anio``: entero o ``None``. Un año ``None`` nunca debe considerarse igual a
  otro año ``None`` a efectos de "ya la tienes" (se trata aparte, en la lógica
  de coincidencias de coleccion.py).
"""

from __future__ import annotations

import unicodedata


def normalizar_texto(texto: str | None) -> str:
    """minúsculas + sin acentos + espacios colapsados. ``None``/``''`` -> ``''``."""
    if texto is None:
        return ""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sin_acentos.lower().split())


def normalizar_anio(anio: int | str | None) -> int | None:
    """Entero de 4 cifras o ``None`` si está vacío/ilegible."""
    if anio is None:
        return None
    if isinstance(anio, str):
        anio = anio.strip()
        if not anio:
            return None
    return int(anio)


def campos_normalizados(
    pais: str | None,
    valor_texto: str | None,
    ceca: str | None,
    variante: str | None,
) -> dict[str, str]:
    """Calcula las columnas ``*_norm`` a partir de los campos "bonitos"."""
    return {
        "pais_norm": normalizar_texto(pais),
        "valor_norm": normalizar_texto(valor_texto),
        "ceca_norm": normalizar_texto(ceca),
        "variante_norm": normalizar_texto(variante),
    }
