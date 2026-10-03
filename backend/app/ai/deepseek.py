"""Adaptador de ``CoinReader`` sobre la API de DeepSeek (segundo respaldo).

DeepSeek expone una API compatible con OpenAI (Chat Completions) en
``https://api.deepseek.com``, así que se usa el SDK oficial ``openai`` con
``base_url``. Según su documentación (api-docs.deepseek.com, 2026-10-03),
``deepseek-flash`` acepta imágenes (``image_url`` con data URI) y tool
calling. El modo estricto de DeepSeek está en beta (otro ``base_url``), así
que no se usa: la forma de la respuesta la valida ``comun.parsear_datos``.

Mismas reglas que los demás adaptadores; cualquier fallo técnico lanza
``LecturaNoDisponibleError`` desde ``intentar_leer``.
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

URL_BASE = "https://api.deepseek.com"

_HERRAMIENTA = {
    "type": "function",
    "function": {
        "name": NOMBRE_HERRAMIENTA,
        "description": DESCRIPCION_HERRAMIENTA,
        "parameters": ESQUEMA_LECTURA,
    },
}


def _bloque_imagen(datos: bytes) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{jpeg_base64(datos)}"},
    }


class DeepSeekCoinReader(LectorConIntento):
    nombre = "deepseek"

    def __init__(self, api_key: str | None = None, modelo: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else config.deepseek_api_key
        self._modelo = modelo if modelo is not None else config.modelo_deepseek

    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda:
        contenido = [_bloque_imagen(imagen_anverso)]
        if imagen_reverso is not None:
            contenido.append(_bloque_imagen(imagen_reverso))
        contenido.append({"type": "text", "text": texto_instruccion(imagen_reverso is not None)})

        try:
            cliente = openai.OpenAI(
                api_key=self._api_key,
                base_url=URL_BASE,
                timeout=config.ia_timeout_segundos,
                max_retries=config.ia_reintentos,
            )
            respuesta = cliente.chat.completions.create(
                model=self._modelo,
                messages=[
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "user", "content": contenido},
                ],
                tools=[_HERRAMIENTA],
            )
        except openai.OpenAIError as exc:
            raise LecturaNoDisponibleError(f"API de DeepSeek: {exc}") from exc

        uso = getattr(respuesta, "usage", None)
        if uso is not None:
            log.info(
                "Lectura IA ok: proveedor=deepseek modelo=%s entrada=%s salida=%s",
                self._modelo,
                getattr(uso, "prompt_tokens", "?"),
                getattr(uso, "completion_tokens", "?"),
            )

        try:
            llamadas = respuesta.choices[0].message.tool_calls or []
        except (AttributeError, IndexError) as exc:
            raise LecturaNoDisponibleError("respuesta sin choices") from exc
        llamada = next((c for c in llamadas if c.function.name == NOMBRE_HERRAMIENTA), None)
        if llamada is None:
            raise LecturaNoDisponibleError("sin lectura estructurada (sin tool_calls)")
        try:
            datos = json.loads(llamada.function.arguments)
        except (TypeError, ValueError) as exc:
            raise LecturaNoDisponibleError("argumentos de la herramienta no son JSON") from exc
        return parsear_datos(datos)
