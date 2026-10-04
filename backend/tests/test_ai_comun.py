"""Piezas comunes de los adaptadores de IA: limpieza de la respuesta."""

from __future__ import annotations

import pytest
from app.ai.comun import limpiar_ceca, parsear_datos


@pytest.mark.parametrize(
    ("propuesta", "esperada"),
    [
        ("M", "M"),
        ("M (ceca de Madrid)", "M"),
        ("M (bajo corona)", "M"),
        ("  KM  ", "KM"),
        ("A (Berlín) (estrella)", "A"),
        ("cornucopia", "cornucopia"),
        ("(ilegible)", None),
        ("", None),
        (None, None),
        (7, None),
    ],
)
def test_limpiar_ceca_deja_solo_la_marca(propuesta, esperada):
    assert limpiar_ceca(propuesta) == esperada


def test_parsear_datos_limpia_la_ceca_pero_no_la_variante():
    # La ceca se compara exacta (forma parte del tipo); la variante se deja
    # tal cual: un paréntesis puede ser parte legítima de su nombre.
    lectura = parsear_datos(
        {
            "pais": "España",
            "valor": "2 euros",
            "anio": 2005,
            "ceca": "M (ceca de Madrid)",
            "variante": "Quijote (IV centenario)",
            "campos_dudosos": [],
        }
    )

    assert lectura.ceca == "M"
    assert lectura.variante == "Quijote (IV centenario)"
