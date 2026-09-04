"""Fase 0: la BD se inicializa con el esquema esperado."""

from __future__ import annotations

import sqlite3

from antcollect import config, db


def test_inicializar_crea_tabla_e_indice(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")

    db.inicializar()
    db.inicializar()  # idempotente

    con = sqlite3.connect(config.DB_PATH)
    try:
        tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indices = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        columnas = {r[1] for r in con.execute("PRAGMA table_info(monedas)")}
    finally:
        con.close()

    assert "monedas" in tablas
    assert "idx_tipo" in indices
    assert {"pais_norm", "valor_norm", "ceca_norm", "variante_norm", "anio"} <= columnas


def test_transaccion_hace_rollback_ante_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    db.inicializar()

    class FalloDeIA(Exception):
        pass

    try:
        with db.transaccion() as con:
            con.execute(
                "INSERT INTO monedas (pais, valor_texto, fecha_agregada, pais_norm, valor_norm) "
                "VALUES ('x', '1', '2026-01-01', 'x', '1')"
            )
            raise FalloDeIA
    except FalloDeIA:
        pass

    con = sqlite3.connect(config.DB_PATH)
    try:
        (total,) = con.execute("SELECT COUNT(*) FROM monedas").fetchone()
    finally:
        con.close()
    assert total == 0
