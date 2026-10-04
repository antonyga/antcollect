"""Política de privacidad y términos del servicio (RNF-M3).

Públicas (sin JWT): las tiendas exigen una URL accesible para enlazarlas
desde la ficha de la app, y la app las abre en el navegador. Se sirven desde
el propio backend para que la URL publicada vaya siempre con la versión
desplegada. El responsable y el email de contacto salen de la configuración
(`LEGAL_RESPONSABLE`, `LEGAL_CONTACTO`), no del código.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..config import config

router = APIRouter(tags=["legal"])

_DIR = Path(__file__).resolve().parent.parent / "legal"

# Fecha de la última revisión del contenido; cambiarla al editar los textos.
ACTUALIZADO = "4 de octubre de 2026"


def _pagina(nombre: str, titulo: str) -> str:
    contenido = Template((_DIR / f"{nombre}.html").read_text(encoding="utf-8")).substitute(
        responsable=escape(config.legal_responsable),
        contacto=escape(config.legal_contacto),
        actualizado=ACTUALIZADO,
    )
    base = Template((_DIR / "base.html").read_text(encoding="utf-8"))
    return base.substitute(titulo=titulo, contenido=contenido)


@router.get("/privacidad", response_class=HTMLResponse)
async def privacidad() -> str:
    return _pagina("privacidad", "Política de privacidad")


@router.get("/terminos", response_class=HTMLResponse)
async def terminos() -> str:
    return _pagina("terminos", "Términos del servicio")
