"""Servicio de colección: alta, edición, borrado, búsqueda y duplicados.

Toda escritura pasa por :func:`db.transaccion` (RNF-7) y solo se llama tras
la confirmación humana explícita en la UI (§2 CLAUDE.md) — este módulo no
decide nada por sí mismo, solo aplica lo que ya se confirmó.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from . import db, imagenes, modelo
from .modelo import Moneda
from .normalizacion import campos_normalizados, normalizar_anio, normalizar_texto

_CAMPOS_EDITABLES = {
    "pais",
    "valor_texto",
    "anio",
    "ceca",
    "variante",
    "notas",
    "estado",
    "foto_anverso",
    "foto_reverso",
    "foto_detalle",
}


class TipoDuplicadoError(Exception):
    """Ya existe un tipo con los mismos campos normalizados (RF-14)."""

    def __init__(self, existente: Moneda):
        self.existente = existente
        super().__init__(f"Ya existe un tipo igual: id={existente.id}")


def obtener(moneda_id: int) -> Moneda | None:
    con = db.conectar()
    try:
        fila = con.execute("SELECT * FROM monedas WHERE id = ?", (moneda_id,)).fetchone()
    finally:
        con.close()
    return Moneda.desde_fila(fila) if fila else None


def listar(
    *,
    texto: str | None = None,
    pais: str | None = None,
    valor: str | None = None,
    anio: int | None = None,
    estado: str | None = None,
) -> list[Moneda]:
    """Lista la colección aplicando los filtros dados (RF-9), todos opcionales."""
    condiciones: list[str] = []
    parametros: list[object] = []

    if texto:
        patron_norm = f"%{normalizar_texto(texto)}%"
        condiciones.append(
            "(pais_norm LIKE ? OR valor_norm LIKE ? OR ceca_norm LIKE ? OR variante_norm LIKE ?"
            " OR LOWER(COALESCE(notas, '')) LIKE ?)"
        )
        parametros += [patron_norm, patron_norm, patron_norm, patron_norm, f"%{texto.lower()}%"]

    if pais:
        condiciones.append("pais_norm LIKE ?")
        parametros.append(f"%{normalizar_texto(pais)}%")

    if valor:
        condiciones.append("valor_norm LIKE ?")
        parametros.append(f"%{normalizar_texto(valor)}%")

    if anio is not None:
        condiciones.append("anio = ?")
        parametros.append(anio)

    if estado:
        condiciones.append("estado = ?")
        parametros.append(estado)

    sql = "SELECT * FROM monedas"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY pais, valor_texto, anio"

    con = db.conectar()
    try:
        filas = con.execute(sql, parametros).fetchall()
    finally:
        con.close()
    return [Moneda.desde_fila(fila) for fila in filas]


def existe_tipo_exacto(
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
    ceca: str | None,
    variante: str | None,
    *,
    excluir_id: int | None = None,
) -> Moneda | None:
    """Busca un tipo con los mismos 5 campos normalizados (RF-14).

    Un ``anio`` desconocido (``None``) nunca cuenta como duplicado exacto: un
    año ilegible no puede confirmar que sea la misma moneda que otra también
    sin año (misma política que aplica el índice único de la BD, que trata
    cada ``NULL`` como distinto).
    """
    anio_norm = normalizar_anio(anio)
    if anio_norm is None:
        return None

    norm = campos_normalizados(pais, valor_texto, ceca, variante)
    sql = (
        "SELECT * FROM monedas WHERE pais_norm = ? AND valor_norm = ? "
        "AND anio = ? AND ceca_norm = ? AND variante_norm = ?"
    )
    parametros: list[object] = [
        norm["pais_norm"],
        norm["valor_norm"],
        anio_norm,
        norm["ceca_norm"],
        norm["variante_norm"],
    ]
    if excluir_id is not None:
        sql += " AND id != ?"
        parametros.append(excluir_id)

    con = db.conectar()
    try:
        fila = con.execute(sql, parametros).fetchone()
    finally:
        con.close()
    return Moneda.desde_fila(fila) if fila else None


def buscar_posibles_coincidencias(
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
) -> list[Moneda]:
    """Candidatos del mismo país+valor para que decida el humano (RF-2).

    Incluye monedas con ``anio`` NULL en la BD (podría ser la misma con año
    ilegible en su día). Si el año consultado es conocido, se limita a ese año
    o a NULL; si es desconocido, se listan todas las del mismo país+valor sin
    filtrar por año (un año ilegible no permite descartar ninguna).
    """
    anio_norm = normalizar_anio(anio)
    norm = campos_normalizados(pais, valor_texto, None, None)
    sql = "SELECT * FROM monedas WHERE pais_norm = ? AND valor_norm = ?"
    parametros: list[object] = [norm["pais_norm"], norm["valor_norm"]]
    if anio_norm is not None:
        sql += " AND (anio = ? OR anio IS NULL)"
        parametros.append(anio_norm)
    sql += " ORDER BY anio, ceca_norm, variante_norm"

    con = db.conectar()
    try:
        filas = con.execute(sql, parametros).fetchall()
    finally:
        con.close()
    return [Moneda.desde_fila(fila) for fila in filas]


def comprobar_tipo(
    *,
    pais: str | None,
    valor_texto: str | None,
    anio: int | str | None,
    ceca: str | None,
    variante: str | None,
    campos_dudosos: list[str] | None = None,
) -> tuple[str, Moneda | None, list[Moneda]]:
    """Responde "¿la tengo?" (RF-2) sobre los campos propuestos/confirmados.

    Devuelve una tupla ``(categoria, exacta, posibles)``:

    - ``"exacta"``: coincidencia exacta en los 5 campos, sin campos dudosos y
      con año conocido → ``exacta`` es la moneda ya catalogada, ``posibles``
      vacío.
    - ``"parcial"``: hay candidatos del mismo país+valor pero no se puede
      confirmar automáticamente (distinta ceca/variante, año NULL en la
      consulta o en la BD, o algún campo venía dudoso de la IA) → decide el
      humano viendo ``posibles``.
    - ``"ninguna"``: no hay ningún candidato parecido en la colección.
    """
    dudosos = campos_dudosos or []
    anio_norm = normalizar_anio(anio)

    if anio_norm is not None and not dudosos:
        exacta = existe_tipo_exacto(pais, valor_texto, anio_norm, ceca, variante)
        if exacta is not None:
            return "exacta", exacta, []

    posibles = buscar_posibles_coincidencias(pais, valor_texto, anio_norm)
    if posibles:
        return "parcial", None, posibles
    return "ninguna", None, []


def crear(
    *,
    pais: str,
    valor_texto: str,
    anio: int | str | None,
    ceca: str | None = None,
    variante: str | None = None,
    notas: str | None = None,
    estado: str = modelo.EN_COLECCION,
    foto_anverso: str | None = None,
    foto_reverso: str | None = None,
    foto_detalle: str | None = None,
) -> Moneda:
    """Da de alta un tipo nuevo (RF-6). Lanza :class:`TipoDuplicadoError` si ya existe.

    No hay forma de "forzar" un alta duplicada: dos tipos con los mismos 5
    campos normalizados son, por definición, el mismo tipo (§2.1 del doc de
    arquitectura). Si el usuario quiere guardar una variante, debe rellenar
    el campo ``variante`` para distinguirla — eso deja de ser un duplicado.
    """
    if estado not in modelo.ESTADOS:
        raise ValueError(f"Estado desconocido: {estado!r}")

    anio_norm = normalizar_anio(anio)
    existente = existe_tipo_exacto(pais, valor_texto, anio_norm, ceca, variante)
    if existente is not None:
        raise TipoDuplicadoError(existente)

    norm = campos_normalizados(pais, valor_texto, ceca, variante)
    with db.transaccion() as con:
        try:
            cursor = con.execute(
                """
                INSERT INTO monedas (
                    pais, valor_texto, anio, ceca, variante, notas, estado,
                    foto_anverso, foto_reverso, foto_detalle, fecha_agregada,
                    pais_norm, valor_norm, ceca_norm, variante_norm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pais.strip(),
                    valor_texto.strip(),
                    anio_norm,
                    ceca,
                    variante,
                    notas,
                    estado,
                    foto_anverso,
                    foto_reverso,
                    foto_detalle,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    norm["pais_norm"],
                    norm["valor_norm"],
                    norm["ceca_norm"],
                    norm["variante_norm"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            existente = existe_tipo_exacto(pais, valor_texto, anio_norm, ceca, variante)
            raise TipoDuplicadoError(existente) from exc
        moneda_id = cursor.lastrowid

    return obtener(moneda_id)


def editar(moneda_id: int, **cambios: object) -> Moneda:
    """Edita una moneda existente (RF-6). Solo cambia los campos pasados en ``cambios``."""
    actual = obtener(moneda_id)
    if actual is None:
        raise ValueError(f"No existe la moneda {moneda_id}")

    desconocidos = set(cambios) - _CAMPOS_EDITABLES
    if desconocidos:
        raise ValueError(f"Campos desconocidos: {desconocidos}")

    datos = {campo: getattr(actual, campo) for campo in _CAMPOS_EDITABLES}
    datos.update(cambios)
    datos["anio"] = normalizar_anio(datos["anio"])

    if datos["estado"] not in modelo.ESTADOS:
        raise ValueError(f"Estado desconocido: {datos['estado']!r}")

    existente = existe_tipo_exacto(
        datos["pais"],
        datos["valor_texto"],
        datos["anio"],
        datos["ceca"],
        datos["variante"],
        excluir_id=moneda_id,
    )
    if existente is not None:
        raise TipoDuplicadoError(existente)

    norm = campos_normalizados(
        datos["pais"], datos["valor_texto"], datos["ceca"], datos["variante"]
    )
    with db.transaccion() as con:
        try:
            con.execute(
                """
                UPDATE monedas SET
                    pais = ?, valor_texto = ?, anio = ?, ceca = ?, variante = ?, notas = ?,
                    estado = ?, foto_anverso = ?, foto_reverso = ?, foto_detalle = ?,
                    pais_norm = ?, valor_norm = ?, ceca_norm = ?, variante_norm = ?
                WHERE id = ?
                """,
                (
                    datos["pais"].strip(),
                    datos["valor_texto"].strip(),
                    datos["anio"],
                    datos["ceca"],
                    datos["variante"],
                    datos["notas"],
                    datos["estado"],
                    datos["foto_anverso"],
                    datos["foto_reverso"],
                    datos["foto_detalle"],
                    norm["pais_norm"],
                    norm["valor_norm"],
                    norm["ceca_norm"],
                    norm["variante_norm"],
                    moneda_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            existente = existe_tipo_exacto(
                datos["pais"],
                datos["valor_texto"],
                datos["anio"],
                datos["ceca"],
                datos["variante"],
                excluir_id=moneda_id,
            )
            raise TipoDuplicadoError(existente) from exc

    return obtener(moneda_id)


def borrar(moneda_id: int) -> None:
    """Borra una moneda y sus fotos asociadas (RF-11). Confirmación es cosa de la UI."""
    moneda = obtener(moneda_id)
    if moneda is None:
        return
    with db.transaccion() as con:
        con.execute("DELETE FROM monedas WHERE id = ?", (moneda_id,))
    imagenes.borrar_imagenes(moneda)
