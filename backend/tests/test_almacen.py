"""Tests del almacén de imágenes: el mismo contrato contra la implementación
local y contra la S3 (con un S3 simulado por ``moto``, sin red ni bucket real).
"""

from __future__ import annotations

import boto3
import pytest
from app.almacen import (
    AlmacenLocal,
    AlmacenS3,
    ObjetoNoEncontradoError,
    clave_imagen,
    prefijo_usuario,
)
from moto import mock_aws


@pytest.fixture(params=["local", "s3"])
def almacen(request, tmp_path, monkeypatch):
    if request.param == "local":
        yield AlmacenLocal(tmp_path)
        return
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(var, "prueba")
    with mock_aws():
        cliente = boto3.client("s3", region_name="us-east-1")
        cliente.create_bucket(Bucket="antcollect-test")
        yield AlmacenS3("antcollect-test", cliente=cliente)


def test_guardar_y_leer(almacen):
    almacen.guardar("usuarios/1/monedas/0001_anverso.jpg", b"datos", "image/jpeg")
    assert almacen.leer("usuarios/1/monedas/0001_anverso.jpg") == b"datos"


def test_leer_inexistente_lanza_error_propio(almacen):
    with pytest.raises(ObjetoNoEncontradoError):
        almacen.leer("usuarios/1/monedas/no-existe.jpg")


def test_borrar_es_idempotente(almacen):
    almacen.guardar("usuarios/1/x.jpg", b"datos", "image/jpeg")
    almacen.borrar("usuarios/1/x.jpg")
    almacen.borrar("usuarios/1/x.jpg")
    with pytest.raises(ObjetoNoEncontradoError):
        almacen.leer("usuarios/1/x.jpg")


def test_borrar_prefijo_solo_borra_ese_usuario(almacen):
    """Usuario 1 vs. usuario 12: el "/" final del prefijo evita que borrar a
    uno arrastre al otro."""
    almacen.guardar(clave_imagen(1, 1, "anverso"), b"a", "image/jpeg")
    almacen.guardar(clave_imagen(1, 2, "reverso"), b"b", "image/jpeg")
    almacen.guardar(clave_imagen(12, 3, "anverso"), b"c", "image/jpeg")

    almacen.borrar_prefijo(prefijo_usuario(1))

    with pytest.raises(ObjetoNoEncontradoError):
        almacen.leer(clave_imagen(1, 1, "anverso"))
    with pytest.raises(ObjetoNoEncontradoError):
        almacen.leer(clave_imagen(1, 2, "reverso"))
    assert almacen.leer(clave_imagen(12, 3, "anverso")) == b"c"


def test_borrar_prefijo_sin_objetos_no_falla(almacen):
    almacen.borrar_prefijo(prefijo_usuario(99))


def test_clave_incluye_usuario_y_moneda():
    assert clave_imagen(7, 1, "detalle") == "usuarios/7/monedas/0001_detalle.jpg"


def test_almacen_local_no_permite_salir_de_la_raiz(tmp_path):
    almacen = AlmacenLocal(tmp_path / "raiz")
    with pytest.raises(ValueError):
        almacen.guardar("../fuera.jpg", b"x", "image/jpeg")
