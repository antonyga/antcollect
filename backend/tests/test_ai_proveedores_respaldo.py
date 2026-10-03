"""Adaptadores de respaldo (OpenAI y DeepSeek): formato de la petición,
parseo de la respuesta y conversión de fallos en ``LecturaNoDisponibleError``.

No llaman a ninguna API: se sustituye ``openai.OpenAI`` por un cliente falso.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from app.ai import deepseek as deepseek_mod
from app.ai import gpt as gpt_mod
from app.ai.base import CAMPOS_TIPO, LecturaNoDisponibleError
from PIL import Image

_ARGUMENTOS = {
    "pais": "Francia",
    "valor": "1 euro",
    "anio": 2010,
    "ceca": None,
    "variante": None,
    "campos_dudosos": ["ceca"],
}


def _imagen() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 10), "blue").save(buffer, "JPEG")
    return buffer.getvalue()


class _ClienteFalso:
    def __init__(self, respuesta=None, excepcion=None):
        self.llamada: dict | None = None
        self.opciones: dict | None = None
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.responses = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamada = kwargs
        if self._excepcion is not None:
            raise self._excepcion
        return self._respuesta


def _instalar(monkeypatch, modulo, cliente):
    def _fabrica(**kwargs):
        cliente.opciones = kwargs
        return cliente

    monkeypatch.setattr(modulo.openai, "OpenAI", _fabrica)


def _error_conexion():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://x"))


# --- OpenAI (Responses API) ---


def _respuesta_openai(*items):
    return SimpleNamespace(
        output=list(items), usage=SimpleNamespace(input_tokens=1, output_tokens=1)
    )


def _llamada_openai(argumentos, nombre="informar_lectura_moneda"):
    return SimpleNamespace(type="function_call", name=nombre, arguments=argumentos)


def test_openai_parsea_la_lectura(monkeypatch):
    cliente = _ClienteFalso(_respuesta_openai(_llamada_openai(json.dumps(_ARGUMENTOS))))
    _instalar(monkeypatch, gpt_mod, cliente)

    lectura = gpt_mod.OpenAICoinReader(api_key="k", modelo="m").intentar_leer(_imagen(), _imagen())

    assert (lectura.pais, lectura.valor, lectura.anio) == ("Francia", "1 euro", 2010)
    assert lectura.campos_dudosos == ["ceca"]


def test_openai_envia_imagenes_antes_del_texto_y_herramienta_estricta(monkeypatch):
    cliente = _ClienteFalso(_respuesta_openai(_llamada_openai(json.dumps(_ARGUMENTOS))))
    _instalar(monkeypatch, gpt_mod, cliente)

    gpt_mod.OpenAICoinReader(api_key="k", modelo="m").intentar_leer(_imagen(), _imagen())

    contenido = cliente.llamada["input"][0]["content"]
    assert [c["type"] for c in contenido] == ["input_image", "input_image", "input_text"]
    assert contenido[0]["image_url"].startswith("data:image/jpeg;base64,")
    herramienta = cliente.llamada["tools"][0]
    assert herramienta["type"] == "function" and herramienta["strict"] is True
    assert cliente.llamada["instructions"]
    assert cliente.opciones["max_retries"] == 0


def test_openai_sin_llamada_a_la_herramienta_es_fallo(monkeypatch):
    texto = SimpleNamespace(type="message")
    _instalar(monkeypatch, gpt_mod, _ClienteFalso(_respuesta_openai(texto)))

    with pytest.raises(LecturaNoDisponibleError):
        gpt_mod.OpenAICoinReader(api_key="k", modelo="m").intentar_leer(_imagen())


def test_openai_argumentos_no_json_es_fallo(monkeypatch):
    _instalar(monkeypatch, gpt_mod, _ClienteFalso(_respuesta_openai(_llamada_openai("{roto"))))

    with pytest.raises(LecturaNoDisponibleError):
        gpt_mod.OpenAICoinReader(api_key="k", modelo="m").intentar_leer(_imagen())


def test_openai_error_de_red_es_fallo_y_leer_no_lanza(monkeypatch):
    _instalar(monkeypatch, gpt_mod, _ClienteFalso(excepcion=_error_conexion()))
    lector = gpt_mod.OpenAICoinReader(api_key="k", modelo="m")

    with pytest.raises(LecturaNoDisponibleError):
        lector.intentar_leer(_imagen())
    assert set(lector.leer(_imagen()).campos_dudosos) == set(CAMPOS_TIPO)


# --- DeepSeek (Chat Completions compatible con OpenAI) ---


def _respuesta_deepseek(tool_calls):
    mensaje = SimpleNamespace(tool_calls=tool_calls, content=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=mensaje)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )


def _tool_call(argumentos, nombre="informar_lectura_moneda"):
    return SimpleNamespace(function=SimpleNamespace(name=nombre, arguments=argumentos))


def test_deepseek_parsea_la_lectura_y_usa_su_url(monkeypatch):
    cliente = _ClienteFalso(_respuesta_deepseek([_tool_call(json.dumps(_ARGUMENTOS))]))
    _instalar(monkeypatch, deepseek_mod, cliente)

    lectura = deepseek_mod.DeepSeekCoinReader(api_key="k", modelo="m").intentar_leer(_imagen())

    assert (lectura.pais, lectura.anio) == ("Francia", 2010)
    assert cliente.opciones["base_url"] == "https://api.deepseek.com"


def test_deepseek_envia_prompt_de_sistema_e_imagenes_antes_del_texto(monkeypatch):
    cliente = _ClienteFalso(_respuesta_deepseek([_tool_call(json.dumps(_ARGUMENTOS))]))
    _instalar(monkeypatch, deepseek_mod, cliente)

    deepseek_mod.DeepSeekCoinReader(api_key="k", modelo="m").intentar_leer(_imagen(), _imagen())

    sistema, usuario = cliente.llamada["messages"]
    assert sistema["role"] == "system"
    assert [c["type"] for c in usuario["content"]] == ["image_url", "image_url", "text"]
    assert cliente.llamada["tools"][0]["function"]["name"] == "informar_lectura_moneda"


def test_deepseek_sin_tool_calls_es_fallo(monkeypatch):
    _instalar(monkeypatch, deepseek_mod, _ClienteFalso(_respuesta_deepseek(None)))

    with pytest.raises(LecturaNoDisponibleError):
        deepseek_mod.DeepSeekCoinReader(api_key="k", modelo="m").intentar_leer(_imagen())


def test_deepseek_forma_inesperada_es_fallo(monkeypatch):
    malos = json.dumps({"anio": "no-es-un-numero"})
    _instalar(monkeypatch, deepseek_mod, _ClienteFalso(_respuesta_deepseek([_tool_call(malos)])))

    with pytest.raises(LecturaNoDisponibleError):
        deepseek_mod.DeepSeekCoinReader(api_key="k", modelo="m").intentar_leer(_imagen())


def test_deepseek_error_de_api_es_fallo(monkeypatch):
    _instalar(monkeypatch, deepseek_mod, _ClienteFalso(excepcion=_error_conexion()))

    with pytest.raises(LecturaNoDisponibleError):
        deepseek_mod.DeepSeekCoinReader(api_key="k", modelo="m").intentar_leer(_imagen())
