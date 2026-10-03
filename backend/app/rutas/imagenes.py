"""Rutas de imágenes de una moneda: subir, descargar y borrar anverso/reverso/
detalle (RF-7, RF-8). Scopeadas por el usuario autenticado igual que el resto
de la colección: una moneda ajena responde 404, como si no existiera.

Las imágenes se sirven a través del backend (con el JWT) en vez de con URLs
públicas del bucket: así el aislamiento entre usuarios (RNF-M1) lo garantiza
la misma comprobación de propiedad que el resto de la API, y el bucket puede
ser privado.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from .. import coleccion, imagenes
from ..almacen import Cara, ObjetoNoEncontradoError, clave_imagen
from ..config import config
from ..dependencias import AlmacenDep, SesionDep, UsuarioActualDep, leer_subida
from ..esquemas import MonedaSalida
from ..modelos import Moneda

log = logging.getLogger(__name__)

router = APIRouter(prefix="/coleccion", tags=["imagenes"])


async def _moneda_propia(sesion: SesionDep, usuario_id: int, moneda_id: int) -> Moneda:
    moneda = await coleccion.obtener(sesion, usuario_id, moneda_id)
    if moneda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa moneda")
    return moneda


@router.put("/{moneda_id}/imagenes/{cara}", response_model=MonedaSalida)
async def subir(
    moneda_id: int,
    cara: Cara,
    archivo: UploadFile,
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    almacen: AlmacenDep,
) -> MonedaSalida:
    """Sube (o reemplaza) una foto. Se endereza, se reduce y se guarda como
    JPEG sin metadatos (ver ``imagenes.normalizar_a_jpeg``)."""
    await _moneda_propia(sesion, usuario_actual.id, moneda_id)
    datos = await leer_subida(archivo)
    try:
        jpeg = imagenes.normalizar_a_jpeg(datos, config.resize_almacenamiento)
    except imagenes.ImagenInvalidaError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El archivo no es una imagen válida"
        ) from exc

    clave = clave_imagen(usuario_actual.id, moneda_id, cara)
    await run_in_threadpool(almacen.guardar, clave, jpeg, imagenes.TIPO_CONTENIDO_JPEG)
    moneda = await coleccion.editar(sesion, usuario_actual.id, moneda_id, **{f"foto_{cara}": clave})
    return MonedaSalida.model_validate(moneda)


@router.get(
    "/{moneda_id}/imagenes/{cara}",
    response_class=Response,
    responses={200: {"content": {imagenes.TIPO_CONTENIDO_JPEG: {}}}},
)
async def descargar(
    moneda_id: int,
    cara: Cara,
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    almacen: AlmacenDep,
) -> Response:
    moneda = await _moneda_propia(sesion, usuario_actual.id, moneda_id)
    clave = getattr(moneda, f"foto_{cara}")
    if not clave:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa moneda no tiene esa foto")
    try:
        datos = await run_in_threadpool(almacen.leer, clave)
    except ObjetoNoEncontradoError as exc:
        log.error("Foto registrada en BD pero ausente del almacén: %s", clave)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa moneda no tiene esa foto") from exc
    return Response(
        datos,
        media_type=imagenes.TIPO_CONTENIDO_JPEG,
        # Datos personales: que ninguna caché compartida (proxy/CDN) los guarde.
        headers={"Cache-Control": "private, no-cache"},
    )


@router.delete("/{moneda_id}/imagenes/{cara}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(
    moneda_id: int,
    cara: Cara,
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    almacen: AlmacenDep,
) -> None:
    moneda = await _moneda_propia(sesion, usuario_actual.id, moneda_id)
    clave = getattr(moneda, f"foto_{cara}")
    if not clave:
        return
    await run_in_threadpool(almacen.borrar, clave)
    await coleccion.editar(sesion, usuario_actual.id, moneda_id, **{f"foto_{cara}": None})
