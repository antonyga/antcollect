"""Adaptador de ``CoinReader`` sobre la API de Anthropic.

Copia de src/antcollect/ai/claude.py (v1, ver catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6) con estos cambios
mínimos, todos en la frontera con el resto del backend o con la API:

- Lee clave/modelo/tamaño de ``app.config`` (pydantic-settings) en vez de
  las constantes de módulo de la v1.
- Prepara cada imagen con ``imagenes.normalizar_a_jpeg``, que además de
  redimensionar aplica la orientación EXIF (fotos de móvil).
- Pide la herramienta con ``tool_choice: auto`` + ``strict: true`` + una
  instrucción explícita, en vez de forzarla con ``tool_choice: tool``: los
  modelos actuales (``claude-sonnet-5-5``, ``claude-opus-5-5``...) rechazan
  con un 400 el ``tool_choice`` forzado, y así cambiar ``ANTCOLLECT_MODELO``
  no rompe la lectura. Si el modelo no llama a la herramienta, el resultado
  es una lectura fallida — igual que antes.
- ``max_tokens`` sube de 1024 a 4096 (margen para el razonamiento adaptativo)
  y un ``stop_reason == "refusal"`` se trata explícitamente como fallo.
- Prompt, esquema y parseo viven en ``comun.py`` (compartidos con los
  adaptadores de respaldo), e ``intentar_leer`` lanza
  ``LecturaNoDisponibleError`` ante un fallo técnico para que la cadena de
  respaldo (``respaldo.py``) pase al siguiente proveedor. Timeout corto y
  sin reintentos del SDK: si Claude falla, el respaldo entra al momento.

Único módulo del backend (junto con ``base.py``) que puede importar el SDK
``anthropic`` (RNF-6). Reglas de este adaptador (§7 CLAUDE.md):

- Las imágenes van en bloques base64, antes del texto, en el mensaje.
- Se redimensionan con Pillow antes de enviarlas (lado largo ``config.resize_lado_largo``).
- La lectura se pide con ``tool use``: el esquema son los 5 campos del tipo
  más ``campos_dudosos``, con esa única herramienta disponible.
- Ningún error (sin red, timeout, API, respuesta no parseable) se propaga al
  llamador: siempre se devuelve una ``LecturaMoneda``, en el peor caso vacía y
  con todos los campos marcados como dudosos. El error queda en el log.
"""

from __future__ import annotations

import logging

import anthropic

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
    "name": NOMBRE_HERRAMIENTA,
    "strict": True,
    "description": DESCRIPCION_HERRAMIENTA,
    "input_schema": ESQUEMA_LECTURA,
}


def _bloque_imagen(datos: bytes) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": jpeg_base64(datos)},
    }


class ClaudeCoinReader(LectorConIntento):
    """Adaptador de ``CoinReader`` que usa un modelo de visión de Anthropic."""

    nombre = "claude"

    def __init__(self, api_key: str | None = None, modelo: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else config.anthropic_api_key
        self._modelo = modelo if modelo is not None else config.modelo_ia

    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda:
        contenido = [_bloque_imagen(imagen_anverso)]
        if imagen_reverso is not None:
            contenido.append(_bloque_imagen(imagen_reverso))
        contenido.append({"type": "text", "text": texto_instruccion(imagen_reverso is not None)})

        try:
            cliente = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=config.ia_timeout_segundos,
                max_retries=config.ia_reintentos,
            )
            respuesta = cliente.messages.create(
                model=self._modelo,
                # Margen para el razonamiento adaptativo que los modelos actuales
                # hacen por defecto antes de llamar a la herramienta.
                max_tokens=4096,
                system=PROMPT_SISTEMA,
                tools=[_HERRAMIENTA],
                tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": contenido}],
            )
        except anthropic.APIError as exc:
            raise LecturaNoDisponibleError(f"API de Anthropic: {exc}") from exc

        self._loguear_coste(respuesta)
        return self._parsear_respuesta(respuesta)

    def _loguear_coste(self, respuesta: anthropic.types.Message) -> None:
        uso = respuesta.usage
        log.info(
            "Lectura IA ok: proveedor=claude modelo=%s entrada=%d salida=%d cache_lectura=%d",
            self._modelo,
            uso.input_tokens,
            uso.output_tokens,
            getattr(uso, "cache_read_input_tokens", None) or 0,
        )

    def _parsear_respuesta(self, respuesta: anthropic.types.Message) -> LecturaMoneda:
        if getattr(respuesta, "stop_reason", None) == "refusal":
            raise LecturaNoDisponibleError("la IA rechazó la petición (stop_reason=refusal)")

        bloque = next((b for b in respuesta.content if b.type == "tool_use"), None)
        if bloque is None:
            raise LecturaNoDisponibleError("sin lectura estructurada (sin bloque tool_use)")
        return parsear_datos(bloque.input)
