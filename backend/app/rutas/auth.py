"""Rutas de autenticación y cuenta (RF-M1)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .. import auth
from ..dependencias import SesionDep, UsuarioActualDep
from ..esquemas import ParDeTokens, RefrescoEntrada, UsuarioLogin, UsuarioRegistro, UsuarioSalida

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


@router.delete("/cuenta", status_code=status.HTTP_204_NO_CONTENT)
async def borrar_cuenta(usuario_actual: UsuarioActualDep, sesion: SesionDep) -> None:
    """Borra la cuenta del usuario autenticado y toda su colección (RF-M1)."""
    await auth.borrar_cuenta(sesion, usuario_actual.id)
