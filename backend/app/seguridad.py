"""Hash de contraseñas y JWT (RF-M1). La clave de firma vive en config
(variable de entorno, nunca hardcodeada — mismo principio que RNF-5 en la v1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

import bcrypt
import jwt

from .config import config


class TipoToken(StrEnum):
    ACCESO = "acceso"
    REFRESCO = "refresco"


class TokenInvalidoError(Exception):
    """El token no es válido, expiró, o no es del tipo esperado."""


def hashear_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))


def _crear_token(usuario_id: int, tipo: TipoToken, vigencia: timedelta) -> str:
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "tipo": tipo.value,
        "iat": ahora,
        "exp": ahora + vigencia,
    }
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algoritmo)


def crear_token_acceso(usuario_id: int) -> str:
    return _crear_token(usuario_id, TipoToken.ACCESO, timedelta(minutes=config.jwt_acceso_minutos))


def crear_token_refresco(usuario_id: int) -> str:
    return _crear_token(usuario_id, TipoToken.REFRESCO, timedelta(days=config.jwt_refresco_dias))


def decodificar_token(token: str, tipo_esperado: TipoToken) -> int:
    """Devuelve el ``usuario_id`` del token si es válido y del tipo esperado."""
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algoritmo])
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError(str(exc)) from exc

    if payload.get("tipo") != tipo_esperado.value:
        raise TokenInvalidoError(f"Se esperaba un token de tipo {tipo_esperado.value!r}")

    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidoError("Token sin 'sub' válido") from exc
