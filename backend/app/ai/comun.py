"""Piezas comunes a todos los adaptadores de IA: prompt, esquema de la
herramienta, preparación de imágenes y parseo de la respuesta.

Se extrajeron de ``claude.py`` (que a su vez es copia de la v1) al añadir
OpenAI y DeepSeek como respaldo: los tres proveedores deben leer con
**exactamente** las mismas reglas (no inventar, ``null`` + ``campos_dudosos``
ante la duda), porque el usuario no sabe qué proveedor respondió.
"""

from __future__ import annotations

import base64
import logging
from abc import abstractmethod

from .. import imagenes
from ..config import config
from .base import CAMPOS_TIPO, CoinReader, LecturaMoneda, LecturaNoDisponibleError

log = logging.getLogger(__name__)

NOMBRE_HERRAMIENTA = "informar_lectura_moneda"

DESCRIPCION_HERRAMIENTA = (
    "Informa los campos del tipo de moneda leídos en las fotos. "
    "Usa null en cualquier campo que no se pueda leer con seguridad."
)

# JSON Schema de los argumentos de la herramienta. Cumple los requisitos del
# modo estricto de los tres proveedores: todas las propiedades en `required`
# y `additionalProperties: false`.
ESQUEMA_LECTURA = {
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
}

PROMPT_SISTEMA = """\
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


def lectura_fallida() -> LecturaMoneda:
    """Lectura vacía con todo marcado como dudoso: fuerza revisión manual completa."""
    return LecturaMoneda(
        pais=None,
        valor=None,
        anio=None,
        ceca=None,
        variante=None,
        campos_dudosos=list(CAMPOS_TIPO),
    )


def texto_o_none(valor: object) -> str | None:
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    return valor or None


def jpeg_base64(datos: bytes) -> str:
    """Imagen enderezada, reducida (RNF-4) y en JPEG, codificada en base64."""
    jpeg = imagenes.normalizar_a_jpeg(datos, config.resize_lado_largo)
    return base64.standard_b64encode(jpeg).decode("utf-8")


def texto_instruccion(hay_reverso: bool) -> str:
    if hay_reverso:
        return "Primera imagen: anverso. Segunda imagen: reverso. Lee los campos del tipo."
    return "Única imagen disponible: anverso. Lee los campos del tipo."


def parsear_datos(datos: object) -> LecturaMoneda:
    """Convierte los argumentos de la herramienta en una ``LecturaMoneda``.
    Lanza :class:`LecturaNoDisponibleError` si no tienen la forma esperada."""
    try:
        anio = datos.get("anio")
        anio = int(anio) if anio is not None else None
        campos_dudosos = [c for c in datos.get("campos_dudosos", []) if c in CAMPOS_TIPO]
        return LecturaMoneda(
            pais=texto_o_none(datos.get("pais")),
            valor=texto_o_none(datos.get("valor")),
            anio=anio,
            ceca=texto_o_none(datos.get("ceca")),
            variante=texto_o_none(datos.get("variante")),
            campos_dudosos=campos_dudosos,
        )
    except (TypeError, ValueError, AttributeError) as exc:
        raise LecturaNoDisponibleError(f"Respuesta con forma inesperada: {datos!r}") from exc


class LectorConIntento(CoinReader):
    """Base de los adaptadores reales: implementan :meth:`intentar_leer`
    (que lanza ante un fallo técnico) y heredan un :meth:`leer` que nunca
    lanza, como exige el contrato de ``CoinReader``."""

    @abstractmethod
    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda: ...

    def leer(self, imagen_anverso: bytes, imagen_reverso: bytes | None = None) -> LecturaMoneda:
        try:
            return self.intentar_leer(imagen_anverso, imagen_reverso)
        except LecturaNoDisponibleError as exc:
            log.warning("Lectura IA fallida (%s): %s", self.nombre, exc)
        except Exception:
            log.exception("Lectura IA fallida (%s, error inesperado)", self.nombre)
        return lectura_fallida()
