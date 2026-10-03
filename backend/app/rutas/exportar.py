"""Ruta de exportación de la colección del usuario autenticado (RF-13)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .. import coleccion, exportar
from ..dependencias import SesionDep, UsuarioActualDep

router = APIRouter(prefix="/exportar", tags=["exportar"])

_TIPOS = {"csv": "text/csv; charset=utf-8", "json": "application/json"}


@router.get(
    "",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}, "application/json": {}}}},
)
async def exportar_coleccion(
    usuario_actual: UsuarioActualDep,
    sesion: SesionDep,
    formato: Literal["csv", "json"] = "csv",
) -> StreamingResponse:
    """Descarga toda la colección del usuario como CSV o JSON.

    Las monedas se cargan antes de empezar a responder (una colección personal
    cabe de sobra en memoria) para no depender de que la sesión de BD siga
    abierta mientras se envía el cuerpo; lo que va en streaming es la
    serialización.
    """
    monedas = await coleccion.listar(sesion, usuario_actual.id)
    generador = (
        exportar.generar_csv(monedas) if formato == "csv" else exportar.generar_json(monedas)
    )
    return StreamingResponse(
        generador,
        media_type=_TIPOS[formato],
        headers={
            "Content-Disposition": f'attachment; filename="{exportar.nombre_archivo(formato)}"'
        },
    )
