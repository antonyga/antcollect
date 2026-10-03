from __future__ import annotations

import pytest_asyncio
from app import auth
from app.db import Base, obtener_sesion
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def sesion_fabrica():
    """Motor SQLite en memoria, aislado por test (StaticPool: una sola
    conexión compartida, si no cada conexión del pool vería una BD distinta).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield fabrica
    await engine.dispose()


@pytest_asyncio.fixture
async def sesion(sesion_fabrica):
    async with sesion_fabrica() as s:
        yield s


@pytest_asyncio.fixture
async def usuario_id(sesion) -> int:
    """Un usuario de prueba ya creado, para los tests de `coleccion.py` que
    necesitan un `usuario_id` válido (columna FK) pero no ejercitan auth."""
    usuario, _tokens = await auth.registrar(sesion, "test@example.com", "contrasena123")
    return usuario.id


@pytest_asyncio.fixture
async def cliente(sesion_fabrica):
    """Cliente HTTP contra la app real, con la sesión de BD sustituida por la
    de pruebas (misma técnica que `dependency_overrides` de FastAPI)."""

    async def _override():
        async with sesion_fabrica() as s:
            yield s

    app.dependency_overrides[obtener_sesion] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
