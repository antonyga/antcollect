"""Adaptador de ``CoinReader`` sobre la API de Anthropic (Fase 2).

Único módulo de la app (junto con ``base.py``) que puede importar el SDK
``anthropic`` (RNF-6). Reglas de este adaptador (§7 CLAUDE.md):

- Las imágenes van en bloques base64, antes del texto, en el mensaje.
- Se redimensionan con Pillow antes de enviarlas (lado largo ``RESIZE_LADO_LARGO``).
- La lectura se pide con ``tool use``: el esquema son los 5 campos del tipo
  más ``campos_dudosos``, forzando la llamada a esa única herramienta.
- Ningún error (sin red, timeout, API, respuesta no parseable) se propaga al
  llamador: siempre se devuelve una ``LecturaMoneda``, en el peor caso vacía y
  con todos los campos marcados como dudosos. El error queda en el log.
"""

from __future__ import annotations

import base64
import io
import logging

import anthropic
from PIL import Image

from .. import config, imagenes
from .base import CAMPOS_TIPO, CoinReader, LecturaMoneda

log = logging.getLogger(__name__)

_NOMBRE_HERRAMIENTA = "informar_lectura_moneda"

_HERRAMIENTA = {
    "name": _NOMBRE_HERRAMIENTA,
    "description": (
        "Informa los campos del tipo de moneda leídos en las fotos. "
        "Usa null en cualquier campo que no se pueda leer con seguridad."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pais": {
                "type": ["string", "null"],
                "description": "País emisor tal como aparece en la moneda.",
            },
            "valor": {
                "type": ["string", "null"],
                "description": "Valor facial tal como aparece, p. ej. '2 euros', '50 centavos'.",
            },
            "anio": {
                "type": ["integer", "null"],
                "description": "Año de acuñación como número de 4 cifras, o null si no es legible.",
            },
            "ceca": {
                "type": ["string", "null"],
                "description": "Marca de ceca si es visible, o null.",
            },
            "variante": {
                "type": ["string", "null"],
                "description": (
                    "Detalle distintivo visible (variante, error, tipo de canto...), o null."
                ),
            },
            "campos_dudosos": {
                "type": "array",
                "items": {"type": "string", "enum": list(CAMPOS_TIPO)},
                "description": "Nombres de los campos anteriores que no se leyeron con seguridad.",
            },
        },
        "required": ["pais", "valor", "anio", "ceca", "variante", "campos_dudosos"],
        "additionalProperties": False,
    },
}

_PROMPT_SISTEMA = """\
Eres un asistente que extrae datos de fotos de monedas para un catálogo personal.

Se te dan una o dos fotos de la misma moneda (anverso y, si está disponible,
reverso). Extrae solo lo que puedas leer con seguridad en las imágenes:

- pais: país emisor tal como aparece en la moneda, o el país al que
  pertenece si es evidente por el escudo o los símbolos aunque el nombre no
  esté escrito.
- valor: valor facial tal como aparece (p. ej. "2 euros", "50 centavos", "1 dólar").
- anio: año de acuñación como número de 4 cifras, o null si no se lee con
  seguridad. Nunca inventes ni redondees un año parcialmente visible.
- ceca: marca de ceca (letra o símbolo) si es visible, o null.
- variante: cualquier detalle distintivo visible (error de acuñación, símbolo
  de ceca especial, tipo de canto, etc.), o null si no hay nada reseñable.

Usa el anverso y el reverso de forma complementaria: si un dato solo se ve en
una de las dos caras, úsalo igualmente.

No inventes ni completes con conocimiento general de numismática lo que no se
vea en la foto. Si un campo no es legible con seguridad, ponlo a null y añade
su nombre a campos_dudosos. Ante la duda, marca el campo como dudoso: es
preferible que una persona lo revise a que quede mal catalogado.

Informa el resultado únicamente llamando a la herramienta proporcionada.
"""


def _lectura_fallida() -> LecturaMoneda:
    """Lectura vacía con todo marcado como dudoso: fuerza revisión manual completa."""
    return LecturaMoneda(
        pais=None,
        valor=None,
        anio=None,
        ceca=None,
        variante=None,
        campos_dudosos=list(CAMPOS_TIPO),
    )


def _texto_o_none(valor: object) -> str | None:
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    return valor or None


def _bloque_imagen(datos: bytes) -> dict:
    imagen = Image.open(io.BytesIO(datos))
    imagen = imagenes.redimensionar(imagen.convert("RGB"), config.RESIZE_LADO_LARGO)
    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", quality=90)
    b64 = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
    }


def _texto_instruccion(hay_reverso: bool) -> str:
    if hay_reverso:
        return "Primera imagen: anverso. Segunda imagen: reverso. Lee los campos del tipo."
    return "Única imagen disponible: anverso. Lee los campos del tipo."


class ClaudeCoinReader(CoinReader):
    """Adaptador de ``CoinReader`` que usa un modelo de visión de Anthropic."""

    def __init__(self, api_key: str | None = None, modelo: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else config.ANTHROPIC_API_KEY
        self._modelo = modelo if modelo is not None else config.MODELO_IA

    def leer(self, imagen_anverso: bytes, imagen_reverso: bytes | None = None) -> LecturaMoneda:
        try:
            contenido = [_bloque_imagen(imagen_anverso)]
            if imagen_reverso is not None:
                contenido.append(_bloque_imagen(imagen_reverso))
            contenido.append(
                {"type": "text", "text": _texto_instruccion(imagen_reverso is not None)}
            )

            cliente = anthropic.Anthropic(api_key=self._api_key)
            respuesta = cliente.messages.create(
                model=self._modelo,
                max_tokens=1024,
                system=_PROMPT_SISTEMA,
                tools=[_HERRAMIENTA],
                tool_choice={"type": "tool", "name": _NOMBRE_HERRAMIENTA},
                messages=[{"role": "user", "content": contenido}],
            )
        except anthropic.APIError as exc:
            log.warning("Lectura IA fallida (API de Anthropic): %s", exc)
            return _lectura_fallida()
        except Exception:
            log.exception("Lectura IA fallida (error inesperado)")
            return _lectura_fallida()

        self._loguear_coste(respuesta)
        return self._parsear_respuesta(respuesta)

    def _loguear_coste(self, respuesta: anthropic.types.Message) -> None:
        uso = respuesta.usage
        log.info(
            "Lectura IA ok: modelo=%s entrada=%d salida=%d cache_lectura=%d",
            self._modelo,
            uso.input_tokens,
            uso.output_tokens,
            getattr(uso, "cache_read_input_tokens", None) or 0,
        )

    def _parsear_respuesta(self, respuesta: anthropic.types.Message) -> LecturaMoneda:
        bloque = next((b for b in respuesta.content if b.type == "tool_use"), None)
        if bloque is None:
            log.error("La IA no devolvió una lectura estructurada (sin bloque tool_use)")
            return _lectura_fallida()

        try:
            datos = bloque.input
            anio = datos.get("anio")
            anio = int(anio) if anio is not None else None
            campos_dudosos = [c for c in datos.get("campos_dudosos", []) if c in CAMPOS_TIPO]
            return LecturaMoneda(
                pais=_texto_o_none(datos.get("pais")),
                valor=_texto_o_none(datos.get("valor")),
                anio=anio,
                ceca=_texto_o_none(datos.get("ceca")),
                variante=_texto_o_none(datos.get("variante")),
                campos_dudosos=campos_dudosos,
            )
        except (TypeError, ValueError, AttributeError):
            log.exception("Respuesta de la IA con forma inesperada: %r", bloque)
            return _lectura_fallida()
