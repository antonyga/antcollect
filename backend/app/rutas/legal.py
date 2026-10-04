"""Política de privacidad, términos del servicio y página web de borrado de
cuenta (RNF-M3, RF-M1).

Públicas (sin JWT): las tiendas exigen una URL accesible para enlazarlas
desde la ficha de la app, y la app las abre en el navegador. Google Play
pide además una URL donde borrar la cuenta sin tener la app instalada
(`/borrar-cuenta`, con email y contraseña). Se sirven desde
el propio backend para que la URL publicada vaya siempre con la versión
desplegada. El responsable y el email de contacto salen de la configuración
(`LEGAL_RESPONSABLE`, `LEGAL_CONTACTO`), no del código.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import HTMLResponse

from .. import auth
from ..config import config
from ..dependencias import AlmacenDep, SesionDep
from .auth import borrar_cuenta_y_fotos

router = APIRouter(tags=["legal"])

_DIR = Path(__file__).resolve().parent.parent / "legal"

# Fecha de la última revisión del contenido; cambiarla al editar los textos.
ACTUALIZADO = "4 de octubre de 2026"


def _pagina(nombre: str, titulo: str, aviso: str = "") -> str:
    contenido = Template((_DIR / f"{nombre}.html").read_text(encoding="utf-8")).substitute(
        responsable=escape(config.legal_responsable),
        contacto=escape(config.legal_contacto),
        actualizado=ACTUALIZADO,
        aviso=aviso,
    )
    base = Template((_DIR / "base.html").read_text(encoding="utf-8"))
    return base.substitute(titulo=titulo, contenido=contenido)


@router.get("/privacidad", response_class=HTMLResponse)
async def privacidad() -> str:
    return _pagina("privacidad", "Política de privacidad")


@router.get("/terminos", response_class=HTMLResponse)
async def terminos() -> str:
    return _pagina("terminos", "Términos del servicio")


@router.get("/borrar-cuenta", response_class=HTMLResponse)
async def borrar_cuenta_formulario() -> str:
    return _pagina("borrar_cuenta", "Borrar tu cuenta")


@router.post("/borrar-cuenta", response_class=HTMLResponse)
async def borrar_cuenta_web(
    email: Annotated[str, Form()],
    contrasena: Annotated[str, Form()],
    sesion: SesionDep,
    almacen: AlmacenDep,
) -> HTMLResponse:
    """Mismo borrado que `POST /auth/cuenta/borrar` (fotos, colección,
    cuenta), autenticando con email y contraseña en vez de con el JWT."""
    try:
        usuario, _tokens = await auth.autenticar(sesion, email, contrasena)
    except auth.CredencialesInvalidasError:
        aviso = '<p class="aviso">Email o contraseña incorrectos. No se ha borrado nada.</p>'
        return HTMLResponse(
            _pagina("borrar_cuenta", "Borrar tu cuenta", aviso),
            status_code=status.HTTP_403_FORBIDDEN,
        )
    await borrar_cuenta_y_fotos(sesion, almacen, usuario.id)
    return HTMLResponse(_pagina("cuenta_borrada", "Cuenta borrada"))
