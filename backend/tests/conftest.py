from __future__ import annotations

import io

import pytest
import pytest_asyncio
from app import auth
from app.ai.base import CAMPOS_TIPO, CoinReader, LecturaMoneda
from app.almacen import AlmacenLocal, obtener_almacen
from app.db import Base, obtener_sesion
from app.dependencias import obtener_lector
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


class LectorFalso(CoinReader):
    """Sustituye al lector real: nunca se llama a la API de Anthropic en tests."""

    def __init__(self) -> None:
        self.lectura = LecturaMoneda(
            pais="España", valor="2 euros", anio=2002, ceca=None, variante=None
        )
        self.llamadas: list[tuple[bytes, bytes | None]] = []

    def leer(self, imagen_anverso: bytes, imagen_reverso: bytes | None = None) -> LecturaMoneda:
        self.llamadas.append((imagen_anverso, imagen_reverso))
        return self.lectura

    def fallar(self) -> None:
        self.lectura = LecturaMoneda(
            pais=None,
            valor=None,
            anio=None,
            ceca=None,
            variante=None,
            campos_dudosos=list(CAMPOS_TIPO),
        )


def imagen_jpeg(ancho: int = 40, alto: int = 20, color: str = "blue") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (ancho, alto), color=color).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def almacen(tmp_path) -> AlmacenLocal:
    return AlmacenLocal(tmp_path / "almacen")


@pytest.fixture
def lector() -> LectorFalso:
    return LectorFalso()


@pytest_asyncio.fixture
async def cliente(sesion_fabrica, almacen, lector):
    """Cliente HTTP contra la app real, con la sesión de BD, el almacén y el
    lector IA sustituidos por los de pruebas (`dependency_overrides`)."""

    async def _override():
        async with sesion_fabrica() as s:
            yield s

    app.dependency_overrides[obtener_sesion] = _override
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    app.dependency_overrides[obtener_lector] = lambda: lector
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def registrar(cliente, email: str = "ana@example.com") -> dict:
    """Registra un usuario y devuelve la cabecera Authorization lista para usar."""
    r = await cliente.post("/auth/registro", json={"email": email, "contrasena": "contrasena123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def crear_moneda(cliente, cabecera: dict, **campos) -> dict:
    datos = {"pais": "España", "valor_texto": "2 euros", "anio": 2002} | campos
    r = await cliente.post("/coleccion", json=datos, headers=cabecera)
    assert r.status_code == 201, r.text
    return r.json()
