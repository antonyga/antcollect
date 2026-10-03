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
  y un ``stop_reason == "refusal"`` se trata explícitamente como lectura
  fallida.

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

import base64
import logging

import anthropic

from .. import imagenes
from ..config import config
from .base import CAMPOS_TIPO, CoinReader, LecturaMoneda

log = logging.getLogger(__name__)

_NOMBRE_HERRAMIENTA = "informar_lectura_moneda"

_HERRAMIENTA = {
    "name": _NOMBRE_HERRAMIENTA,
    "strict": True,
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

Informa el resultado únicamente llamando a la herramienta informar_lectura_moneda,
siempre, aunque no puedas leer ningún campo (en ese caso, todos a null y todos
en campos_dudosos). No respondas con texto.
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
    jpeg = imagenes.normalizar_a_jpeg(datos, config.resize_lado_largo)
    b64 = base64.standard_b64encode(jpeg).decode("utf-8")
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
        self._api_key = api_key if api_key is not None else config.anthropic_api_key
        self._modelo = modelo if modelo is not None else config.modelo_ia

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
                # Margen para el razonamiento adaptativo que los modelos actuales
                # hacen por defecto antes de llamar a la herramienta.
                max_tokens=4096,
                system=_PROMPT_SISTEMA,
                tools=[_HERRAMIENTA],
                tool_choice={"type": "auto"},
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
        if getattr(respuesta, "stop_reason", None) == "refusal":
            log.warning("La IA rechazó la petición de lectura (stop_reason=refusal)")
            return _lectura_fallida()

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
