"""Exportación de la colección a formatos portables (RF-13).

Complementa la copia de seguridad real (`antcollect.db` + `imagenes/`, ver
README) con un volcado legible/portable de los campos "bonitos" de cada
moneda. No incluye las columnas `*_norm`: son un detalle interno para
comparar tipos, no datos que el usuario haya introducido.
"""

from __future__ import annotations

import csv
import json
import tempfile
from datetime import datetime
from pathlib import Path

from .modelo import Moneda

CAMPOS_EXPORTADOS = (
    "id",
    "pais",
    "valor_texto",
    "anio",
    "ceca",
    "variante",
    "notas",
    "estado",
    "foto_anverso",
    "foto_reverso",
    "foto_detalle",
    "fecha_agregada",
)


def _fila(m: Moneda) -> dict[str, object]:
    return {campo: getattr(m, campo) for campo in CAMPOS_EXPORTADOS}


def _nombre(sufijo: str) -> str:
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"antcollect_coleccion_{marca}.{sufijo}"


def exportar_csv(monedas: list[Moneda]) -> Path:
    """Escribe la colección a un CSV temporal y devuelve su ruta."""
    ruta = Path(tempfile.gettempdir()) / _nombre("csv")
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_EXPORTADOS)
        escritor.writeheader()
        for m in monedas:
            fila = _fila(m)
            fila["ceca"] = fila["ceca"] or ""
            fila["variante"] = fila["variante"] or ""
            fila["notas"] = fila["notas"] or ""
            escritor.writerow(fila)
    return ruta


def exportar_json(monedas: list[Moneda]) -> Path:
    """Escribe la colección a un JSON temporal y devuelve su ruta."""
    ruta = Path(tempfile.gettempdir()) / _nombre("json")
    datos = [_fila(m) for m in monedas]
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
