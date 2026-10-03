"""Cadena de respaldo entre proveedores de IA: Claude principal, y si falla,
OpenAI y después DeepSeek, en el momento y dentro de la misma petición, para
que el usuario no vea un error (decisión del usuario, 2026-10-03).

"Falla" = fallo *técnico* (``LecturaNoDisponibleError`` o cualquier
excepción: sin red, timeout, error/sobrecarga de la API, rechazo, respuesta
sin la herramienta o con forma inválida). Si un proveedor responde bien pero
no pudo leer ningún campo (foto borrosa), eso es una respuesta válida y NO se
pregunta a otro: el resultado sería el mismo y costaría el doble.

La propia cadena es un ``CoinReader``, así que el resto del backend no sabe
cuántos proveedores hay detrás (RNF-6). Solo si fallan todos se devuelve la
lectura vacía y la app pasa al modo manual, como antes.
"""

from __future__ import annotations

import logging

from .base import CoinReader, LecturaMoneda, LecturaNoDisponibleError
from .comun import LectorConIntento

log = logging.getLogger(__name__)


class CoinReaderConRespaldo(LectorConIntento):
    nombre = "cadena"

    def __init__(self, lectores: list[CoinReader]) -> None:
        if not lectores:
            raise ValueError("La cadena de respaldo necesita al menos un lector")
        self._lectores = lectores
        self.nombre = "+".join(lector.nombre for lector in lectores)

    @property
    def lectores(self) -> list[CoinReader]:
        return list(self._lectores)

    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda:
        errores: list[str] = []
        for i, lector in enumerate(self._lectores):
            try:
                lectura = lector.intentar_leer(imagen_anverso, imagen_reverso)
            except LecturaNoDisponibleError as exc:
                errores.append(f"{lector.nombre}: {exc}")
            except Exception as exc:
                log.exception("Error inesperado en el lector %s", lector.nombre)
                errores.append(f"{lector.nombre}: {exc!r}")
            else:
                if i > 0:
                    log.warning(
                        "Lectura servida por el respaldo %s tras fallar: %s",
                        lector.nombre,
                        "; ".join(errores),
                    )
                return lectura
            log.warning("Lector %s falló, se prueba el siguiente: %s", lector.nombre, errores[-1])

        raise LecturaNoDisponibleError("fallaron todos los proveedores: " + "; ".join(errores))
