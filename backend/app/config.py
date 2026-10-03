"""Configuración del backend. Todo por variable de entorno, nada hardcodeado
(mismo principio que src/antcollect/config.py en la v1, RNF-5 extendido a
este contexto — ver Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §2).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./antcollect_dev.db"

    jwt_secret: str = "inseguro-solo-para-desarrollo-local"
    jwt_algoritmo: str = "HS256"
    jwt_acceso_minutos: int = 30
    jwt_refresco_dias: int = 30


config = Config()
