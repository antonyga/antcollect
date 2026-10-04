"""Punto de entrada de la API de AntCollect Móvil (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .rutas import auth, coleccion, exportar, imagenes, lecturas

app = FastAPI(
    title="AntCollect API",
    version="0.2.0",
    description=(
        "API de AntCollect Móvil: cuentas, colección de monedas por usuario, "
        "fotos, lectura por IA con cuota diaria y exportación. "
        "La IA solo **propone** campos (`POST /lecturas`); nada se guarda en la "
        "colección sin que el cliente lo envíe tras la confirmación humana."
    ),
)

if config.cors_origenes:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in config.cors_origenes.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
        # Para que la app web lea el nombre del archivo de /exportar.
        expose_headers=["Content-Disposition"],
    )

app.include_router(auth.router)
app.include_router(coleccion.router)
app.include_router(imagenes.router)
app.include_router(lecturas.router)
app.include_router(exportar.router)


@app.get("/salud", tags=["salud"])
async def salud() -> dict[str, bool]:
    return {"ok": True}
