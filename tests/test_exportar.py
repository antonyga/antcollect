"""Fase 5: exportación de la colección a CSV/JSON (RF-13)."""

from __future__ import annotations

import csv
import json

import pytest

from antcollect import coleccion, config, db, exportar
from antcollect.coleccion import crear


@pytest.fixture(autouse=True)
def _bd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    db.inicializar()


def test_exportar_csv_incluye_las_columnas_esperadas():
    crear(pais="España", valor_texto="2 euros", anio=2002, ceca="M", variante=None)
    crear(pais="Francia", valor_texto="1 euro", anio=None, ceca=None, variante=None)

    ruta = exportar.exportar_csv(coleccion.listar())

    with ruta.open(encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))

    assert list(filas[0].keys()) == list(exportar.CAMPOS_EXPORTADOS)
    fila_espana = next(f for f in filas if f["pais"] == "España")
    assert fila_espana["anio"] == "2002"
    assert fila_espana["ceca"] == "M"
    fila_francia = next(f for f in filas if f["pais"] == "Francia")
    assert fila_francia["anio"] == ""
    assert fila_francia["ceca"] == ""
    ruta.unlink()


def test_exportar_json_preserva_anio_nulo_como_null():
    crear(pais="Francia", valor_texto="1 euro", anio=None, ceca=None, variante=None)

    ruta = exportar.exportar_json(coleccion.listar())
    datos = json.loads(ruta.read_text(encoding="utf-8"))

    assert len(datos) == 1
    assert datos[0]["anio"] is None
    assert datos[0]["pais"] == "Francia"
    assert set(datos[0].keys()) == set(exportar.CAMPOS_EXPORTADOS)
    ruta.unlink()
