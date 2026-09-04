"""Fase 2: adaptador ClaudeCoinReader — parseo, mapeo y camino de error.

No llama a la API real: se sustituye ``anthropic.Anthropic`` por un cliente
falso que devuelve respuestas construidas a mano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from PIL import Image

from antcollect.ai import claude as claude_mod
from antcollect.ai.base import CAMPOS_TIPO, LecturaMoneda


def _imagen_bytes(ancho: int = 20, alto: int = 10) -> bytes:
    import io

    buffer = io.BytesIO()
    Image.new("RGB", (ancho, alto), color="blue").save(buffer, "JPEG")
    return buffer.getvalue()


@dataclass
class _BloqueToolUse:
    input: dict
    type: str = "tool_use"


@dataclass
class _Uso:
    input_tokens: int = 10
    output_tokens: int = 5
    cache_read_input_tokens: int = 0


@dataclass
class _RespuestaFalsa:
    content: list = field(default_factory=list)
    usage: _Uso = field(default_factory=_Uso)


class _ClienteFalso:
    """Sustituye a ``anthropic.Anthropic``: registra la llamada y devuelve lo dado."""

    ultima_llamada: dict | None = None

    def __init__(self, respuesta=None, excepcion=None):
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        _ClienteFalso.ultima_llamada = kwargs
        if self._excepcion is not None:
            raise self._excepcion
        return self._respuesta


def _lector(monkeypatch, respuesta=None, excepcion=None) -> claude_mod.ClaudeCoinReader:
    fake = _ClienteFalso(respuesta=respuesta, excepcion=excepcion)
    monkeypatch.setattr(claude_mod.anthropic, "Anthropic", lambda **kwargs: fake)
    return claude_mod.ClaudeCoinReader(api_key="clave-de-prueba", modelo="claude-sonnet-5")


def test_leer_parsea_lectura_completa(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[
            _BloqueToolUse(
                input={
                    "pais": "España",
                    "valor": "2 euros",
                    "anio": 2002,
                    "ceca": None,
                    "variante": None,
                    "campos_dudosos": [],
                }
            )
        ]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lectura = lector.leer(_imagen_bytes(), _imagen_bytes())

    assert lectura == LecturaMoneda(
        pais="España", valor="2 euros", anio=2002, ceca=None, variante=None, campos_dudosos=[]
    )


def test_leer_conserva_campos_dudosos_y_descarta_desconocidos(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[
            _BloqueToolUse(
                input={
                    "pais": "Francia",
                    "valor": "1 euro",
                    "anio": None,
                    "ceca": None,
                    "variante": None,
                    "campos_dudosos": ["anio", "algo_inventado"],
                }
            )
        ]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lectura = lector.leer(_imagen_bytes())

    assert lectura.anio is None
    assert lectura.campos_dudosos == ["anio"]


def test_leer_normaliza_cadenas_vacias_a_none(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[
            _BloqueToolUse(
                input={
                    "pais": "Italia",
                    "valor": "1 lira",
                    "anio": 1950,
                    "ceca": "  ",
                    "variante": "",
                    "campos_dudosos": [],
                }
            )
        ]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lectura = lector.leer(_imagen_bytes())

    assert lectura.ceca is None
    assert lectura.variante is None


def test_leer_sin_bloque_tool_use_devuelve_lectura_fallida(monkeypatch):
    respuesta = _RespuestaFalsa(content=[])
    lector = _lector(monkeypatch, respuesta=respuesta)

    lectura = lector.leer(_imagen_bytes())

    assert lectura.pais is None
    assert set(lectura.campos_dudosos) == set(CAMPOS_TIPO)


def test_leer_con_forma_inesperada_devuelve_lectura_fallida(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[_BloqueToolUse(input={"pais": "España", "anio": "no-es-un-numero"})]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lectura = lector.leer(_imagen_bytes())

    assert set(lectura.campos_dudosos) == set(CAMPOS_TIPO)


def test_leer_ante_error_de_red_no_propaga_excepcion(monkeypatch):
    peticion = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    excepcion = anthropic.APIConnectionError(request=peticion)
    lector = _lector(monkeypatch, excepcion=excepcion)

    lectura = lector.leer(_imagen_bytes())

    assert lectura.pais is None
    assert set(lectura.campos_dudosos) == set(CAMPOS_TIPO)


def test_leer_ante_error_inesperado_no_propaga_excepcion(monkeypatch):
    lector = _lector(monkeypatch, excepcion=RuntimeError("boom"))

    lectura = lector.leer(_imagen_bytes())

    assert lectura.pais is None
    assert set(lectura.campos_dudosos) == set(CAMPOS_TIPO)


def test_leer_envia_imagenes_antes_del_texto(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[
            _BloqueToolUse(
                input={
                    "pais": None,
                    "valor": None,
                    "anio": None,
                    "ceca": None,
                    "variante": None,
                    "campos_dudosos": list(CAMPOS_TIPO),
                }
            )
        ]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lector.leer(_imagen_bytes(), _imagen_bytes())

    contenido = _ClienteFalso.ultima_llamada["messages"][0]["content"]
    tipos = [bloque["type"] for bloque in contenido]
    assert tipos == ["image", "image", "text"]
    assert _ClienteFalso.ultima_llamada["tool_choice"] == {
        "type": "tool",
        "name": "informar_lectura_moneda",
    }


def test_leer_sin_reverso_solo_envia_una_imagen(monkeypatch):
    respuesta = _RespuestaFalsa(
        content=[
            _BloqueToolUse(
                input={
                    "pais": None,
                    "valor": None,
                    "anio": None,
                    "ceca": None,
                    "variante": None,
                    "campos_dudosos": list(CAMPOS_TIPO),
                }
            )
        ]
    )
    lector = _lector(monkeypatch, respuesta=respuesta)

    lector.leer(_imagen_bytes())

    contenido = _ClienteFalso.ultima_llamada["messages"][0]["content"]
    tipos = [bloque["type"] for bloque in contenido]
    assert tipos == ["image", "text"]


@pytest.mark.parametrize("api_key", ["clave-directa", None])
def test_constructor_usa_config_por_defecto_si_no_se_pasa_clave(monkeypatch, api_key):
    monkeypatch.setattr(claude_mod.config, "ANTHROPIC_API_KEY", "clave-de-config")
    monkeypatch.setattr(claude_mod.config, "MODELO_IA", "modelo-de-config")

    lector = claude_mod.ClaudeCoinReader(api_key=api_key)

    esperado = api_key if api_key is not None else "clave-de-config"
    assert lector._api_key == esperado
    assert lector._modelo == "modelo-de-config"
