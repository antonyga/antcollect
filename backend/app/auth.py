"""Servicio de autenticación y cuentas (RF-M1): registro, login, refresco de
token y borrado de cuenta. Lógica de negocio separada de las rutas FastAPI a
propósito — la v1 dejó validación/orquestación mezclada en handlers de UI
(`ui/app.py`, ver catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6) y aquí se evita
repetir ese problema.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .esquemas import ParDeTokens
from .modelos import Usuario
from .seguridad import (
    TipoToken,
    TokenInvalidoError,
    crear_token_acceso,
    crear_token_refresco,
    decodificar_token,
    hashear_contrasena,
    verificar_contrasena,
)


class EmailYaRegistradoError(Exception):
    pass


class CredencialesInvalidasError(Exception):
    pass


async def obtener_usuario_por_id(sesion: AsyncSession, usuario_id: int) -> Usuario | None:
    resultado = await sesion.execute(select(Usuario).where(Usuario.id == usuario_id))
    return resultado.scalar_one_or_none()


async def obtener_usuario_por_email(sesion: AsyncSession, email: str) -> Usuario | None:
    resultado = await sesion.execute(select(Usuario).where(Usuario.email == email))
    return resultado.scalar_one_or_none()


def _emitir_par_de_tokens(usuario_id: int) -> ParDeTokens:
    return ParDeTokens(
        access_token=crear_token_acceso(usuario_id),
        refresh_token=crear_token_refresco(usuario_id),
    )


async def registrar(
    sesion: AsyncSession, email: str, contrasena: str
) -> tuple[Usuario, ParDeTokens]:
    usuario = Usuario(email=email.lower().strip(), password_hash=hashear_contrasena(contrasena))
    sesion.add(usuario)
    try:
        await sesion.commit()
    except IntegrityError as exc:
        await sesion.rollback()
        raise EmailYaRegistradoError(email) from exc

    await sesion.refresh(usuario)
    return usuario, _emitir_par_de_tokens(usuario.id)


async def autenticar(
    sesion: AsyncSession, email: str, contrasena: str
) -> tuple[Usuario, ParDeTokens]:
    usuario = await obtener_usuario_por_email(sesion, email.lower().strip())
    if usuario is None or not verificar_contrasena(contrasena, usuario.password_hash):
        raise CredencialesInvalidasError

    return usuario, _emitir_par_de_tokens(usuario.id)


async def refrescar(sesion: AsyncSession, refresh_token: str) -> ParDeTokens:
    try:
        usuario_id = decodificar_token(refresh_token, TipoToken.REFRESCO)
    except TokenInvalidoError as exc:
        raise CredencialesInvalidasError from exc

    usuario = await obtener_usuario_por_id(sesion, usuario_id)
    if usuario is None:
        raise CredencialesInvalidasError

    return _emitir_par_de_tokens(usuario.id)


async def borrar_cuenta(sesion: AsyncSession, usuario_id: int) -> None:
    """Borra la cuenta y, en cascada, toda su colección (RF-M1 — obligatorio
    para la revisión de Apple si la app permite crear cuentas, ver Docs
    .../Movil-Arquitectura-y-Requisitos.md §7). Las fotos en el almacén las
    borra antes la ruta (``rutas/auth.py``), que es quien tiene acceso a él.
    """
    usuario = await obtener_usuario_por_id(sesion, usuario_id)
    if usuario is None:
        return
    await sesion.delete(usuario)
    await sesion.commit()
