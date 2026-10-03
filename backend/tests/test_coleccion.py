"""Migrado de tests/test_coleccion.py (v1): misma lógica de dominio
(normalización, duplicados, "¿la tengo?"), ahora async y scopeada por
usuario_id. Ver catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6.
"""

from __future__ import annotations

import pytest
from app import coleccion, modelos


async def _crear_2_euros_espana(sesion, usuario_id, **overrides):
    datos = {
        "pais": "España",
        "valor_texto": "2 euros",
        "anio": 2002,
        "ceca": None,
        "variante": None,
    }
    datos.update(overrides)
    return await coleccion.crear(sesion, usuario_id, **datos)


async def test_crear_y_obtener(sesion, usuario_id):
    creada = await _crear_2_euros_espana(sesion, usuario_id, notas="primera moneda")

    assert creada.id is not None
    assert creada.pais_norm == "espana"
    assert creada.valor_norm == "2 euros"
    assert creada.fecha_agregada

    obtenida = await coleccion.obtener(sesion, usuario_id, creada.id)
    assert obtenida.id == creada.id


async def test_crear_duplicado_exacto_lanza_error(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id)

    with pytest.raises(coleccion.TipoDuplicadoError):
        await _crear_2_euros_espana(sesion, usuario_id)


async def test_crear_duplicado_exacto_es_insensible_a_mayusculas_y_acentos(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, pais="España", valor_texto="2 Euros")

    with pytest.raises(coleccion.TipoDuplicadoError):
        await _crear_2_euros_espana(sesion, usuario_id, pais="ESPAÑA", valor_texto="2 euros")


async def test_crear_con_distinta_ceca_no_es_duplicado(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, ceca="M")

    otra = await _crear_2_euros_espana(sesion, usuario_id, ceca="S")

    assert otra.id is not None
    assert len(await coleccion.listar(sesion, usuario_id)) == 2


async def test_crear_con_anio_null_nunca_es_duplicado_exacto(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, anio=None)

    otra = await _crear_2_euros_espana(sesion, usuario_id, anio=None)

    assert otra.id is not None
    assert len(await coleccion.listar(sesion, usuario_id)) == 2


async def test_editar_actualiza_campos_y_normalizados(sesion, usuario_id):
    creada = await _crear_2_euros_espana(sesion, usuario_id)

    editada = await coleccion.editar(
        sesion, usuario_id, creada.id, ceca="M", notas="ahora con ceca"
    )

    assert editada.ceca == "M"
    assert editada.ceca_norm == "m"
    assert editada.notas == "ahora con ceca"
    assert editada.pais == "España"


async def test_editar_hacia_un_duplicado_existente_lanza_error(sesion, usuario_id):
    a = await _crear_2_euros_espana(sesion, usuario_id, ceca="M")
    await _crear_2_euros_espana(sesion, usuario_id, ceca="S")

    with pytest.raises(coleccion.TipoDuplicadoError):
        await coleccion.editar(sesion, usuario_id, a.id, ceca="S")


async def test_editar_moneda_inexistente_lanza_error(sesion, usuario_id):
    with pytest.raises(ValueError):
        await coleccion.editar(sesion, usuario_id, 999, notas="x")


async def test_borrar_elimina_la_moneda(sesion, usuario_id):
    creada = await _crear_2_euros_espana(sesion, usuario_id)

    await coleccion.borrar(sesion, usuario_id, creada.id)

    assert await coleccion.obtener(sesion, usuario_id, creada.id) is None


async def test_borrar_moneda_inexistente_no_falla(sesion, usuario_id):
    await coleccion.borrar(sesion, usuario_id, 999)


async def test_listar_filtra_por_texto_pais_y_anio(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, ceca="M")
    await coleccion.crear(
        sesion,
        usuario_id,
        pais="Francia",
        valor_texto="1 euro",
        anio=2010,
        ceca=None,
        variante=None,
    )

    assert len(await coleccion.listar(sesion, usuario_id)) == 2
    assert len(await coleccion.listar(sesion, usuario_id, texto="francia")) == 1
    assert len(await coleccion.listar(sesion, usuario_id, pais="España")) == 1
    assert len(await coleccion.listar(sesion, usuario_id, valor="2 euros")) == 1
    assert len(await coleccion.listar(sesion, usuario_id, anio=2010)) == 1
    assert len(await coleccion.listar(sesion, usuario_id, pais="España", anio=1999)) == 0


async def test_listar_filtra_por_estado(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, ceca="M", estado=modelos.EN_COLECCION)
    await _crear_2_euros_espana(sesion, usuario_id, ceca="S", estado=modelos.DUPLICADA)

    assert len(await coleccion.listar(sesion, usuario_id)) == 2
    assert len(await coleccion.listar(sesion, usuario_id, estado=modelos.EN_COLECCION)) == 1
    assert len(await coleccion.listar(sesion, usuario_id, estado=modelos.DUPLICADA)) == 1
    assert len(await coleccion.listar(sesion, usuario_id, estado=modelos.PARA_INTERCAMBIO)) == 0


async def test_comprobar_tipo_exacta(sesion, usuario_id):
    guardada = await _crear_2_euros_espana(sesion, usuario_id)

    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion,
        usuario_id,
        pais="ESPAÑA",
        valor_texto="2 Euros",
        anio=2002,
        ceca=None,
        variante=None,
    )

    assert categoria == "exacta"
    assert exacta.id == guardada.id
    assert posibles == []


async def test_comprobar_tipo_con_campo_dudoso_nunca_da_exacta(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id)

    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion,
        usuario_id,
        pais="España",
        valor_texto="2 euros",
        anio=2002,
        ceca=None,
        variante=None,
        campos_dudosos=["ceca"],
    )

    assert categoria == "parcial"
    assert exacta is None
    assert len(posibles) == 1


async def test_comprobar_tipo_distinta_ceca_es_parcial(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id, ceca="M")

    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion, usuario_id, pais="España", valor_texto="2 euros", anio=2002, ceca="S", variante=None
    )

    assert categoria == "parcial"
    assert exacta is None
    assert len(posibles) == 1
    assert posibles[0].ceca == "M"


async def test_comprobar_tipo_anio_null_en_consulta_es_parcial_no_falso_positivo(
    sesion, usuario_id
):
    await _crear_2_euros_espana(sesion, usuario_id)

    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion,
        usuario_id,
        pais="España",
        valor_texto="2 euros",
        anio=None,
        ceca=None,
        variante=None,
    )

    assert categoria == "parcial"
    assert exacta is None
    assert len(posibles) == 1


async def test_comprobar_tipo_sin_coincidencia(sesion, usuario_id):
    await _crear_2_euros_espana(sesion, usuario_id)

    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion,
        usuario_id,
        pais="Francia",
        valor_texto="1 euro",
        anio=2010,
        ceca=None,
        variante=None,
    )

    assert categoria == "ninguna"
    assert exacta is None
    assert posibles == []
