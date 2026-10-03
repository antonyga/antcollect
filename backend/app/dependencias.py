"""Dependencias de FastAPI compartidas entre routers: sesión de BD, usuario
autenticado a partir del JWT de acceso, almacén de imágenes y lector IA.
Las dos últimas se sustituyen en tests con ``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth
from .ai.base import CoinReader
from .ai.claude import ClaudeCoinReader
from .ai.deepseek import DeepSeekCoinReader
from .ai.gpt import OpenAICoinReader
from .ai.respaldo import CoinReaderConRespaldo
from .almacen import Almacen, obtener_almacen
from .config import config
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


AlmacenDep = Annotated[Almacen, Depends(obtener_almacen)]


def obtener_lector() -> CoinReader | None:
    """El lector IA configurado: Claude como principal y, si están sus claves,
    OpenAI y DeepSeek como respaldo inmediato (en ese orden). ``None`` si no
    hay ninguna clave (la lectura no está disponible y el cliente usa el modo
    manual)."""
    lectores: list[CoinReader] = []
    if config.anthropic_api_key:
        lectores.append(ClaudeCoinReader())
    if config.openai_api_key:
        lectores.append(OpenAICoinReader())
    if config.deepseek_api_key:
        lectores.append(DeepSeekCoinReader())
    if not lectores:
        return None
    return CoinReaderConRespaldo(lectores)


LectorDep = Annotated[CoinReader | None, Depends(obtener_lector)]


async def leer_subida(archivo: UploadFile) -> bytes:
    """Lee un fichero subido sin aceptar más de ``config.imagen_max_bytes``."""
    datos = await archivo.read(config.imagen_max_bytes + 1)
    if len(datos) > config.imagen_max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"La imagen supera el máximo de {config.imagen_max_bytes // (1024 * 1024)} MB",
        )
    if not datos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La imagen está vacía")
    return datos
