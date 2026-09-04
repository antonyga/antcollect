"""Dataclasses del dominio de AntCollect."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

EN_COLECCION = "en_coleccion"
DUPLICADA = "duplicada"
PARA_INTERCAMBIO = "para_intercambio"
ESTADOS = (EN_COLECCION, DUPLICADA, PARA_INTERCAMBIO)


@dataclass
class Moneda:
    """Un tipo de moneda catalogado (pais + valor + anio + ceca + variante)."""

    id: int | None
    pais: str
    valor_texto: str
    anio: int | None
    ceca: str | None
    variante: str | None
    notas: str | None
    estado: str
    foto_anverso: str | None
    foto_reverso: str | None
    foto_detalle: str | None
    fecha_agregada: str
    pais_norm: str
    valor_norm: str
    ceca_norm: str
    variante_norm: str

    @classmethod
    def desde_fila(cls, fila: sqlite3.Row) -> Moneda:
        return cls(**{campo: fila[campo] for campo in fila.keys()})
