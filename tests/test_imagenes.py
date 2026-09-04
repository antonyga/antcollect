"""Fase 1: guardado y borrado de imágenes de monedas."""

from __future__ import annotations

from PIL import Image

from antcollect import config, imagenes
from antcollect.modelo import Moneda


def _moneda(id_, foto_anverso=None, foto_reverso=None) -> Moneda:
    return Moneda(
        id=id_,
        pais="España",
        valor_texto="2 euros",
        anio=2002,
        ceca=None,
        variante=None,
        notas=None,
        estado="en_coleccion",
        foto_anverso=foto_anverso,
        foto_reverso=foto_reverso,
        fecha_agregada="2026-01-01T00:00:00",
        pais_norm="espana",
        valor_norm="2 euros",
        ceca_norm="",
        variante_norm="",
    )


def test_guardar_imagen_crea_fichero_con_nombre_derivado_del_id(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    imagen = Image.new("RGB", (100, 50), color="red")

    nombre = imagenes.guardar_imagen(imagen, 7, "anverso")

    assert nombre == "0007_anverso.jpg"
    assert imagenes.ruta_completa(nombre).exists()


def test_redimensionar_reduce_lado_largo_pero_no_amplia():
    grande = Image.new("RGB", (2000, 1000))
    reducida = imagenes.redimensionar(grande, 1000)
    assert max(reducida.size) == 1000

    pequena = Image.new("RGB", (100, 50))
    igual = imagenes.redimensionar(pequena, 1000)
    assert igual.size == (100, 50)


def test_borrar_imagenes_elimina_ficheros_existentes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    imagen = Image.new("RGB", (10, 10))
    nombre_anverso = imagenes.guardar_imagen(imagen, 1, "anverso")
    nombre_reverso = imagenes.guardar_imagen(imagen, 1, "reverso")
    moneda = _moneda(1, nombre_anverso, nombre_reverso)

    imagenes.borrar_imagenes(moneda)

    assert not imagenes.ruta_completa(nombre_anverso).exists()
    assert not imagenes.ruta_completa(nombre_reverso).exists()


def test_borrar_imagenes_sin_fotos_no_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    imagenes.borrar_imagenes(_moneda(1))
