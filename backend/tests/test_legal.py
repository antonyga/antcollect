"""Política de privacidad y términos (RNF-M3): públicas y con los datos del
responsable tomados de la configuración."""

from __future__ import annotations

import pytest
from app.config import config


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
