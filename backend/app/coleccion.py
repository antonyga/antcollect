"""Servicio de colección: alta, edición, borrado, búsqueda y duplicados.

Adaptado de src/antcollect/coleccion.py (v1): mismo contrato y mismos nombres
(dominio en español, ver CLAUDE.md §4), pero cada función recibe una sesión
async de SQLAlchemy y un ``usuario_id`` — todas las consultas están scopeadas
por usuario, así que la unicidad de "tipo" (RF-14) y la respuesta "¿la
tengo?" (RF-2) nunca cruzan datos entre usuarios. Ver catálogo de
reutilización en Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6.

Igual que en la v1, este módulo no decide nada por sí mismo: solo aplica lo
que ya se confirmó (el endpoint que lo llama es quien exige esa confirmación
humana antes de invocar `crear`/`editar`).
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from . import modelos
from .modelos import Moneda
from .normalizacion import campos_normalizados, normalizar_anio, normalizar_texto

_CAMPOS_EDITABLES = {
    "pais",
    "valor_texto",
    "anio",
    "ceca",
    "variante",
    "notas",
    "estado",
    "foto_anverso",
    "foto_reverso",
    "foto_detalle",
}


class TipoDuplicadoError(Exception):
    """Ya existe un tipo con los mismos campos normalizados para este usuario (RF-14)."""

    def __init__(self, existente: Moneda):
        self.existente = existente
        super().__init__(f"Ya existe un tipo igual: id={existente.id}")


async def obtener(sesion: AsyncSession, usuario_id: int, moneda_id: int) -> Moneda | None:
    resultado = await sesion.execute(
        select(Moneda).where(Moneda.id == moneda_id, Moneda.usuario_id == usuario_id)
    )
    return resultado.scalar_one_or_none()


async def listar(
    sesion: AsyncSession,
    usuario_id: int,
    *,
    texto: str | None = None,
    pais: str | None = None,
    valor: str | None = None,
    anio: int | None = None,
    estado: str | None = None,
) -> list[Moneda]:
    """Lista la colección del usuario aplicando los filtros dados (RF-9)."""
    consulta = select(Moneda).where(Moneda.usuario_id == usuario_id)

    if texto:
        patron_norm = f"%{normalizar_texto(texto)}%"
        patron_notas = f"%{texto.lower()}%"
        consulta = consulta.where(
            or_(
                Moneda.pais_norm.like(patron_norm),
                Moneda.valor_norm.like(patron_norm),
                Moneda.ceca_norm.like(patron_norm),
                Moneda.variante_norm.like(patron_norm),
                func.lower(func.coalesce(Moneda.notas, "")).like(patron_notas),
            )
        )
    if pais:
        consulta = consulta.where(Moneda.pais_norm.like(f"%{normalizar_texto(pais)}%"))
    if valor:
        consulta = consulta.where(Moneda.valor_norm.like(f"%{normalizar_texto(valor)}%"))
    if anio is not None:
        consulta = consulta.where(Moneda.anio == anio)
    if estado:
        consulta = consulta.where(Moneda.estado == estado)

    consulta = consulta.order_by(Moneda.pais, Moneda.valor_texto, Moneda.anio)
    resultado = await sesion.execute(consulta)
    return list(resultado.scalars().all())


async def existe_tipo_exacto(
    sesion: AsyncSession,
    usuario_id: int,
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
    ceca: str | None,
    variante: str | None,
    *,
    excluir_id: int | None = None,
) -> Moneda | None:
    """Busca, dentro de la colección del usuario, un tipo con los mismos 5
    campos normalizados (RF-14).

    Un ``anio`` desconocido (``None``) nunca cuenta como duplicado exacto —
    mismo motivo que en la v1: un año ilegible no puede confirmar que sea la
    misma moneda que otra también sin año.
    """
    anio_norm = normalizar_anio(anio)
    if anio_norm is None:
        return None

    norm = campos_normalizados(pais, valor_texto, ceca, variante)
    consulta = select(Moneda).where(
        Moneda.usuario_id == usuario_id,
        Moneda.pais_norm == norm["pais_norm"],
        Moneda.valor_norm == norm["valor_norm"],
        Moneda.anio == anio_norm,
        Moneda.ceca_norm == norm["ceca_norm"],
        Moneda.variante_norm == norm["variante_norm"],
    )
    if excluir_id is not None:
        consulta = consulta.where(Moneda.id != excluir_id)

    resultado = await sesion.execute(consulta)
    return resultado.scalar_one_or_none()


async def buscar_posibles_coincidencias(
    sesion: AsyncSession,
    usuario_id: int,
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
) -> list[Moneda]:
    """Candidatos del mismo país+valor (dentro de la colección del usuario)
    para que decida el humano (RF-2). Incluye monedas con ``anio`` NULL."""
    anio_norm = normalizar_anio(anio)
    norm = campos_normalizados(pais, valor_texto, None, None)
    consulta = select(Moneda).where(
        Moneda.usuario_id == usuario_id,
        Moneda.pais_norm == norm["pais_norm"],
        Moneda.valor_norm == norm["valor_norm"],
    )
    if anio_norm is not None:
        consulta = consulta.where(or_(Moneda.anio == anio_norm, Moneda.anio.is_(None)))
    consulta = consulta.order_by(Moneda.anio, Moneda.ceca_norm, Moneda.variante_norm)

    resultado = await sesion.execute(consulta)
    return list(resultado.scalars().all())


async def comprobar_tipo(
    sesion: AsyncSession,
    usuario_id: int,
    *,
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
    ceca: str | None,
    variante: str | None,
    campos_dudosos: list[str] | None = None,
) -> tuple[str, Moneda | None, list[Moneda]]:
    """Responde "¿la tengo?" (RF-2) sobre los campos propuestos/confirmados.

    Devuelve ``(categoria, exacta, posibles)`` — misma semántica que en la v1:
    ``"exacta"`` / ``"parcial"`` / ``"ninguna"``.
    """
    dudosos = campos_dudosos or []
    anio_norm = normalizar_anio(anio)

    if anio_norm is not None and not dudosos:
        exacta = await existe_tipo_exacto(
            sesion, usuario_id, pais, valor_texto, anio_norm, ceca, variante
        )
        if exacta is not None:
            return "exacta", exacta, []

    posibles = await buscar_posibles_coincidencias(sesion, usuario_id, pais, valor_texto, anio_norm)
    if posibles:
        return "parcial", None, posibles
    return "ninguna", None, []


async def crear(
    sesion: AsyncSession,
    usuario_id: int,
    *,
    pais: str,
    valor_texto: str,
    anio: int | str | None,
    ceca: str | None = None,
    variante: str | None = None,
    notas: str | None = None,
    estado: str = modelos.EN_COLECCION,
    foto_anverso: str | None = None,
    foto_reverso: str | None = None,
    foto_detalle: str | None = None,
) -> Moneda:
    """Da de alta un tipo nuevo para el usuario (RF-6). Lanza
    :class:`TipoDuplicadoError` si ya existe (dentro de SU colección)."""
    if estado not in modelos.ESTADOS:
        raise ValueError(f"Estado desconocido: {estado!r}")

    anio_norm = normalizar_anio(anio)
    existente = await existe_tipo_exacto(
        sesion, usuario_id, pais, valor_texto, anio_norm, ceca, variante
    )
    if existente is not None:
        raise TipoDuplicadoError(existente)

    norm = campos_normalizados(pais, valor_texto, ceca, variante)
    moneda = Moneda(
        usuario_id=usuario_id,
        pais=pais.strip(),
        valor_texto=valor_texto.strip(),
        anio=anio_norm,
        ceca=ceca,
        variante=variante,
        notas=notas,
        estado=estado,
        foto_anverso=foto_anverso,
        foto_reverso=foto_reverso,
        foto_detalle=foto_detalle,
        **norm,
    )
    sesion.add(moneda)
    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        existente = await existe_tipo_exacto(
            sesion, usuario_id, pais, valor_texto, anio_norm, ceca, variante
        )
        raise TipoDuplicadoError(existente) from exc

    await sesion.refresh(moneda)
    return moneda


async def editar(
    sesion: AsyncSession, usuario_id: int, moneda_id: int, **cambios: object
) -> Moneda:
    """Edita una moneda del usuario (RF-6). Solo cambia los campos en ``cambios``."""
    actual = await obtener(sesion, usuario_id, moneda_id)
    if actual is None:
        raise ValueError(f"No existe la moneda {moneda_id}")

    desconocidos = set(cambios) - _CAMPOS_EDITABLES
    if desconocidos:
        raise ValueError(f"Campos desconocidos: {desconocidos}")

    datos = {campo: getattr(actual, campo) for campo in _CAMPOS_EDITABLES}
    datos.update(cambios)
    datos["anio"] = normalizar_anio(datos["anio"])

    if datos["estado"] not in modelos.ESTADOS:
        raise ValueError(f"Estado desconocido: {datos['estado']!r}")

    existente = await existe_tipo_exacto(
        sesion,
        usuario_id,
        datos["pais"],
        datos["valor_texto"],
        datos["anio"],
        datos["ceca"],
        datos["variante"],
        excluir_id=moneda_id,
    )
    if existente is not None:
        raise TipoDuplicadoError(existente)

    norm = campos_normalizados(
        datos["pais"], datos["valor_texto"], datos["ceca"], datos["variante"]
    )
    for campo, valor in datos.items():
        if campo == "pais" or campo == "valor_texto":
            valor = valor.strip()
        setattr(actual, campo, valor)
    for campo, valor in norm.items():
        setattr(actual, campo, valor)

    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        existente = await existe_tipo_exacto(
            sesion,
            usuario_id,
            datos["pais"],
            datos["valor_texto"],
            datos["anio"],
            datos["ceca"],
            datos["variante"],
            excluir_id=moneda_id,
        )
        raise TipoDuplicadoError(existente) from exc

    await sesion.refresh(actual)
    return actual


async def borrar(sesion: AsyncSession, usuario_id: int, moneda_id: int) -> None:
    """Borra una moneda del usuario (RF-11). Confirmación es cosa del cliente.

    Solo borra la fila: las fotos en el almacén las borra antes la ruta
    (``rutas/coleccion.py``), que es quien tiene acceso al almacén.
    """
    moneda = await obtener(sesion, usuario_id, moneda_id)
    if moneda is None:
        return
    await sesion.delete(moneda)
    await sesion.commit()
