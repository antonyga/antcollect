"""Política de privacidad y términos (RNF-M3): públicas y con los datos del
responsable tomados de la configuración."""

from __future__ import annotations

import pytest
from app.config import config

from tests.conftest import crear_moneda, imagen_jpeg, registrar
from tests.test_imagenes import _subida


@pytest.mark.parametrize("ruta", ["/privacidad", "/terminos"])
async def test_paginas_legales_publicas_y_con_el_responsable(cliente, monkeypatch, ruta):
    monkeypatch.setattr(config, "legal_responsable", "Ana <Coleccionista>")
    monkeypatch.setattr(config, "legal_contacto", "privacidad@example.com")

    r = await cliente.get(ruta)  # sin JWT

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Ana &lt;Coleccionista&gt;" in r.text  # escapado
    assert "privacidad@example.com" in r.text
    assert "$" not in r.text  # ninguna variable sin sustituir


async def test_privacidad_menciona_a_los_proveedores_que_reciben_fotos(cliente):
    texto = (await cliente.get("/privacidad")).text
    for proveedor in ("Anthropic", "OpenAI", "DeepSeek", "Railway"):
        assert proveedor in texto


async def test_pagina_web_de_borrado_publica_con_formulario_y_contacto(cliente, monkeypatch):
    monkeypatch.setattr(config, "legal_contacto", "privacidad@example.com")

    r = await cliente.get("/borrar-cuenta")  # sin JWT

    assert r.status_code == 200
    assert '<form method="post" action="/borrar-cuenta">' in r.text
    assert "privacidad@example.com" in r.text
    assert "$" not in r.text


async def test_borrar_cuenta_desde_la_web_con_email_y_contrasena(cliente, almacen):
    """Google Play exige poder borrar la cuenta sin la app instalada."""
    cab = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")
    moneda = await crear_moneda(cliente, cab)
    await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/anverso", files=_subida(imagen_jpeg()), headers=cab
    )

    datos = {"email": "ana@example.com", "contrasena": "contrasena123"}
    r = await cliente.post("/borrar-cuenta", data=datos)

    assert r.status_code == 200
    assert "Cuenta borrada" in r.text
    assert not list(almacen._raiz.rglob("*.jpg"))
    r = await cliente.post("/auth/login", json=datos)
    assert r.status_code == 401
    assert (await cliente.get("/auth/yo", headers=luis)).status_code == 200


async def test_borrar_cuenta_desde_la_web_con_contrasena_mal_no_borra(cliente):
    cab = await registrar(cliente, "ana@example.com")

    r = await cliente.post(
        "/borrar-cuenta", data={"email": "ana@example.com", "contrasena": "equivocada"}
    )

    assert r.status_code == 403
    assert "No se ha borrado nada" in r.text
    assert (await cliente.get("/auth/yo", headers=cab)).status_code == 200
