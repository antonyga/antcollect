"""Dependencias de FastAPI compartidas entre routers: sesión de BD y usuario
autenticado a partir del JWT de acceso.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth
from .db import obtener_sesion
from .modelos import Usuario
from .seguridad import TipoToken, TokenInvalidoError, decodificar_token

_esquema_bearer = HTTPBearer(auto_error=False)

SesionDep = Annotated[AsyncSession, Depends(obtener_sesion)]


async def usuario_actual(
    sesion: SesionDep,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
) -> Usuario:
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de acceso")

    try:
        usuario_id = decodificar_token(credenciales.credentials, TipoToken.ACCESO)
    except TokenInvalidoError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado") from exc

    usuario = await auth.obtener_usuario_por_id(sesion, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El usuario del token ya no existe")

    return usuario


UsuarioActualDep = Annotated[Usuario, Depends(usuario_actual)]
