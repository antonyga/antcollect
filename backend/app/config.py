"""Configuración del backend. Todo por variable de entorno, nada hardcodeado
(mismo principio que src/antcollect/config.py en la v1, RNF-5 extendido a
este contexto — ver Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./antcollect_dev.db"

    jwt_secret: str = "inseguro-solo-para-desarrollo-local"
    jwt_algoritmo: str = "HS256"
    jwt_acceso_minutos: int = 30
    jwt_refresco_dias: int = 30

    # Orígenes permitidos por CORS, separados por comas. Vacío (por defecto) =
    # CORS desactivado: la app nativa no lo necesita. Solo hace falta para
    # desarrollar la app Flutter en el navegador (`flutter run -d chrome`).
    cors_origenes: str = ""

    # --- Política de privacidad y términos (RNF-M3, rutas/legal.py) ---
    # Quién presta el servicio y dónde se le escribe. Obligatorio rellenarlos
    # antes de publicar: los valores por defecto se ven a propósito.
    legal_responsable: str = "[LEGAL_RESPONSABLE sin configurar]"
    legal_contacto: str = "[LEGAL_CONTACTO sin configurar]"

    # --- Lectura por IA (RF-1/RF-2, RF-M3) ---
    # La clave vive SOLO aquí, en el backend (RNF-5): nunca en la app móvil.
    anthropic_api_key: str = ""
    modelo_ia: str = Field(default="claude-sonnet-5", validation_alias="ANTCOLLECT_MODELO")
    # Respaldo si Claude falla (en este orden). Clave vacía = ese respaldo no
    # se usa. Se aceptan los nombres estándar y los usados en el .env del
    # usuario (OPEN_AI_API_KEY, DEEPSEE_API_KEY).
    openai_api_key: str = Field(
        default="", validation_alias=AliasChoices("OPENAI_API_KEY", "OPEN_AI_API_KEY")
    )
    modelo_openai: str = Field(default="gpt-6.1-sol", validation_alias="ANTCOLLECT_MODELO_OPENAI")
    deepseek_api_key: str = Field(
        default="", validation_alias=AliasChoices("DEEPSEEK_API_KEY", "DEEPSEE_API_KEY")
    )
    modelo_deepseek: str = Field(
        default="deepseek-flash", validation_alias="ANTCOLLECT_MODELO_DEEPSEEK"
    )
    # Por proveedor. Timeout corto y sin reintentos del SDK: ante un fallo se
    # pasa al siguiente proveedor al momento, en vez de esperar reintentos.
    ia_timeout_segundos: float = 45.0
    ia_reintentos: int = 0

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
