"""Esquemas Pydantic de entrada/salida de la API (distintos de los modelos ORM
de modelos.py). Separar ORM de esquemas de API es intencional: evita exponer
columnas internas (p. ej. password_hash) y deja que la forma de la API
evolucione sin acoplarse 1:1 al esquema de la base de datos.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioRegistro(BaseModel):
    email: EmailStr
    contrasena: str = Field(min_length=8, max_length=72)


class UsuarioLogin(BaseModel):
    email: EmailStr
    contrasena: str


class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    creado_en: datetime


class ParDeTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefrescoEntrada(BaseModel):
    refresh_token: str


class MonedaEntrada(BaseModel):
    """Campos que el usuario confirma antes de guardar (principio rector:
    la IA solo propone, ver CLAUDE.md §2 / Docs .../Movil... §1)."""

    pais: str = Field(min_length=1, max_length=200)
    valor_texto: str = Field(min_length=1, max_length=200)
    anio: int | None = None
    ceca: str | None = None
    variante: str | None = None
    notas: str | None = None
    estado: str = "en_coleccion"


class MonedaEdicion(BaseModel):
    """Igual que MonedaEntrada pero con todos los campos opcionales (PATCH)."""

    pais: str | None = Field(default=None, min_length=1, max_length=200)
    valor_texto: str | None = Field(default=None, min_length=1, max_length=200)
    anio: int | None = None
    ceca: str | None = None
    variante: str | None = None
    notas: str | None = None
    estado: str | None = None


class MonedaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pais: str
    valor_texto: str
    anio: int | None
    ceca: str | None
    variante: str | None
    notas: str | None
    estado: str
    foto_anverso: str | None
    foto_reverso: str | None
    foto_detalle: str | None
    fecha_agregada: datetime


class ComprobarTipoEntrada(BaseModel):
    pais: str | None = None
    valor_texto: str | None = None
    anio: int | None = None
    ceca: str | None = None
    variante: str | None = None
    campos_dudosos: list[str] = Field(default_factory=list)


class ComprobarTipoSalida(BaseModel):
    categoria: str
    exacta: MonedaSalida | None
    posibles: list[MonedaSalida]
