"""Contrato de lectura por IA (RNF-6): el resto de la app depende solo de esto.

Copia de src/antcollect/ai/base.py (v1) ampliada para el backend con
``intentar_leer`` / ``LecturaNoDisponibleError``, que permiten encadenar
varios proveedores (Claude principal, OpenAI y DeepSeek de respaldo). El
contrato original (``leer`` nunca lanza) no cambia.

Nadie fuera de ``ai/`` debe importar el SDK de ningún proveedor de IA directamente. Cambiar
de proveedor de IA es escribir un nuevo adaptador que implemente ``CoinReader``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Nombres de los campos del "tipo" de moneda (§1 CLAUDE.md), en el orden en
# que se comparan para saber si dos monedas son el mismo tipo.
CAMPOS_TIPO = ("pais", "valor", "anio", "ceca", "variante")


@dataclass
class LecturaMoneda:
    """Lo que la IA propone a partir de las fotos. Nunca se guarda tal cual:
    siempre pasa antes por confirmación humana (§2 CLAUDE.md, RF-3)."""

    pais: str | None
    valor: str | None
    anio: int | None
    ceca: str | None
    variante: str | None
    campos_dudosos: list[str] = field(default_factory=list)


class LecturaNoDisponibleError(Exception):
    """Fallo *técnico* de un proveedor de IA (sin red, timeout, error de la
    API, rechazo, respuesta sin la herramienta o no parseable). Distinto de
    una lectura válida en la que la IA no pudo leer ningún campo."""


class CoinReader(ABC):
    """Lee los campos del tipo a partir de una o dos fotos de una moneda."""

    #: Nombre corto del proveedor, para los logs.
    nombre: str = "desconocido"

    @abstractmethod
    def leer(self, imagen_anverso: bytes, imagen_reverso: bytes | None = None) -> LecturaMoneda:
        """Nunca lanza excepción al llamador: un fallo se refleja como una
        ``LecturaMoneda`` con todos los campos ``None`` y todos dudosos."""
        raise NotImplementedError

    def intentar_leer(
        self, imagen_anverso: bytes, imagen_reverso: bytes | None = None
    ) -> LecturaMoneda:
        """Como :meth:`leer`, pero un fallo técnico lanza
        :class:`LecturaNoDisponibleError` en vez de devolver la lectura vacía.
        Es lo que usa la cadena de respaldo (``ai/respaldo.py``) para saber
        cuándo pasar al siguiente proveedor.

        Implementación por defecto para adaptadores que solo definen
        ``leer``: no puede distinguir un fallo técnico de "no se leyó nada",
        así que trata la lectura vacía como fallo. Los adaptadores reales la
        sobrescriben.
        """
        lectura = self.leer(imagen_anverso, imagen_reverso)
        if es_lectura_fallida(lectura):
            raise LecturaNoDisponibleError(f"{self.nombre}: lectura vacía")
        return lectura


def es_lectura_fallida(lectura: LecturaMoneda) -> bool:
    """True si ``lectura`` es la lectura vacía que devuelve un ``CoinReader``
    cuando la IA no ha podido leer nada (sin red, error de la API, etc.)."""
    return all(getattr(lectura, campo) is None for campo in CAMPOS_TIPO) and set(
        lectura.campos_dudosos
    ) == set(CAMPOS_TIPO)
