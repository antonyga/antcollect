"""Modelos ORM (SQLAlchemy 2.0): Usuario, Moneda y LecturaIA.

Adaptado de src/antcollect/modelo.py (v1): la dataclass ``Moneda`` pasa a ser
una tabla ORM con ``usuario_id`` (ownership) en vez de depender de
``sqlite3.Row``; se añade ``Usuario`` (no existía en la v1, de un solo
usuario). Ver catálogo de reutilización en
Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §6.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

EN_COLECCION = "en_coleccion"
DUPLICADA = "duplicada"
PARA_INTERCAMBIO = "para_intercambio"
ESTADOS = (EN_COLECCION, DUPLICADA, PARA_INTERCAMBIO)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    monedas: Mapped[list[Moneda]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    lecturas_ia: Mapped[list[LecturaIA]] = relationship(cascade="all, delete-orphan")


class Moneda(Base):
    """Un tipo de moneda catalogado, propiedad de un usuario (RF-M1, RF-M2).

    Mismo modelo de dominio que la v1 (pais + valor + anio + ceca + variante
    define el "tipo", ver Docs/AntCollect-Arquitectura-y-Requisitos.md §2),
    scopeado por `usuario_id`: la unicidad de tipo es *por usuario*, no global
    — dos usuarios distintos pueden catalogar la misma moneda cada uno.
    """

    __tablename__ = "monedas"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "pais_norm",
            "valor_norm",
            "anio",
            "ceca_norm",
            "variante_norm",
            name="uq_tipo_por_usuario",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )

    pais: Mapped[str] = mapped_column(String(200))
    valor_texto: Mapped[str] = mapped_column(String(200))
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ceca: Mapped[str | None] = mapped_column(String(200), nullable=True)
    variante: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notas: Mapped[str | None] = mapped_column(String, nullable=True)
    estado: Mapped[str] = mapped_column(String(50), default=EN_COLECCION)

    foto_anverso: Mapped[str | None] = mapped_column(String(500), nullable=True)
    foto_reverso: Mapped[str | None] = mapped_column(String(500), nullable=True)
    foto_detalle: Mapped[str | None] = mapped_column(String(500), nullable=True)

    fecha_agregada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    pais_norm: Mapped[str] = mapped_column(String(200))
    valor_norm: Mapped[str] = mapped_column(String(200))
    ceca_norm: Mapped[str] = mapped_column(String(200), default="")
    variante_norm: Mapped[str] = mapped_column(String(200), default="")

    usuario: Mapped[Usuario] = relationship(back_populates="monedas")


class LecturaIA(Base):
    """Registro de una lectura por IA consumida por un usuario, para la cuota
    diaria (RF-M3, RNF-M2). Solo guarda cuándo y de quién: ni las fotos ni el
    resultado (la lectura es una propuesta efímera hasta que el humano la
    confirma y la guarda como `Moneda`).
    """

    __tablename__ = "lecturas_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
