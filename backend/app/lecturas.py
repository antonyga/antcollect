"""Cuota diaria de lecturas por IA por usuario (RF-M3, RNF-M2).

Cada lectura cuesta dinero real al operador del backend (no al usuario, como
en la v1), así que la cuota no es opcional. El día es el día natural en UTC.

Patrón "reservar y devolver": antes de llamar a la IA se inserta la lectura y
*después* se cuenta, incluyéndola. Si dos peticiones del mismo usuario llegan
a la vez con una sola lectura libre, ambas ven el exceso y ambas se rechazan:
se puede perder una lectura en esa carrera, pero nunca se supera la cuota (el
coste queda acotado, que es lo que importa). Si la IA falla sin leer nada, la
reserva se devuelve: un fallo de red o de la API no gasta cuota.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .modelos import LecturaIA


class CuotaAgotadaError(Exception):
    def __init__(self, limite: int):
        self.limite = limite
        super().__init__(f"Cuota diaria de lecturas IA agotada ({limite})")


def ahora() -> datetime:
    """Punto único de "qué hora es" (los tests lo sustituyen)."""
    return datetime.now(UTC)


def _inicio_del_dia(momento: datetime) -> datetime:
    return momento.replace(hour=0, minute=0, second=0, microsecond=0)


async def usadas_hoy(sesion: AsyncSession, usuario_id: int) -> int:
    momento = ahora()
    resultado = await sesion.execute(
        select(func.count(LecturaIA.id)).where(
            LecturaIA.usuario_id == usuario_id,
            LecturaIA.creada_en >= _inicio_del_dia(momento),
        )
    )
    return resultado.scalar_one()


async def reservar(sesion: AsyncSession, usuario_id: int, limite: int) -> LecturaIA:
    """Consume una lectura de la cuota de hoy o lanza :class:`CuotaAgotadaError`."""
    reserva = LecturaIA(usuario_id=usuario_id, creada_en=ahora())
    sesion.add(reserva)
    await sesion.commit()

    if await usadas_hoy(sesion, usuario_id) > limite:
        await sesion.delete(reserva)
        await sesion.commit()
        raise CuotaAgotadaError(limite)
    return reserva


async def devolver(sesion: AsyncSession, reserva: LecturaIA) -> None:
    """Anula una reserva (la lectura no llegó a producir nada útil)."""
    await sesion.delete(reserva)
    await sesion.commit()
