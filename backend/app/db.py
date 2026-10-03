"""Acceso a la base de datos: engine async, sesiones y Base declarativa.

Sustituye a src/antcollect/db.py (SQLite sin servidor) por SQLAlchemy async
sobre PostgreSQL en producción — ver el catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6. En tests se apunta a
SQLite en memoria vía aiosqlite (mismo esquema, sin servidor que levantar).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import config

engine = create_async_engine(config.database_url)
SesionAsync = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def obtener_sesion() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por request."""
    async with SesionAsync() as sesion:
        yield sesion


async def crear_tablas() -> None:
    """Crea el esquema si no existe. En producción, las migraciones de Alembic
    son la fuente de verdad (ver backend/alembic/); esto se usa en tests y en
    desarrollo local rápido.
    """
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
