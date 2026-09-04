"""Acceso a SQLite: conexión, esquema y ayuda transaccional.

Sin ORM y sin servidor de base de datos (RNF-2, RNF-8). Las escrituras se hacen
dentro de :func:`transaccion`, que hace commit al salir y rollback ante error
(RNF-7).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from . import config

# Política NULL vs '' (ver README y CLAUDE.md §4):
#   - ceca_norm / variante_norm: NOT NULL DEFAULT '' -> "vacío" es un único valor.
#   - anio: INTEGER que admite NULL -> año ilegible; nunca da "ya la tienes".
ESQUEMA = """
CREATE TABLE IF NOT EXISTS monedas (
    id              INTEGER PRIMARY KEY,
    pais            TEXT NOT NULL,
    valor_texto     TEXT NOT NULL,
    anio            INTEGER,
    ceca            TEXT,
    variante        TEXT,
    notas           TEXT,
    estado          TEXT NOT NULL DEFAULT 'en_coleccion',
    foto_anverso    TEXT,
    foto_reverso    TEXT,
    foto_detalle    TEXT,
    fecha_agregada  TEXT NOT NULL,

    pais_norm       TEXT NOT NULL,
    valor_norm      TEXT NOT NULL,
    ceca_norm       TEXT NOT NULL DEFAULT '',
    variante_norm   TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tipo
    ON monedas (pais_norm, valor_norm, anio, ceca_norm, variante_norm);
"""


def conectar() -> sqlite3.Connection:
    """Abre una conexión a la BD con filas accesibles por nombre."""
    config.asegurar_directorios()
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar() -> None:
    """Crea el esquema si no existe, y migra bases de datos de fases anteriores.

    Sin framework de migraciones (RNF-8): basta con comprobar columnas nuevas
    vía ``PRAGMA table_info`` y añadirlas con ``ALTER TABLE`` si faltan.
    """
    con = conectar()
    try:
        con.executescript(ESQUEMA)
        columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(monedas)")}
        if "foto_detalle" not in columnas:
            con.execute("ALTER TABLE monedas ADD COLUMN foto_detalle TEXT")
        con.commit()
    finally:
        con.close()


@contextmanager
def transaccion() -> Iterator[sqlite3.Connection]:
    """Contexto transaccional: commit al salir, rollback ante excepción."""
    con = conectar()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
