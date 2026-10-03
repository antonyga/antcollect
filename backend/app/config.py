"""Configuración del backend. Todo por variable de entorno, nada hardcodeado
(mismo principio que src/antcollect/config.py en la v1, RNF-5 extendido a
este contexto — ver Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./antcollect_dev.db"

    jwt_secret: str = "inseguro-solo-para-desarrollo-local"
    jwt_algoritmo: str = "HS256"
    jwt_acceso_minutos: int = 30
    jwt_refresco_dias: int = 30

    # --- Lectura por IA (RF-1/RF-2, RF-M3) ---
    # La clave vive SOLO aquí, en el backend (RNF-5): nunca en la app móvil.
    anthropic_api_key: str = ""
    modelo_ia: str = Field(default="claude-sonnet-5", validation_alias="ANTCOLLECT_MODELO")
    lecturas_ia_cuota_diaria: int = 20
    # Lado largo máximo de la imagen enviada a la IA (RNF-4, mismo valor que la v1).
    resize_lado_largo: int = 1568

    # --- Imágenes (RF-7/RF-8) ---
    # Lado largo máximo de la imagen almacenada (mismo valor que la v1).
    resize_almacenamiento: int = 2000
    # Tamaño máximo aceptado por subida, antes de redimensionar.
    imagen_max_bytes: int = 15 * 1024 * 1024

    # "local": carpeta en disco (desarrollo y tests). "s3": object storage
    # compatible con S3 (producción — Railway Buckets, ver README).
    almacen: Literal["local", "s3"] = "local"
    almacen_dir_local: Path = Path("./almacen_dev")
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None


config = Config()
