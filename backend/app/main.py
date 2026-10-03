"""Punto de entrada de la API de AntCollect Móvil (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI

from .rutas import auth, coleccion

app = FastAPI(title="AntCollect API", version="0.1.0")

app.include_router(auth.router)
app.include_router(coleccion.router)


@app.get("/salud", tags=["salud"])
async def salud() -> dict[str, bool]:
    return {"ok": True}
