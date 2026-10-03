"""Rutas de lectura por IA (RF-1/RF-2) con cuota diaria por usuario (RF-M3).

Esta ruta solo *propone*: devuelve los campos leídos y nunca escribe en la
colección. Guardar (``POST /coleccion``) o consultar
(``POST /coleccion/comprobar``) es un paso posterior, que el cliente da solo
tras la confirmación humana del formulario (principio rector, RF-3).

Las fotos no se guardan: se leen y se descartan. Si el usuario acaba
guardando la moneda, la app las sube después a ``/coleccion/{id}/imagenes``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from .. import imagenes, lecturas
from ..ai.base import es_lectura_fallida
from ..config import config
from ..dependencias import LectorDep, SesionDep, UsuarioActualDep, leer_subida
from ..esquemas import CuotaSalida, LecturaSalida

router = APIRouter(prefix="/lecturas", tags=["lecturas IA"])

# La IA nombra el campo "valor" (contrato de CoinReader, igual que en la v1);
# la API lo llama "valor_texto" como el resto de esquemas de la colección.
_CAMPO_API = {"valor": "valor_texto"}


async def _preparar(archivo: UploadFile) -> bytes:
    datos = await leer_subida(archivo)
    try:
        return imagenes.normalizar_a_jpeg(datos, config.resize_lado_largo)
    except imagenes.ImagenInvalidaError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El archivo no es una imagen válida"
        ) from exc


@router.post("", response_model=LecturaSalida)
async def leer(
    anverso: UploadFile,
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    lector: LectorDep,
    reverso: UploadFile | None = None,
) -> LecturaSalida:
    """Propone los campos del tipo a partir de las fotos.

    - 503 si la lectura IA no está configurada en el servidor → modo manual.
    - 429 si el usuario agotó su cuota de hoy → modo manual.
    - 200 con ``fallida: true`` si la IA no pudo leer → modo manual (no gasta cuota).
    """
    if lector is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "La lectura automática no está disponible. Rellena los campos a mano.",
        )

    # Validar las imágenes antes de reservar cuota: una subida inválida no gasta.
    jpeg_anverso = await _preparar(anverso)
    jpeg_reverso = await _preparar(reverso) if reverso is not None else None

    try:
        reserva = await lecturas.reservar(
            sesion, usuario_actual.id, config.lecturas_ia_cuota_diaria
        )
    except lecturas.CuotaAgotadaError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Has usado tus {exc.limite} lecturas automáticas de hoy. "
            "Puedes seguir rellenando los campos a mano.",
        ) from exc

    lectura = await run_in_threadpool(lector.leer, jpeg_anverso, jpeg_reverso)
    fallida = es_lectura_fallida(lectura)
    if fallida:
        await lecturas.devolver(sesion, reserva)

    usadas = await lecturas.usadas_hoy(sesion, usuario_actual.id)
    return LecturaSalida(
        pais=lectura.pais,
        valor_texto=lectura.valor,
        anio=lectura.anio,
        ceca=lectura.ceca,
        variante=lectura.variante,
        campos_dudosos=[_CAMPO_API.get(c, c) for c in lectura.campos_dudosos],
        fallida=fallida,
        lecturas_restantes_hoy=max(config.lecturas_ia_cuota_diaria - usadas, 0),
    )


@router.get("/cuota", response_model=CuotaSalida)
async def cuota(usuario_actual: UsuarioActualDep, sesion: SesionDep) -> CuotaSalida:
    usadas = await lecturas.usadas_hoy(sesion, usuario_actual.id)
    limite = config.lecturas_ia_cuota_diaria
    return CuotaSalida(
        limite_diario=limite, usadas_hoy=usadas, restantes_hoy=max(limite - usadas, 0)
    )
