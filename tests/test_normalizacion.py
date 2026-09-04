"""Fase 1: normalización de campos del tipo."""

from __future__ import annotations

import pytest

from antcollect.normalizacion import campos_normalizados, normalizar_anio, normalizar_texto


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (None, ""),
        ("", ""),
        ("  ", ""),
        ("España", "espana"),
        ("ESPAÑA", "espana"),
        ("  Ciudad   del   Vaticano  ", "ciudad del vaticano"),
        ("Köln", "koln"),
    ],
)
def test_normalizar_texto(entrada, esperado):
    assert normalizar_texto(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (2002, 2002),
        ("2002", 2002),
        ("  1999 ", 1999),
    ],
)
def test_normalizar_anio(entrada, esperado):
    assert normalizar_anio(entrada) == esperado


def test_campos_normalizados_ceca_y_variante_vacias_dan_cadena_vacia():
    resultado = campos_normalizados("España", "2 euros", None, None)
    assert resultado == {
        "pais_norm": "espana",
        "valor_norm": "2 euros",
        "ceca_norm": "",
        "variante_norm": "",
    }


def test_campos_normalizados_distingue_mayusculas_y_acentos():
    a = campos_normalizados("España", "2 Euros", "M", "")
    b = campos_normalizados("españa", "2 euros", "m", None)
    assert a == b
