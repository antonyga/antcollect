"""Rutas de autenticación y cuenta (RF-M1)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..almacen import Almacen, prefijo_usuario
from ..dependencias import AlmacenDep, SesionDep, UsuarioActualDep
from ..esquemas import (
    BorrarCuentaEntrada,
    ParDeTokens,
    RefrescoEntrada,
    UsuarioLogin,
    UsuarioRegistro,
    UsuarioSalida,
)
from ..seguridad import verificar_contrasena

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=ParDeTokens, status_code=status.HTTP_201_CREATED)
async def registro(datos: UsuarioRegistro, sesion: SesionDep) -> ParDeTokens:
    try:
        _usuario, tokens = await auth.registrar(sesion, datos.email, datos.contrasena)
    except auth.EmailYaRegistradoError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese email ya está registrado") from exc
    return tokens


@router.post("/login", response_model=ParDeTokens)
async def login(datos: UsuarioLogin, sesion: SesionDep) -> ParDeTokens:
    try:
        _usuario, tokens = await auth.autenticar(sesion, datos.email, datos.contrasena)
    except auth.CredencialesInvalidasError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos") from exc
    return tokens


@router.post("/refresco", response_model=ParDeTokens)
async def refresco(datos: RefrescoEntrada, sesion: SesionDep) -> ParDeTokens:
    try:
        return await auth.refrescar(sesion, datos.refresh_token)
    except auth.CredencialesInvalidasError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token de refresco inválido o expirado"
        ) from exc


@router.get("/yo", response_model=UsuarioSalida)
async def yo(usuario_actual: UsuarioActualDep) -> UsuarioSalida:
    return UsuarioSalida.model_validate(usuario_actual)


@router.post("/cuenta/borrar", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_cuenta(
    datos: BorrarCuentaEntrada,
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    almacen: AlmacenDep,
) -> None:
    """Borra la cuenta del usuario autenticado, toda su colección y todas sus
    fotos (RF-M1). Pide la contraseña: un token robado o un móvil
    desbloqueado en manos ajenas no basta para borrar una colección entera.
    Responde 403 (no 401) si no coincide, para que el cliente no lo confunda
    con una sesión caducada.

    Las fotos primero, por el mismo motivo que al borrar una moneda: si el
    almacén falla, la cuenta sigue existiendo y se puede reintentar, en vez
    de quedar fotos personales huérfanas en el bucket."""
    if not verificar_contrasena(datos.contrasena, usuario_actual.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Contraseña incorrecta")
    await borrar_cuenta_y_fotos(sesion, almacen, usuario_actual.id)


async def borrar_cuenta_y_fotos(sesion: AsyncSession, almacen: Almacen, usuario_id: int) -> None:
    """Fotos primero, luego la cuenta (y en cascada la colección). Compartido
    con la página web de borrado (`rutas/legal.py`)."""
    await run_in_threadpool(almacen.borrar_prefijo, prefijo_usuario(usuario_id))
    await auth.borrar_cuenta(sesion, usuario_id)
