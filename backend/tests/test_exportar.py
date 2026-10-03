"""Tests de exportación CSV/JSON (RF-13), adaptados de tests/test_exportar.py
(v1) al backend: respuesta HTTP en streaming y solo la colección propia."""

from __future__ import annotations

import csv
import io
import json

from .conftest import crear_moneda, imagen_jpeg, registrar


async def test_exportar_csv(cliente):
    cab = await registrar(cliente)
    await crear_moneda(cliente, cab, pais="España", valor_texto="2 euros", anio=2002)
    await crear_moneda(cliente, cab, pais="Francia", valor_texto="1 euro", anio=None, notas="ñ")

    r = await cliente.get("/exportar", params={"formato": "csv"}, headers=cab)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('.csv"')
    texto = r.content.decode("utf-8-sig")
    filas = list(csv.DictReader(io.StringIO(texto)))
    assert [f["pais"] for f in filas] == ["España", "Francia"]
    assert filas[1]["anio"] == ""
    assert filas[1]["notas"] == "ñ"
    assert filas[0]["ceca"] == ""
    assert "pais_norm" not in filas[0]
    assert "usuario_id" not in filas[0]


async def test_exportar_csv_empieza_con_bom_para_excel(cliente):
    cab = await registrar(cliente)

    r = await cliente.get("/exportar", headers=cab)

    assert r.content.startswith("﻿".encode())


async def test_exportar_json(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)
    await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/anverso",
        files={"archivo": ("a.jpg", imagen_jpeg(), "image/jpeg")},
        headers=cab,
    )

    r = await cliente.get("/exportar", params={"formato": "json"}, headers=cab)

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    datos = json.loads(r.content)
    assert len(datos) == 1
    assert datos[0]["pais"] == "España"
    assert datos[0]["anio"] == 2002
    assert datos[0]["foto_anverso"] == f"/coleccion/{moneda['id']}/imagenes/anverso"
    assert datos[0]["foto_reverso"] is None


async def test_exportar_json_vacio_es_lista_valida(cliente):
    cab = await registrar(cliente)

    r = await cliente.get("/exportar", params={"formato": "json"}, headers=cab)

    assert json.loads(r.content) == []


async def test_exportar_solo_incluye_la_coleccion_propia(cliente):
    ana = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")
    await crear_moneda(cliente, ana, pais="España")
    await crear_moneda(cliente, luis, pais="Portugal")

    r = await cliente.get("/exportar", params={"formato": "json"}, headers=ana)

    assert [m["pais"] for m in json.loads(r.content)] == ["España"]


async def test_exportar_formato_desconocido_se_rechaza(cliente):
    cab = await registrar(cliente)

    r = await cliente.get("/exportar", params={"formato": "xml"}, headers=cab)

    assert r.status_code == 422


async def test_exportar_sin_token_devuelve_401(cliente):
    r = await cliente.get("/exportar")
    assert r.status_code == 401
