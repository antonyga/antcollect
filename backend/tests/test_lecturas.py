"""Tests de lectura por IA (RF-1/RF-2) y su cuota diaria (RF-M3, RNF-M2).

Nunca llaman a la API de Anthropic: ``conftest.LectorFalso`` sustituye al
lector real vía ``dependency_overrides``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import lecturas
from app.dependencias import obtener_lector
from app.main import app

from .conftest import imagen_jpeg, registrar


def _fotos(reverso: bool = True) -> dict:
    archivos = {"anverso": ("a.jpg", imagen_jpeg(), "image/jpeg")}
    if reverso:
        archivos["reverso"] = ("r.jpg", imagen_jpeg(), "image/jpeg")
    return archivos


async def test_lectura_devuelve_campos_propuestos(cliente, lector):
    cab = await registrar(cliente)

    r = await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["pais"] == "España"
    assert datos["valor_texto"] == "2 euros"
    assert datos["anio"] == 2002
    assert datos["fallida"] is False
    assert datos["lecturas_restantes_hoy"] == 19
    anverso, reverso = lector.llamadas[0]
    assert anverso and reverso


async def test_lectura_solo_con_anverso(cliente, lector):
    cab = await registrar(cliente)

    r = await cliente.post("/lecturas", files=_fotos(reverso=False), headers=cab)

    assert r.status_code == 200
    assert lector.llamadas[0][1] is None


async def test_lectura_no_escribe_en_la_coleccion(cliente):
    """Principio rector: la IA solo propone. Leer no crea ninguna moneda."""
    cab = await registrar(cliente)

    await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert (await cliente.get("/coleccion", headers=cab)).json() == []


async def test_campos_dudosos_usan_los_nombres_de_la_api(cliente, lector):
    lector.lectura.campos_dudosos = ["valor", "anio"]
    cab = await registrar(cliente)

    r = await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert r.json()["campos_dudosos"] == ["valor_texto", "anio"]


async def test_lectura_fallida_no_gasta_cuota(cliente, lector):
    lector.fallar()
    cab = await registrar(cliente)

    r = await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert r.status_code == 200
    assert r.json()["fallida"] is True
    assert r.json()["lecturas_restantes_hoy"] == 20
    cuota = (await cliente.get("/lecturas/cuota", headers=cab)).json()
    assert cuota == {"limite_diario": 20, "usadas_hoy": 0, "restantes_hoy": 20}


async def test_imagen_invalida_devuelve_400_y_no_gasta_cuota(cliente, lector):
    cab = await registrar(cliente)

    r = await cliente.post(
        "/lecturas", files={"anverso": ("a.jpg", b"basura", "image/jpeg")}, headers=cab
    )

    assert r.status_code == 400
    assert lector.llamadas == []
    assert (await cliente.get("/lecturas/cuota", headers=cab)).json()["usadas_hoy"] == 0


async def test_sin_clave_de_ia_devuelve_503(cliente):
    app.dependency_overrides[obtener_lector] = lambda: None
    cab = await registrar(cliente)

    r = await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert r.status_code == 503
    assert "a mano" in r.json()["detail"]


async def test_lectura_sin_token_devuelve_401(cliente, lector):
    r = await cliente.post("/lecturas", files=_fotos())
    assert r.status_code == 401
    assert lector.llamadas == []


# --- Cuota diaria ---


async def test_cuota_agotada_devuelve_429_sin_llamar_a_la_ia(cliente, lector, monkeypatch):
    monkeypatch.setattr("app.rutas.lecturas.config.lecturas_ia_cuota_diaria", 2)
    cab = await registrar(cliente)

    for _ in range(2):
        assert (await cliente.post("/lecturas", files=_fotos(), headers=cab)).status_code == 200
    r = await cliente.post("/lecturas", files=_fotos(), headers=cab)

    assert r.status_code == 429
    assert "a mano" in r.json()["detail"]
    assert len(lector.llamadas) == 2
    cuota = (await cliente.get("/lecturas/cuota", headers=cab)).json()
    assert cuota == {"limite_diario": 2, "usadas_hoy": 2, "restantes_hoy": 0}


async def test_la_cuota_es_por_usuario(cliente, monkeypatch):
    monkeypatch.setattr("app.rutas.lecturas.config.lecturas_ia_cuota_diaria", 1)
    ana = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")

    assert (await cliente.post("/lecturas", files=_fotos(), headers=ana)).status_code == 200
    assert (await cliente.post("/lecturas", files=_fotos(), headers=ana)).status_code == 429
    assert (await cliente.post("/lecturas", files=_fotos(), headers=luis)).status_code == 200


async def test_la_cuota_se_renueva_cada_dia(cliente, monkeypatch):
    monkeypatch.setattr("app.rutas.lecturas.config.lecturas_ia_cuota_diaria", 1)
    hoy = datetime(2026, 10, 3, 23, 50, tzinfo=UTC)
    monkeypatch.setattr(lecturas, "ahora", lambda: hoy)
    cab = await registrar(cliente)

    assert (await cliente.post("/lecturas", files=_fotos(), headers=cab)).status_code == 200
    assert (await cliente.post("/lecturas", files=_fotos(), headers=cab)).status_code == 429

    monkeypatch.setattr(lecturas, "ahora", lambda: hoy + timedelta(minutes=15))
    assert (await cliente.post("/lecturas", files=_fotos(), headers=cab)).status_code == 200


async def test_borrar_cuenta_borra_su_historial_de_lecturas(cliente, sesion):
    cab = await registrar(cliente)
    await cliente.post("/lecturas", files=_fotos(), headers=cab)

    await cliente.delete("/auth/cuenta", headers=cab)

    from app.modelos import LecturaIA
    from sqlalchemy import func, select

    total = (await sesion.execute(select(func.count(LecturaIA.id)))).scalar_one()
    assert total == 0
