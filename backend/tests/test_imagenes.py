"""Tests de imágenes (RF-7/RF-8): subida, descarga, borrado, normalización
(EXIF, tamaño, metadatos) y, sobre todo, aislamiento entre usuarios (RNF-M1)
y limpieza del almacén al borrar una moneda o una cuenta.
"""

from __future__ import annotations

import io

from app import imagenes
from PIL import Image

from .conftest import crear_moneda, imagen_jpeg, registrar


def _subida(datos: bytes, nombre: str = "foto.jpg", tipo: str = "image/jpeg") -> dict:
    return {"archivo": (nombre, datos, tipo)}


async def test_subir_y_descargar_foto(cliente, almacen):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)

    r = await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/anverso", files=_subida(imagen_jpeg()), headers=cab
    )
    assert r.status_code == 200, r.text
    assert r.json()["foto_anverso"] == f"/coleccion/{moneda['id']}/imagenes/anverso"
    assert r.json()["foto_reverso"] is None

    r = await cliente.get(r.json()["foto_anverso"], headers=cab)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert "private" in r.headers["cache-control"]
    assert Image.open(io.BytesIO(r.content)).format == "JPEG"


async def test_la_ficha_expone_url_y_no_la_clave_interna(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)
    await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/reverso", files=_subida(imagen_jpeg()), headers=cab
    )

    ficha = (await cliente.get(f"/coleccion/{moneda['id']}", headers=cab)).json()
    assert ficha["foto_reverso"] == f"/coleccion/{moneda['id']}/imagenes/reverso"
    assert "usuarios/" not in str(ficha)


async def test_subir_reemplaza_la_foto_anterior(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)
    url = f"/coleccion/{moneda['id']}/imagenes/anverso"

    await cliente.put(url, files=_subida(imagen_jpeg(color="red")), headers=cab)
    await cliente.put(url, files=_subida(imagen_jpeg(color="green")), headers=cab)

    r = await cliente.get(url, headers=cab)
    r_, g, b = Image.open(io.BytesIO(r.content)).getpixel((5, 5))
    assert g > r_ and g > b


async def test_foto_inexistente_devuelve_404(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)

    r = await cliente.get(f"/coleccion/{moneda['id']}/imagenes/detalle", headers=cab)
    assert r.status_code == 404


async def test_cara_desconocida_se_rechaza(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)

    r = await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/canto", files=_subida(imagen_jpeg()), headers=cab
    )
    assert r.status_code == 422


async def test_archivo_que_no_es_imagen_devuelve_400(cliente):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)

    r = await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/anverso",
        files=_subida(b"esto no es una imagen", "x.jpg"),
        headers=cab,
    )
    assert r.status_code == 400
    ficha = (await cliente.get(f"/coleccion/{moneda['id']}", headers=cab)).json()
    assert ficha["foto_anverso"] is None


async def test_imagen_demasiado_grande_devuelve_413(cliente, monkeypatch):
    monkeypatch.setattr("app.dependencias.config.imagen_max_bytes", 100)
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)

    r = await cliente.put(
        f"/coleccion/{moneda['id']}/imagenes/anverso",
        files=_subida(imagen_jpeg(400, 400)),
        headers=cab,
    )
    assert r.status_code == 413


async def test_borrar_foto(cliente, almacen):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)
    url = f"/coleccion/{moneda['id']}/imagenes/anverso"
    await cliente.put(url, files=_subida(imagen_jpeg()), headers=cab)

    r = await cliente.delete(url, headers=cab)
    assert r.status_code == 204
    assert (await cliente.get(url, headers=cab)).status_code == 404
    assert not list((almacen._raiz).rglob("*.jpg"))


# --- Aislamiento entre usuarios (RNF-M1) ---


async def test_no_se_puede_ver_la_foto_de_otro_usuario(cliente):
    ana = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")
    moneda = await crear_moneda(cliente, ana)
    url = f"/coleccion/{moneda['id']}/imagenes/anverso"
    await cliente.put(url, files=_subida(imagen_jpeg()), headers=ana)

    r = await cliente.get(url, headers=luis)
    assert r.status_code == 404


