"""Procesado de imágenes de monedas antes de almacenarlas o enviarlas a la IA.

``redimensionar`` es copia tal cual de src/antcollect/imagenes.py (Pillow
puro, ver catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6). El resto de aquel
módulo (rutas en disco, nombres de fichero) se sustituye por ``almacen.py``.

Novedad respecto a la v1, porque ahora las fotos vienen de la cámara de un
móvil y de un cliente no confiable:

- Se aplica la orientación EXIF (las fotos de móvil suelen venir "de lado"
  con la rotación solo en metadatos).
- Se re-codifica siempre a JPEG sin metadatos: así no se guarda la
  geolocalización GPS que muchos móviles incrustan en la foto (privacidad,
  RNF-M3), y lo que se almacena es siempre una imagen válida.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

TIPO_CONTENIDO_JPEG = "image/jpeg"


class ImagenInvalidaError(Exception):
    """Los bytes recibidos no son una imagen que Pillow pueda abrir."""


def redimensionar(imagen: Image.Image, lado_largo_max: int) -> Image.Image:
    """Reduce la imagen si su lado largo supera ``lado_largo_max``. No amplía."""
    ancho, alto = imagen.size
    lado_largo = max(ancho, alto)
    if lado_largo <= lado_largo_max:
        return imagen
    escala = lado_largo_max / lado_largo
    nuevo_tamano = (round(ancho * escala), round(alto * escala))
    return imagen.resize(nuevo_tamano, Image.LANCZOS)


def normalizar_a_jpeg(datos: bytes, lado_largo_max: int) -> bytes:
    """Abre ``datos`` como imagen, la endereza según EXIF, la reduce a
    ``lado_largo_max`` y la devuelve como JPEG sin metadatos.

    Lanza :class:`ImagenInvalidaError` si no es una imagen válida (incluidas
    las "bombas de descompresión" que Pillow detecta por número de píxeles).
    """
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen = ImageOps.exif_transpose(imagen)
        imagen = redimensionar(imagen.convert("RGB"), lado_largo_max)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ImagenInvalidaError(str(exc)) from exc

    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()
