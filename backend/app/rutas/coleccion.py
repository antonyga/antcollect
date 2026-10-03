"""Rutas de la colección: alta, edición, borrado, búsqueda y "¿la tengo?"
(RF-2, RF-6, RF-9, RF-10, RF-11, RF-14). Scopeadas por el usuario autenticado
— ningún endpoint acepta ni expone un `usuario_id` del cliente.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from .. import coleccion
from ..dependencias import AlmacenDep, SesionDep, UsuarioActualDep
from ..esquemas import (
    ComprobarTipoEntrada,
    ComprobarTipoSalida,
    MonedaEdicion,
    MonedaEntrada,
    MonedaSalida,
)

router = APIRouter(prefix="/coleccion", tags=["coleccion"])


def _conflicto_duplicado(exc: coleccion.TipoDuplicadoError) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "mensaje": "Ya existe un tipo igual en tu colección",
            "existente_id": exc.existente.id,
        },
    )


@router.get("", response_model=list[MonedaSalida])
async def listar(
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    texto: str | None = None,
    pais: str | None = None,
    valor: str | None = None,
    anio: int | None = None,
    estado: str | None = None,
) -> list[MonedaSalida]:
    monedas = await coleccion.listar(
        sesion, usuario_actual.id, texto=texto, pais=pais, valor=valor, anio=anio, estado=estado
    )
    return [MonedaSalida.model_validate(m) for m in monedas]


@router.post("", response_model=MonedaSalida, status_code=status.HTTP_201_CREATED)
async def crear(
    datos: MonedaEntrada, usuario_actual: UsuarioActualDep, sesion: SesionDep
) -> MonedaSalida:
    try:
        moneda = await coleccion.crear(sesion, usuario_actual.id, **datos.model_dump())
    except coleccion.TipoDuplicadoError as exc:
        raise _conflicto_duplicado(exc) from exc
    return MonedaSalida.model_validate(moneda)


@router.get("/{moneda_id}", response_model=MonedaSalida)
async def obtener(
    moneda_id: int, usuario_actual: UsuarioActualDep, sesion: SesionDep
) -> MonedaSalida:
    moneda = await coleccion.obtener(sesion, usuario_actual.id, moneda_id)
    if moneda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa moneda")
    return MonedaSalida.model_validate(moneda)


@router.patch("/{moneda_id}", response_model=MonedaSalida)
async def editar(
    moneda_id: int, datos: MonedaEdicion, usuario_actual: UsuarioActualDep, sesion: SesionDep
) -> MonedaSalida:
    actual = await coleccion.obtener(sesion, usuario_actual.id, moneda_id)
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa moneda")

    cambios = datos.model_dump(exclude_unset=True)
    try:
        moneda = await coleccion.editar(sesion, usuario_actual.id, moneda_id, **cambios)
    except coleccion.TipoDuplicadoError as exc:
        raise _conflicto_duplicado(exc) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return MonedaSalida.model_validate(moneda)


@router.delete("/{moneda_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(
    moneda_id: int, usuario_actual: UsuarioActualDep, sesion: SesionDep, almacen: AlmacenDep
) -> None:
    """Borra la moneda y sus fotos (RF-11). Primero las fotos: si el almacén
    falla, la moneda sigue intacta y el cliente puede reintentar; al revés
    quedarían fotos huérfanas sin forma de borrarlas desde la app."""
    moneda = await coleccion.obtener(sesion, usuario_actual.id, moneda_id)
    if moneda is None:
        return
    for clave in (moneda.foto_anverso, moneda.foto_reverso, moneda.foto_detalle):
        if clave:
            await run_in_threadpool(almacen.borrar, clave)
    await coleccion.borrar(sesion, usuario_actual.id, moneda_id)


@router.post("/comprobar", response_model=ComprobarTipoSalida)
async def comprobar(
    datos: ComprobarTipoEntrada, usuario_actual: UsuarioActualDep, sesion: SesionDep
) -> ComprobarTipoSalida:
    """ "¿La tengo?" (RF-2): consulta exacta sobre los campos ya confirmados."""
    categoria, exacta, posibles = await coleccion.comprobar_tipo(
        sesion,
        usuario_actual.id,
        pais=datos.pais,
        valor_texto=datos.valor_texto,
        anio=datos.anio,
        ceca=datos.ceca,
        variante=datos.variante,
        campos_dudosos=datos.campos_dudosos,
    )
    return ComprobarTipoSalida(
        categoria=categoria,
        exacta=MonedaSalida.model_validate(exacta) if exacta else None,
        posibles=[MonedaSalida.model_validate(m) for m in posibles],
    )
