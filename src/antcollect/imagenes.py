"""Guardado de imágenes de monedas (anverso/reverso) en disco.

Los ficheros se nombran a partir del id de la moneda para trazabilidad
(RNF-2): ``0001_anverso.jpg``. Se redimensionan con Pillow antes de guardar
(RNF-4) para no acumular fotos de móvil a resolución completa; este
redimensionado es el de almacenamiento, distinto del que se hará en la
Fase 2 antes de enviar a la IA (``config.RESIZE_LADO_LARGO``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from PIL import Image

from . import config

if TYPE_CHECKING:
    from .modelo import Moneda

Cara = Literal["anverso", "reverso"]


def _nombre_archivo(moneda_id: int, cara: Cara) -> str:
    return f"{moneda_id:04d}_{cara}.jpg"


def ruta_completa(nombre_archivo: str) -> Path:
    return config.IMAGENES_DIR / nombre_archivo


def redimensionar(imagen: Image.Image, lado_largo_max: int) -> Image.Image:
    """Reduce la imagen si su lado largo supera ``lado_largo_max``. No amplía."""
    ancho, alto = imagen.size
    lado_largo = max(ancho, alto)
    if lado_largo <= lado_largo_max:
        return imagen
    escala = lado_largo_max / lado_largo
    nuevo_tamano = (round(ancho * escala), round(alto * escala))
    return imagen.resize(nuevo_tamano, Image.LANCZOS)


def guardar_imagen(imagen: Image.Image, moneda_id: int, cara: Cara) -> str:
    """Redimensiona y guarda una foto de moneda. Devuelve el nombre de fichero."""
    config.asegurar_directorios()
    imagen = redimensionar(imagen.convert("RGB"), config.RESIZE_ALMACENAMIENTO)
    nombre = _nombre_archivo(moneda_id, cara)
    imagen.save(ruta_completa(nombre), "JPEG", quality=90)
    return nombre


def borrar_imagenes(moneda: Moneda) -> None:
    """Borra del disco las fotos asociadas a una moneda, si existen."""
    for nombre in (moneda.foto_anverso, moneda.foto_reverso):
        if not nombre:
            continue
        ruta_completa(nombre).unlink(missing_ok=True)
