"""Almacenamiento de objetos para las imágenes de monedas.

Sustituye a la carpeta ``imagenes/`` local de la v1 (ver catálogo de
reutilización en Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6). Igual
que ``CoinReader`` desacopla el proveedor de IA (RNF-6), ``Almacen`` desacopla
el proveedor de almacenamiento: en desarrollo y tests, una carpeta en disco;
en producción, cualquier object storage compatible con S3 (Railway Buckets).

Las claves siempre empiezan por ``usuarios/{usuario_id}/`` (ver
:func:`clave_imagen`), de modo que borrar una cuenta es borrar un prefijo y
ninguna clave de un usuario puede coincidir con la de otro (RNF-M1).

Las implementaciones son síncronas (boto3 lo es); las rutas async las llaman
vía ``run_in_threadpool`` para no bloquear el event loop.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Literal

from .config import config

Cara = Literal["anverso", "reverso", "detalle"]
CARAS: tuple[Cara, ...] = ("anverso", "reverso", "detalle")


def prefijo_usuario(usuario_id: int) -> str:
    return f"usuarios/{usuario_id}/"


def clave_imagen(usuario_id: int, moneda_id: int, cara: Cara) -> str:
    """Clave derivada del id de la moneda, igual que el nombre de fichero de
    la v1 (``0001_anverso.jpg``), para trazabilidad."""
    return f"{prefijo_usuario(usuario_id)}monedas/{moneda_id:04d}_{cara}.jpg"


class ObjetoNoEncontradoError(Exception):
    pass


class Almacen(ABC):
    @abstractmethod
    def guardar(self, clave: str, datos: bytes, tipo_contenido: str) -> None: ...

    @abstractmethod
    def leer(self, clave: str) -> bytes:
        """Lanza :class:`ObjetoNoEncontradoError` si no existe."""

    @abstractmethod
    def borrar(self, clave: str) -> None:
        """Idempotente: borrar algo que no existe no es un error."""

    @abstractmethod
    def borrar_prefijo(self, prefijo: str) -> None:
        """Borra todos los objetos cuya clave empieza por ``prefijo``."""


class AlmacenLocal(Almacen):
    """Carpeta en disco. Para desarrollo local y tests, no para producción
    (el disco de un contenedor de Railway no es persistente)."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz.resolve()

    def _ruta(self, clave: str) -> Path:
        ruta = (self._raiz / clave).resolve()
        # Defensa en profundidad: las claves las genera el backend, nunca el
        # cliente, pero aun así no se permite salir de la raíz.
        if not ruta.is_relative_to(self._raiz):
            raise ValueError(f"Clave fuera del almacén: {clave!r}")
        return ruta

    def guardar(self, clave: str, datos: bytes, tipo_contenido: str) -> None:
        ruta = self._ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)

    def leer(self, clave: str) -> bytes:
        ruta = self._ruta(clave)
        if not ruta.is_file():
            raise ObjetoNoEncontradoError(clave)
        return ruta.read_bytes()

    def borrar(self, clave: str) -> None:
        self._ruta(clave).unlink(missing_ok=True)

    def borrar_prefijo(self, prefijo: str) -> None:
        # Los prefijos que usa el backend son siempre "carpetas" (acaban en
        # "/"), así que basta con borrar ese directorio entero.
        if not prefijo.endswith("/"):
            raise ValueError(f"Prefijo sin '/' final: {prefijo!r}")
        ruta = self._ruta(prefijo)
        if ruta != self._raiz and ruta.is_dir():
            shutil.rmtree(ruta)


class AlmacenS3(Almacen):
    """Object storage compatible con S3 (Railway Buckets, AWS S3, R2, MinIO...)."""

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        cliente=None,
    ) -> None:
        if cliente is None:
            import boto3

            cliente = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
        self._s3 = cliente
        self._bucket = bucket

    def guardar(self, clave: str, datos: bytes, tipo_contenido: str) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=clave, Body=datos, ContentType=tipo_contenido)

    def leer(self, clave: str) -> bytes:
        try:
            respuesta = self._s3.get_object(Bucket=self._bucket, Key=clave)
        except self._s3.exceptions.NoSuchKey as exc:
            raise ObjetoNoEncontradoError(clave) from exc
        return respuesta["Body"].read()

    def borrar(self, clave: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=clave)

    def borrar_prefijo(self, prefijo: str) -> None:
        paginador = self._s3.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=self._bucket, Prefix=prefijo):
            objetos = [{"Key": o["Key"]} for o in pagina.get("Contents", [])]
            if objetos:
                # delete_objects acepta hasta 1000 claves; list_objects_v2
                # devuelve como mucho 1000 por página, así que cuadra.
                self._s3.delete_objects(Bucket=self._bucket, Delete={"Objects": objetos})


@lru_cache
def obtener_almacen() -> Almacen:
    """Dependencia de FastAPI: el almacén configurado (se sustituye en tests)."""
    if config.almacen == "s3":
        if not config.s3_bucket:
            raise RuntimeError("ALMACEN=s3 requiere S3_BUCKET")
        return AlmacenS3(
            config.s3_bucket,
            endpoint_url=config.s3_endpoint_url,
            region=config.s3_region,
            access_key_id=config.s3_access_key_id,
            secret_access_key=config.s3_secret_access_key,
        )
    return AlmacenLocal(config.almacen_dir_local)
