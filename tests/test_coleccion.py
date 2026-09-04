"""Fase 1: alta, edición, borrado, búsqueda y duplicados (RF-6, RF-9, RF-11, RF-14)."""

from __future__ import annotations

import pytest

from antcollect import coleccion, config, db


@pytest.fixture(autouse=True)
def _bd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "imagenes")
    db.inicializar()


def _crear_2_euros_espana(**overrides):
    datos = {
        "pais": "España",
        "valor_texto": "2 euros",
        "anio": 2002,
        "ceca": None,
        "variante": None,
    }
    datos.update(overrides)
    return coleccion.crear(**datos)


def test_crear_y_obtener():
    creada = _crear_2_euros_espana(notas="primera moneda")

    assert creada.id is not None
    assert creada.pais_norm == "espana"
    assert creada.valor_norm == "2 euros"
    assert creada.fecha_agregada

    obtenida = coleccion.obtener(creada.id)
    assert obtenida == creada


def test_crear_duplicado_exacto_lanza_error():
    _crear_2_euros_espana()

    with pytest.raises(coleccion.TipoDuplicadoError):
        _crear_2_euros_espana()


def test_crear_duplicado_exacto_es_insensible_a_mayusculas_y_acentos():
    _crear_2_euros_espana(pais="España", valor_texto="2 Euros")

    with pytest.raises(coleccion.TipoDuplicadoError):
        _crear_2_euros_espana(pais="ESPAÑA", valor_texto="2 euros")


def test_crear_con_distinta_ceca_no_es_duplicado():
    _crear_2_euros_espana(ceca="M")

    otra = _crear_2_euros_espana(ceca="S")

    assert otra.id is not None
    assert len(coleccion.listar()) == 2


def test_crear_completamente_distinta_no_es_duplicado():
    _crear_2_euros_espana()

    otra = coleccion.crear(
        pais="Francia", valor_texto="1 euro", anio=2010, ceca=None, variante=None
    )

    assert otra.id is not None


def test_crear_con_anio_null_nunca_es_duplicado_exacto():
    _crear_2_euros_espana(anio=None)

    otra = _crear_2_euros_espana(anio=None)

    assert otra.id is not None
    assert len(coleccion.listar()) == 2


def test_existe_tipo_exacto_devuelve_none_si_no_hay_coincidencia():
    assert coleccion.existe_tipo_exacto("España", "2 euros", 2002, None, None) is None


def test_editar_actualiza_campos_y_normalizados():
    creada = _crear_2_euros_espana()

    editada = coleccion.editar(creada.id, ceca="M", notas="ahora con ceca")

    assert editada.ceca == "M"
    assert editada.ceca_norm == "m"
    assert editada.notas == "ahora con ceca"
    assert editada.pais == "España"


def test_editar_hacia_un_duplicado_existente_lanza_error():
    a = _crear_2_euros_espana(ceca="M")
    _crear_2_euros_espana(ceca="S")

    with pytest.raises(coleccion.TipoDuplicadoError):
        coleccion.editar(a.id, ceca="S")


def test_editar_puede_conservar_sus_propios_campos_sin_confundirse_con_duplicado():
    creada = _crear_2_euros_espana()

    editada = coleccion.editar(creada.id, notas="sin cambios de tipo")

    assert editada.id == creada.id


def test_editar_moneda_inexistente_lanza_error():
    with pytest.raises(ValueError):
        coleccion.editar(999, notas="x")


def test_borrar_elimina_la_moneda():
    creada = _crear_2_euros_espana()

    coleccion.borrar(creada.id)

    assert coleccion.obtener(creada.id) is None


def test_borrar_moneda_inexistente_no_falla():
    coleccion.borrar(999)


def test_listar_filtra_por_texto_pais_y_anio():
    _crear_2_euros_espana(ceca="M")
    coleccion.crear(pais="Francia", valor_texto="1 euro", anio=2010, ceca=None, variante=None)

    assert len(coleccion.listar()) == 2
    assert len(coleccion.listar(texto="francia")) == 1
    assert len(coleccion.listar(pais="España")) == 1
    assert len(coleccion.listar(valor="2 euros")) == 1
    assert len(coleccion.listar(anio=2010)) == 1
    assert len(coleccion.listar(pais="España", anio=1999)) == 0


def test_listar_busca_tambien_en_notas():
    _crear_2_euros_espana(notas="regalo de la abuela")

    assert len(coleccion.listar(texto="abuela")) == 1
    assert len(coleccion.listar(texto="inexistente")) == 0
