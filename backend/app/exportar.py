"""Exportación de la colección de un usuario a CSV/JSON (RF-13).

Adaptado de src/antcollect/exportar.py (v1): mismos campos y mismo formato
(CSV en UTF-8 con BOM para que Excel lo abra bien, JSON legible), pero en vez
de escribir un fichero temporal en el disco del servidor, genera el contenido
por trozos para devolverlo como respuesta HTTP en streaming. Ver catálogo de
reutilización en Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6.

Igual que en la v1, no incluye las columnas ``*_norm`` (detalle interno) ni
``usuario_id``. Las fotos se exportan como la ruta de la API desde la que se
descargan (las claves del almacén son un detalle interno).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime

from .esquemas import url_imagen
from .modelos import Moneda

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
    fila: dict[str, object] = {campo: getattr(m, campo) for campo in CAMPOS_EXPORTADOS}
    for cara in ("anverso", "reverso", "detalle"):
        campo = f"foto_{cara}"
        fila[campo] = url_imagen(m.id, cara) if fila[campo] else None
    fila["fecha_agregada"] = m.fecha_agregada.isoformat()
    return fila


def nombre_archivo(sufijo: str) -> str:
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"antcollect_coleccion_{marca}.{sufijo}"


def generar_csv(monedas: list[Moneda]) -> Iterator[str]:
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=CAMPOS_EXPORTADOS)

    def _vaciar() -> str:
        trozo = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return trozo

    escritor.writeheader()
    yield "﻿" + _vaciar()
    for m in monedas:
        fila = _fila(m)
        for campo in ("ceca", "variante", "notas", "foto_anverso", "foto_reverso", "foto_detalle"):
            fila[campo] = fila[campo] or ""
        escritor.writerow(fila)
        yield _vaciar()


def generar_json(monedas: list[Moneda]) -> Iterator[str]:
    yield "["
    for i, m in enumerate(monedas):
        separador = "," if i else ""
        yield separador + "\n  " + json.dumps(_fila(m), ensure_ascii=False)
    yield "\n]\n" if monedas else "]\n"
