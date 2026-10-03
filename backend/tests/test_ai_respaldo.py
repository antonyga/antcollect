"""Tests de la cadena de respaldo (Claude → OpenAI → DeepSeek) y de cómo se
monta a partir de las claves configuradas."""

from __future__ import annotations

import pytest
from app.ai.base import CAMPOS_TIPO, CoinReader, LecturaMoneda, LecturaNoDisponibleError
from app.ai.claude import ClaudeCoinReader
from app.ai.deepseek import DeepSeekCoinReader
from app.ai.gpt import OpenAICoinReader
from app.ai.respaldo import CoinReaderConRespaldo
from app.dependencias import obtener_lector

_BUENA = LecturaMoneda(pais="España", valor="1 euro", anio=2005, ceca=None, variante=None)
_ILEGIBLE = LecturaMoneda(
    pais=None, valor=None, anio=None, ceca=None, variante=None, campos_dudosos=list(CAMPOS_TIPO)
)


class _Lector(CoinReader):
    def __init__(self, nombre: str, resultado: LecturaMoneda | Exception) -> None:
        self.nombre = nombre
        self._resultado = resultado
        self.llamadas = 0

    def leer(self, imagen_anverso, imagen_reverso=None):  # pragma: no cover - no se usa
        raise AssertionError("la cadena debe usar intentar_leer")

    def intentar_leer(self, imagen_anverso, imagen_reverso=None):
        self.llamadas += 1
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


def test_si_el_principal_responde_no_se_llama_a_los_respaldos():
    claude = _Lector("claude", _BUENA)
    gpt = _Lector("openai", _BUENA)

    lectura = CoinReaderConRespaldo([claude, gpt]).leer(b"a")

    assert lectura == _BUENA
    assert (claude.llamadas, gpt.llamadas) == (1, 0)


def test_si_falla_claude_responde_el_primer_respaldo():
    claude = _Lector("claude", LecturaNoDisponibleError("529 overloaded"))
    gpt = _Lector("openai", _BUENA)
    deepseek = _Lector("deepseek", _BUENA)

    lectura = CoinReaderConRespaldo([claude, gpt, deepseek]).leer(b"a", b"r")

    assert lectura == _BUENA
    assert (claude.llamadas, gpt.llamadas, deepseek.llamadas) == (1, 1, 0)


def test_si_fallan_claude_y_openai_responde_deepseek():
    claude = _Lector("claude", LecturaNoDisponibleError("timeout"))
    gpt = _Lector("openai", RuntimeError("error inesperado"))
    deepseek = _Lector("deepseek", _BUENA)

    assert CoinReaderConRespaldo([claude, gpt, deepseek]).leer(b"a") == _BUENA


def test_si_fallan_todos_leer_devuelve_lectura_vacia_sin_lanzar():
    cadena = CoinReaderConRespaldo(
        [
            _Lector("claude", LecturaNoDisponibleError("x")),
            _Lector("openai", LecturaNoDisponibleError("y")),
        ]
    )

    lectura = cadena.leer(b"a")

    assert lectura.pais is None
    assert set(lectura.campos_dudosos) == set(CAMPOS_TIPO)
    with pytest.raises(LecturaNoDisponibleError):
        cadena.intentar_leer(b"a")


def test_foto_ilegible_no_es_un_fallo_y_no_gasta_respaldos():
    """Si Claude responde bien pero no pudo leer nada, es una respuesta
    válida: preguntar a otro proveedor costaría el doble para lo mismo."""
    claude = _Lector("claude", _ILEGIBLE)
    gpt = _Lector("openai", _BUENA)

    lectura = CoinReaderConRespaldo([claude, gpt]).leer(b"a")

    assert lectura == _ILEGIBLE
    assert gpt.llamadas == 0


def test_cadena_vacia_no_se_permite():
    with pytest.raises(ValueError):
        CoinReaderConRespaldo([])


# --- Montaje según las claves configuradas ---


def _configurar(monkeypatch, anthropic="", openai="", deepseek=""):
    monkeypatch.setattr("app.dependencias.config.anthropic_api_key", anthropic)
    monkeypatch.setattr("app.dependencias.config.openai_api_key", openai)
    monkeypatch.setattr("app.dependencias.config.deepseek_api_key", deepseek)


def test_orden_claude_openai_deepseek(monkeypatch):
    _configurar(monkeypatch, "a", "o", "d")

    lector = obtener_lector()

    assert [type(x) for x in lector.lectores] == [
        ClaudeCoinReader,
        OpenAICoinReader,
        DeepSeekCoinReader,
    ]


def test_sin_claves_de_respaldo_solo_claude(monkeypatch):
    _configurar(monkeypatch, anthropic="a")

    assert [type(x) for x in obtener_lector().lectores] == [ClaudeCoinReader]


def test_sin_ninguna_clave_no_hay_lector(monkeypatch):
    _configurar(monkeypatch)

    assert obtener_lector() is None


def test_se_aceptan_los_nombres_de_variable_del_env_del_usuario(monkeypatch):
    from app.config import Config

    monkeypatch.setenv("OPEN_AI_API_KEY", "clave-openai")
    monkeypatch.setenv("DEEPSEE_API_KEY", "clave-deepseek")
    config = Config(_env_file=None)

    assert config.openai_api_key == "clave-openai"
    assert config.deepseek_api_key == "clave-deepseek"