async def test_no_se_puede_subir_ni_borrar_la_foto_de_otro_usuario(cliente):
    ana = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")
    moneda = await crear_moneda(cliente, ana)
    url = f"/coleccion/{moneda['id']}/imagenes/anverso"
    await cliente.put(url, files=_subida(imagen_jpeg(color="red")), headers=ana)

    r = await cliente.put(url, files=_subida(imagen_jpeg(color="green")), headers=luis)
    assert r.status_code == 404
    r = await cliente.delete(url, headers=luis)
    assert r.status_code == 404

    r = await cliente.get(url, headers=ana)
    assert r.status_code == 200
    rojo, verde, _ = Image.open(io.BytesIO(r.content)).getpixel((5, 5))
    assert rojo > verde


async def test_fotos_sin_token_devuelven_401(cliente):
    ana = await registrar(cliente)
    moneda = await crear_moneda(cliente, ana)

    r = await cliente.get(f"/coleccion/{moneda['id']}/imagenes/anverso")
    assert r.status_code == 401


# --- Limpieza del almacén ---


async def test_borrar_moneda_borra_sus_fotos(cliente, almacen):
    cab = await registrar(cliente)
    moneda = await crear_moneda(cliente, cab)
    for cara in ("anverso", "reverso", "detalle"):
        await cliente.put(
            f"/coleccion/{moneda['id']}/imagenes/{cara}",
            files=_subida(imagen_jpeg()),
            headers=cab,
        )
    assert len(list(almacen._raiz.rglob("*.jpg"))) == 3

    r = await cliente.delete(f"/coleccion/{moneda['id']}", headers=cab)
    assert r.status_code == 204
    assert not list(almacen._raiz.rglob("*.jpg"))


async def test_borrar_cuenta_borra_todas_sus_fotos_y_no_las_de_otros(cliente, almacen):
    ana = await registrar(cliente, "ana@example.com")
    luis = await registrar(cliente, "luis@example.com")
    for cab in (ana, luis):
        moneda = await crear_moneda(cliente, cab)
        await cliente.put(
            f"/coleccion/{moneda['id']}/imagenes/anverso",
            files=_subida(imagen_jpeg()),
            headers=cab,
        )
    assert len(list(almacen._raiz.rglob("*.jpg"))) == 2

    r = await cliente.delete("/auth/cuenta", headers=ana)
    assert r.status_code == 204

    restantes = list(almacen._raiz.rglob("*.jpg"))
    assert len(restantes) == 1
    moneda_luis = (await cliente.get("/coleccion", headers=luis)).json()[0]
    r = await cliente.get(moneda_luis["foto_anverso"], headers=luis)
    assert r.status_code == 200


# --- Normalización (unitarios de imagenes.py) ---


def test_normalizar_reduce_al_lado_largo_maximo():
    jpeg = imagenes.normalizar_a_jpeg(imagen_jpeg(3000, 1500), 2000)
    assert Image.open(io.BytesIO(jpeg)).size == (2000, 1000)


def test_normalizar_no_amplia():
    jpeg = imagenes.normalizar_a_jpeg(imagen_jpeg(300, 200), 2000)
    assert Image.open(io.BytesIO(jpeg)).size == (300, 200)


def test_normalizar_aplica_orientacion_exif_y_quita_metadatos():
    original = Image.new("RGB", (60, 30), color="blue")
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotar 90° — típico de una foto vertical de móvil
    buffer = io.BytesIO()
    original.save(buffer, "JPEG", exif=exif)

    resultado = Image.open(io.BytesIO(imagenes.normalizar_a_jpeg(buffer.getvalue(), 2000)))

    assert resultado.size == (30, 60)
    assert not resultado.getexif()


def test_normalizar_convierte_png_con_transparencia_a_jpeg():
    buffer = io.BytesIO()
    Image.new("RGBA", (20, 20), (255, 0, 0, 128)).save(buffer, "PNG")

    jpeg = imagenes.normalizar_a_jpeg(buffer.getvalue(), 2000)
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG"
