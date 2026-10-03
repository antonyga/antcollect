"""Adaptador de ``CoinReader`` sobre la API de OpenAI (respaldo de Claude).

Usa la **Responses API** (``client.responses.create``): la documentación de
OpenAI indica que los modelos GPT-6 requieren esa API para tool calling
(comprobado en developers.openai.com, 2026-10-03). Mismas reglas que el
adaptador de Claude: imágenes antes del texto, una sola herramienta estricta
con el esquema de ``comun.py``, y cualquier fallo técnico lanza
``LecturaNoDisponibleError`` desde ``intentar_leer``.

Único módulo del backend (junto con ``deepseek.py``) que importa el SDK
``openai`` (RNF-6).
"""

from __future__ import annotations

import json
import logging

import openai

from ..config import config
from .base import LecturaMoneda, LecturaNoDisponibleError
from .comun import (
    DESCRIPCION_HERRAMIENTA,
    ESQUEMA_LECTURA,
    NOMBRE_HERRAMIENTA,
    PROMPT_SISTEMA,
    LectorConIntento,
    jpeg_base64,
    parsear_datos,
    texto_instruccion,
)

log = logging.getLogger(__name__)

_HERRAMIENTA = {
    "type": "function",
    "name": NOMBRE_HERRAMIENTA,
    "description": DESCRIPCION_HERRAMIENTA,
    "parameters": ESQUEMA_LECTURA,
    "strict": True,
}


def _bloque_imagen(datos: bytes) -> dict:
    return {"type": "input_image", "image_url": f"data:image/jpeg;base64,{jpeg_base64(datos)}"}


class OpenAICoinReader(LectorConIntento):
    nombre = "openai"

    def __init__(self, api_key: str | None = None, modelo: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else config.openai_api_key
        self._modelo = modelo if modelo is not None else config.modelo_openai

    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda:
        contenido = [_bloque_imagen(imagen_anverso)]
        if imagen_reverso is not None:
            contenido.append(_bloque_imagen(imagen_reverso))
        contenido.append(
            {"type": "input_text", "text": texto_instruccion(imagen_reverso is not None)}
        )

        try:
            cliente = openai.OpenAI(
                api_key=self._api_key,
                timeout=config.ia_timeout_segundos,
                max_retries=config.ia_reintentos,
            )
            respuesta = cliente.responses.create(
                model=self._modelo,
                instructions=PROMPT_SISTEMA,
                tools=[_HERRAMIENTA],
                tool_choice="required",
                input=[{"role": "user", "content": contenido}],
            )
        except openai.OpenAIError as exc:
            raise LecturaNoDisponibleError(f"API de OpenAI: {exc}") from exc

        uso = getattr(respuesta, "usage", None)
        if uso is not None:
            log.info(
                "Lectura IA ok: proveedor=openai modelo=%s entrada=%s salida=%s",
                self._modelo,
                getattr(uso, "input_tokens", "?"),
                getattr(uso, "output_tokens", "?"),
            )

        llamada = next(
            (
                item
                for item in respuesta.output
                if item.type == "function_call" and item.name == NOMBRE_HERRAMIENTA
            ),
            None,
        )
        if llamada is None:
            raise LecturaNoDisponibleError("sin lectura estructurada (sin function_call)")
        try:
            datos = json.loads(llamada.arguments)
        except (TypeError, ValueError) as exc:
            raise LecturaNoDisponibleError("argumentos de la herramienta no son JSON") from exc
        return parsear_datos(datos)
