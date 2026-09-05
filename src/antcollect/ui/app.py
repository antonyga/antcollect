"""Interfaz Gradio de AntCollect.

Fase 1: catálogo manual completo (RF-6, RF-9, RF-10, RF-11, RF-12).
Fase 2: flujo "Enseñar moneda nueva" (RF-1) con lectura por IA (`CoinReader`)
seguida de confirmación humana (RF-3).
Fase 3: flujo "¿La tengo?" (RF-2, RF-4, RF-5), reutilizando el mismo pipeline
captura → leer → confirmar; solo cambia el paso final (guardar vs. consultar).
"""

from __future__ import annotations

import io

import gradio as gr

from .. import coleccion, config, exportar, imagenes, modelo
from ..ai.base import LecturaMoneda, es_lectura_fallida
from ..ai.claude import ClaudeCoinReader
from ..coleccion import TipoDuplicadoError
from ..modelo import Moneda

_AVISO_SIN_IA = (
    "ℹ️ No hay `ANTHROPIC_API_KEY` configurada: la lectura por IA estará "
    "desactivada. El modo manual funciona sin conexión."
)

# Cámara trasera por defecto en móvil (no la frontal/selfie) y sin espejar la
# imagen: una moneda espejada puede leerse mal (ceca, letras). Gradio ya
# enumera las cámaras disponibles y deja elegir cuando hay varias (webcam +
# microscopio Jiusion UVC en escritorio), sin necesidad de UI propia (RF-8).
_OPCIONES_CAMARA = gr.WebcamOptions(mirror=False, constraints={"facingMode": "environment"})

# Móvil (§10): tacto más cómodo en pantallas estrechas — botones/inputs algo
# más grandes (Gradio ya reordena las filas en columna en breakpoints móviles).
_CSS = """
@media (max-width: 640px) {
    button { font-size: 1.05em; min-height: 2.6em; }
    input, textarea { font-size: 1.05em; }
}
"""

_ESTADOS_ETIQUETAS = [
    ("En colección", modelo.EN_COLECCION),
    ("Duplicada", modelo.DUPLICADA),
    ("Para intercambio", modelo.PARA_INTERCAMBIO),
]

_ESTADO_SLUG_A_ETIQUETA = {slug: etiqueta for etiqueta, slug in _ESTADOS_ETIQUETAS}
_ESTADO_ETIQUETA_A_SLUG = {etiqueta: slug for etiqueta, slug in _ESTADOS_ETIQUETAS}
_FILTRO_ESTADO_TODOS = "(todos)"

_ENCABEZADOS_TABLA = ["id", "País", "Valor", "Año", "Ceca", "Variante", "Estado"]


def _etiqueta_estado(estado: str) -> str:
    return _ESTADO_SLUG_A_ETIQUETA.get(estado, estado)


_ETIQUETA_PAIS = "País *"
_ETIQUETA_VALOR = "Valor *"
_ETIQUETA_ANIO = "Año (vacío si es ilegible)"
_ETIQUETA_CECA = "Ceca"
_ETIQUETA_VARIANTE = "Variante"

_ETIQUETAS_CAMPOS = {
    "pais": _ETIQUETA_PAIS,
    "valor": _ETIQUETA_VALOR,
    "anio": _ETIQUETA_ANIO,
    "ceca": _ETIQUETA_CECA,
    "variante": _ETIQUETA_VARIANTE,
}

_NOMBRES_CAMPOS = {
    "pais": "país",
    "valor": "valor",
    "anio": "año",
    "ceca": "ceca",
    "variante": "variante",
}


def _campo_ia(valor: str | None, campo: str, dudosos: list[str]):
    """Valor propuesto por la IA; si es un campo dudoso, resalta la etiqueta."""
    base = _ETIQUETAS_CAMPOS[campo]
    etiqueta = f"⚠️ {base} — revisar" if campo in dudosos else base
    return gr.update(value=valor or "", label=etiqueta)


def _aviso_lectura_ia(lectura: LecturaMoneda) -> str:
    if es_lectura_fallida(lectura):
        return (
            "⚠️ No se pudo leer la moneda con IA (sin conexión o error del servicio). "
            "Rellena los campos a mano."
        )
    if lectura.campos_dudosos:
        nombres = ", ".join(_NOMBRES_CAMPOS.get(c, c) for c in lectura.campos_dudosos)
        return f"ℹ️ Campos propuestos por la IA. Revisa especialmente: **{nombres}**."
    return "ℹ️ Campos propuestos por la IA. Revísalos antes de guardar."


def _imagen_a_bytes(imagen) -> bytes | None:
    if imagen is None:
        return None
    buffer = io.BytesIO()
    imagen.convert("RGB").save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _fila_tabla(m: Moneda) -> list:
    return [
        m.id,
        m.pais,
        m.valor_texto,
        m.anio if m.anio is not None else "",
        m.ceca or "",
        m.variante or "",
        _etiqueta_estado(m.estado),
    ]


def _filas_tabla(monedas: list[Moneda]) -> list[list]:
    return [_fila_tabla(m) for m in monedas]


def _etiqueta_moneda(m: Moneda) -> str:
    partes = [m.pais, m.valor_texto, str(m.anio) if m.anio is not None else "año ?"]
    if m.ceca:
        partes.append(f"ceca {m.ceca}")
    if m.variante:
        partes.append(m.variante)
    return " · ".join(partes) + f"  (#{m.id})"


def _opciones_selector(monedas: list[Moneda]) -> list[tuple[str, int]]:
    return [(_etiqueta_moneda(m), m.id) for m in monedas]


def _datos_ficha(m: Moneda) -> tuple[str, str | None, str | None, str | None, str]:
    titulo = f"### {m.pais} — {m.valor_texto}"
    detalles = (
        f"- **Año:** {m.anio if m.anio is not None else 'desconocido'}\n"
        f"- **Ceca:** {m.ceca or '—'}\n"
        f"- **Variante:** {m.variante or '—'}\n"
        f"- **Estado:** {_etiqueta_estado(m.estado)}\n"
        f"- **Notas:** {m.notas or '—'}\n"
        f"- **Añadida el:** {m.fecha_agregada}\n"
    )
    foto_anverso = str(imagenes.ruta_completa(m.foto_anverso)) if m.foto_anverso else None
    foto_reverso = str(imagenes.ruta_completa(m.foto_reverso)) if m.foto_reverso else None
    foto_detalle = str(imagenes.ruta_completa(m.foto_detalle)) if m.foto_detalle else None
    return titulo, foto_anverso, foto_reverso, foto_detalle, detalles


def _texto_duplicado(existente: Moneda) -> str:
    return (
        "⚠️ **Ya existe un tipo igual** (mismos país, valor, año, ceca y variante): "
        f"{_etiqueta_moneda(existente)}.\n\n"
        "Si es una variante distinta, rellena el campo **Variante** para diferenciarla. "
        "Si no, cancela: puede que ya la tengas catalogada."
    )


def _parsear_campos_formulario(
    pais: str,
    valor_texto: str,
    anio: str,
    ceca: str,
    variante: str,
    notas: str | None = None,
) -> tuple[dict[str, object] | None, str | None]:
    """Valida y normaliza los campos del formulario compartido (RF-1/RF-2/RF-6).

    Usado tanto para guardar como para comprobar "¿la tengo?": ambos flujos
    parten del mismo formulario confirmado por el humano (§1 CLAUDE.md).
    """
    pais = (pais or "").strip()
    valor_texto = (valor_texto or "").strip()
    anio_texto = (anio or "").strip()
    if not pais or not valor_texto:
        return None, "⚠️ País y valor son obligatorios."
    if anio_texto and not anio_texto.isdigit():
        return None, "⚠️ El año debe ser un número (déjalo vacío si es ilegible)."
    return {
        "pais": pais,
        "valor_texto": valor_texto,
        "anio": int(anio_texto) if anio_texto else None,
        "ceca": (ceca or "").strip() or None,
        "variante": (variante or "").strip() or None,
        "notas": (notas or "").strip() or None,
    }, None


def _titulo_captura_para_modo(modo: str) -> str:
    return "## ¿La tengo?" if modo == "comprobar" else "## Enseñar moneda nueva"


def _instrucciones_captura_para_modo(modo: str) -> str:
    base = "Sube la foto del anverso (el reverso es opcional, pero ayuda a leer mejor la moneda)."
    if modo == "comprobar":
        return (
            f"{base} Comprobaremos si ya está en tu colección; revisa los campos "
            "propuestos antes de buscar."
        )
    return f"{base} La IA solo propone los campos: revísalos antes de guardar nada."


def _titulo_formulario_para_modo(modo: str, *, con_ia: bool) -> str:
    if modo == "comprobar":
        if con_ia:
            return "### ¿La tengo? (propuesta por IA — revisa antes de buscar)"
        return "### ¿La tengo? — revisa los campos antes de buscar"
    if con_ia:
        return "### Moneda nueva (propuesta por IA — revisa antes de guardar)"
    return "### Nueva moneda"


def _botones_formulario_para_modo(modo: str) -> tuple:
    es_comprobar = modo == "comprobar"
    return gr.update(visible=not es_comprobar), gr.update(visible=es_comprobar)


def _texto_resultado_exacta(existente: Moneda) -> str:
    return (
        "## ✅ Ya la tienes\n\n"
        f"Coincide con lo que ya tienes catalogado: **{_etiqueta_moneda(existente)}**."
    )


def _texto_resultado_ninguna() -> str:
    return (
        "## 🆕 No la tienes\n\n"
        "No hay ningún tipo igual en tu colección. Puedes guardarla como nueva."
    )


def _texto_resultado_parcial(posibles: list[Moneda]) -> str:
    lineas = "\n".join(f"- {_etiqueta_moneda(m)}" for m in posibles)
    return (
        "## 🤔 Posible coincidencia\n\n"
        "Hay uno o más tipos parecidos en tu colección, pero no coinciden con "
        "seguridad en los 5 campos (revisa año, ceca o variante, o algún campo "
        "propuesto por la IA era dudoso). Decide tú si es la misma moneda:\n\n"
        f"{lineas}"
    )


def _guardar_fotos(
    moneda_id: int,
    foto_anverso_img,
    foto_reverso_img,
    foto_detalle_img,
    anterior: Moneda | None,
) -> None:
    """Guarda/borra fotos según lo que haya en el formulario, comparado con lo anterior."""
    cambios: dict[str, str | None] = {}

    for campo, cara, imagen in (
        ("foto_anverso", "anverso", foto_anverso_img),
        ("foto_reverso", "reverso", foto_reverso_img),
        ("foto_detalle", "detalle", foto_detalle_img),
    ):
        if imagen is not None:
            cambios[campo] = imagenes.guardar_imagen(imagen, moneda_id, cara)
        elif anterior is not None and getattr(anterior, campo):
            imagenes.ruta_completa(getattr(anterior, campo)).unlink(missing_ok=True)
            cambios[campo] = None

    if cambios:
        coleccion.editar(moneda_id, **cambios)


def construir() -> gr.Blocks:  # noqa: C901 - wiring de UI, no lógica de negocio
    """Construye la app Gradio."""
    with gr.Blocks(title="AntCollect") as app:
        gr.Markdown(
            "# AntCollect\n"
            "**La máquina propone, el humano dispone.** La IA solo sugiere los "
            "campos leídos de la foto; tú los confirmas antes de guardar nada."
        )

        with gr.Tabs() as pestañas:
            with gr.Tab("🏠 Inicio", id="inicio"):
                with gr.Row(equal_height=True):
                    boton_ir_enseñar = gr.Button(
                        "📖  Enseñar moneda nueva", variant="primary", size="lg"
                    )
                    boton_ir_comprobar = gr.Button("🔎  ¿La tengo?", variant="secondary", size="lg")
                if not config.hay_ia():
                    gr.Markdown(_AVISO_SIN_IA)

            with gr.Tab("📚 Colección", id="coleccion"):
                id_ficha_actual = gr.State(None)
                id_en_edicion = gr.State(None)
                modo_flujo = gr.State("nueva")
                id_resultado_exacta = gr.State(None)

                with gr.Group(visible=True) as panel_lista:
                    gr.Markdown("## Colección")
                    with gr.Row():
                        filtro_texto = gr.Textbox(
                            label="Buscar", placeholder="país, valor, ceca, notas…", scale=2
                        )
                        filtro_pais = gr.Textbox(label="País")
                        filtro_valor = gr.Textbox(label="Valor")
                        # Textbox y no Number: en esta versión de Gradio, gr.Number con
                        # value=None se renderiza en el navegador como "0" en la carga
                        # inicial y ese 0 se envía de verdad al backend (rompe "Buscar"
                        # sin tocar el año). Se parsea el año a mano abajo.
                        filtro_anio = gr.Textbox(label="Año", placeholder="p. ej. 2002")
                        filtro_estado = gr.Dropdown(
                            label="Estado",
                            choices=[_FILTRO_ESTADO_TODOS, *_ESTADO_ETIQUETA_A_SLUG],
                            value=_FILTRO_ESTADO_TODOS,
                        )
                    with gr.Row():
                        boton_buscar = gr.Button("🔍 Buscar", size="lg")
                        boton_limpiar = gr.Button("Limpiar filtros")
                        boton_nueva = gr.Button("➕ Añadir moneda", variant="primary", size="lg")
                        boton_exportar_csv = gr.DownloadButton("⬇️ Exportar CSV")
                        boton_exportar_json = gr.DownloadButton("⬇️ Exportar JSON")
                    tabla = gr.Dataframe(
                        headers=_ENCABEZADOS_TABLA,
                        datatype=["number", "str", "str", "number", "str", "str", "str"],
                        interactive=False,
                        row_count=(0, "dynamic"),
                        value=_filas_tabla(coleccion.listar()),
                    )
                    selector = gr.Dropdown(
                        label="Abrir ficha de…",
                        choices=_opciones_selector(coleccion.listar()),
                        value=None,
                    )

                with gr.Group(visible=False) as panel_captura:
                    titulo_captura = gr.Markdown("## Enseñar moneda nueva")
                    instrucciones_captura = gr.Markdown(_instrucciones_captura_para_modo("nueva"))
                    with gr.Row():
                        captura_anverso = gr.Image(
                            label="Foto anverso (completa)",
                            type="pil",
                            webcam_options=_OPCIONES_CAMARA,
                        )
                        captura_reverso = gr.Image(
                            label="Foto reverso (completa, opcional)",
                            type="pil",
                            webcam_options=_OPCIONES_CAMARA,
                        )
                    gr.Markdown(
                        "🔬 **Detalle/macro (opcional):** un primer plano (p. ej. con un "
                        "microscopio USB) para leer mejor una ceca, variante o error. Es "
                        "solo apoyo para confirmar campos dudosos a simple vista — nunca "
                        "se envía a la IA ni sustituye a la foto completa de arriba."
                    )
                    captura_detalle = gr.Image(
                        label="Foto de detalle/macro (opcional)",
                        type="pil",
                        webcam_options=_OPCIONES_CAMARA,
                    )
                    aviso_captura = gr.Markdown(visible=False)
                    with gr.Row():
                        boton_leer_ia = gr.Button("🔎 Leer con IA", variant="primary", size="lg")
                        boton_manual_en_vez = gr.Button("Prefiero rellenarlo a mano")
                        boton_cancelar_captura = gr.Button("Cancelar")

                with gr.Group(visible=False) as panel_formulario:
                    titulo_formulario = gr.Markdown("### Nueva moneda")
                    with gr.Row():
                        campo_pais = gr.Textbox(label=_ETIQUETA_PAIS)
                        campo_valor = gr.Textbox(
                            label=_ETIQUETA_VALOR, placeholder="p. ej. 2 euros"
                        )
                        campo_anio = gr.Textbox(label=_ETIQUETA_ANIO, placeholder="p. ej. 2002")
                    with gr.Row():
                        campo_ceca = gr.Textbox(label=_ETIQUETA_CECA)
                        campo_variante = gr.Textbox(label=_ETIQUETA_VARIANTE)
                        campo_estado = gr.Dropdown(
                            label="Estado",
                            choices=_ESTADOS_ETIQUETAS,
                            value=modelo.EN_COLECCION,
                        )
                    campo_notas = gr.Textbox(label="Notas", lines=3)
                    with gr.Row():
                        campo_foto_anverso = gr.Image(
                            label="Foto anverso", type="pil", webcam_options=_OPCIONES_CAMARA
                        )
                        campo_foto_reverso = gr.Image(
                            label="Foto reverso", type="pil", webcam_options=_OPCIONES_CAMARA
                        )
                        campo_foto_detalle = gr.Image(
                            label="Foto de detalle/macro (opcional, apoyo humano)",
                            type="pil",
                            webcam_options=_OPCIONES_CAMARA,
                        )
                    aviso_formulario = gr.Markdown(visible=False)
                    with gr.Row():
                        boton_guardar = gr.Button("💾 Guardar", variant="primary", size="lg")
                        boton_comprobar_bd = gr.Button(
                            "🔎 Buscar en mi colección",
                            variant="primary",
                            visible=False,
                            size="lg",
                        )
                        boton_cancelar_formulario = gr.Button("Cancelar")

                with gr.Group(visible=False) as panel_resultado_comprobacion:
                    resultado_texto = gr.Markdown()
                    with gr.Row(visible=False) as resultado_fotos_comparacion:
                        with gr.Column():
                            gr.Markdown("**Ya en tu colección**")
                            resultado_foto_existente_anverso = gr.Image(
                                interactive=False, label="Anverso guardado"
                            )
                            resultado_foto_existente_reverso = gr.Image(
                                interactive=False, label="Reverso guardado"
                            )
                        with gr.Column():
                            gr.Markdown("**Foto que acabas de capturar**")
                            resultado_foto_capturada_anverso = gr.Image(
                                interactive=False, label="Tu anverso"
                            )
                            resultado_foto_capturada_reverso = gr.Image(
                                interactive=False, label="Tu reverso"
                            )
                    resultado_selector = gr.Dropdown(
                        label="Ver ficha de…", choices=[], value=None, visible=False
                    )
                    with gr.Row():
                        boton_ver_ficha_resultado = gr.Button("👁️ Ver ficha completa", visible=False)
                        boton_guardar_de_todos_modos = gr.Button(
                            "💾 Guardar esta como nueva", variant="primary", visible=False
                        )
                        boton_volver_resultado = gr.Button("⬅️ Volver al listado")

                with gr.Group(visible=False) as panel_ficha:
                    ficha_titulo = gr.Markdown()
                    with gr.Row():
                        ficha_foto_anverso = gr.Image(label="Anverso", interactive=False)
                        ficha_foto_reverso = gr.Image(label="Reverso", interactive=False)
                        ficha_foto_detalle = gr.Image(label="Detalle/macro", interactive=False)
                    ficha_detalles = gr.Markdown()
                    with gr.Row():
                        boton_editar = gr.Button("✏️ Editar")
                        boton_borrar = gr.Button("🗑️ Borrar", variant="stop")
                        boton_volver = gr.Button("⬅️ Volver al listado")
                    with gr.Group(visible=False) as panel_confirmar_borrado:
                        gr.Markdown("¿Seguro que quieres borrar esta moneda? No se puede deshacer.")
                        with gr.Row():
                            boton_confirmar_borrado = gr.Button("Sí, borrar", variant="stop")
                            boton_cancelar_borrado = gr.Button("Cancelar")

                def _buscar(texto, pais, valor, anio, estado):
                    anio_texto = (anio or "").strip()
                    anio_filtro = int(anio_texto) if anio_texto.isdigit() else None
                    monedas = coleccion.listar(
                        texto=texto or None,
                        pais=pais or None,
                        valor=valor or None,
                        anio=anio_filtro,
                        estado=_ESTADO_ETIQUETA_A_SLUG.get(estado),
                    )
                    return _filas_tabla(monedas), gr.update(
                        choices=_opciones_selector(monedas), value=None
                    )

                def _limpiar_filtros():
                    monedas = coleccion.listar()
                    return (
                        "",
                        "",
                        "",
                        "",
                        _FILTRO_ESTADO_TODOS,
                        _filas_tabla(monedas),
                        gr.update(choices=_opciones_selector(monedas), value=None),
                    )

                def _exportar_csv():
                    # gr.DownloadButton necesita 2 clics: el primero genera el
                    # archivo y lo convierte en enlace real; sin cambiar la
                    # etiqueta, un solo clic no parece hacer nada. El segundo
                    # clic (ya con el enlace listo) dispara la descarga.
                    ruta = exportar.exportar_csv(coleccion.listar())
                    return gr.update(value=str(ruta), label="✅ Pulsa para descargar el CSV")

                def _exportar_json():
                    ruta = exportar.exportar_json(coleccion.listar())
                    return gr.update(value=str(ruta), label="✅ Pulsa para descargar el JSON")

                def _abrir_formulario_nuevo():
                    return (
                        gr.update(visible=False),  # panel_lista
                        gr.update(visible=True),  # panel_formulario
                        gr.update(visible=False),  # panel_ficha
                        "### Nueva moneda",
                        gr.update(value="", label=_ETIQUETA_PAIS),
                        gr.update(value="", label=_ETIQUETA_VALOR),
                        gr.update(value="", label=_ETIQUETA_ANIO),
                        gr.update(value="", label=_ETIQUETA_CECA),
                        gr.update(value="", label=_ETIQUETA_VARIANTE),
                        modelo.EN_COLECCION,
                        "",
                        None,  # campo_foto_anverso
                        None,  # campo_foto_reverso
                        None,  # campo_foto_detalle
                        gr.update(visible=False, value=""),
                        None,  # id_en_edicion
                    )

                def _abrir_ficha(moneda_id):
                    if moneda_id is None:
                        return (gr.update(),) * 8 + (None,)
                    m = coleccion.obtener(int(moneda_id))
                    if m is None:
                        return (gr.update(),) * 8 + (None,)
                    titulo, foto_a, foto_r, foto_d, detalles = _datos_ficha(m)
                    return (
                        gr.update(visible=False),  # panel_lista
                        gr.update(visible=False),  # panel_formulario
                        gr.update(visible=True),  # panel_ficha
                        titulo,
                        foto_a,
                        foto_r,
                        foto_d,
                        detalles,
                        m.id,
                    )

                def _iniciar_edicion(moneda_id):
                    m = coleccion.obtener(moneda_id) if moneda_id is not None else None
                    if m is None:
                        return (gr.update(),) * 16
                    foto_a = str(imagenes.ruta_completa(m.foto_anverso)) if m.foto_anverso else None
                    foto_r = str(imagenes.ruta_completa(m.foto_reverso)) if m.foto_reverso else None
                    foto_d = str(imagenes.ruta_completa(m.foto_detalle)) if m.foto_detalle else None
                    return (
                        gr.update(visible=False),  # panel_lista
                        gr.update(visible=True),  # panel_formulario
                        gr.update(visible=False),  # panel_ficha
                        f"### Editar: {m.pais} — {m.valor_texto}",
                        gr.update(value=m.pais, label=_ETIQUETA_PAIS),
                        gr.update(value=m.valor_texto, label=_ETIQUETA_VALOR),
                        gr.update(
                            value=str(m.anio) if m.anio is not None else "", label=_ETIQUETA_ANIO
                        ),
                        gr.update(value=m.ceca or "", label=_ETIQUETA_CECA),
                        gr.update(value=m.variante or "", label=_ETIQUETA_VARIANTE),
                        m.estado,
                        m.notas or "",
                        foto_a,
                        foto_r,
                        foto_d,
                        gr.update(visible=False, value=""),
                        m.id,
                    )

                def _guardar(
                    id_edicion,
                    pais,
                    valor_texto,
                    anio,
                    ceca,
                    variante,
                    notas,
                    estado,
                    foto_anverso_img,
                    foto_reverso_img,
                    foto_detalle_img,
                ):
                    datos, error = _parsear_campos_formulario(
                        pais, valor_texto, anio, ceca, variante, notas
                    )
                    if error:
                        aviso = gr.update(visible=True, value=error)
                        return (
                            gr.update(visible=False),  # panel_lista
                            gr.update(visible=True),  # panel_formulario
                            gr.update(visible=False),  # panel_ficha
                            gr.update(),  # ficha_titulo
                            gr.update(),  # ficha_foto_anverso
                            gr.update(),  # ficha_foto_reverso
                            gr.update(),  # ficha_foto_detalle
                            gr.update(),  # ficha_detalles
                            aviso,
                            gr.update(),
                            gr.update(),
                        )

                    pais, valor_texto, anio_valor, ceca, variante, notas = (
                        datos["pais"],
                        datos["valor_texto"],
                        datos["anio"],
                        datos["ceca"],
                        datos["variante"],
                        datos["notas"],
                    )

                    try:
                        if id_edicion is None:
                            moneda = coleccion.crear(
                                pais=pais,
                                valor_texto=valor_texto,
                                anio=anio_valor,
                                ceca=ceca,
                                variante=variante,
                                notas=notas,
                                estado=estado,
                            )
                            _guardar_fotos(
                                moneda.id,
                                foto_anverso_img,
                                foto_reverso_img,
                                foto_detalle_img,
                                None,
                            )
                        else:
                            anterior = coleccion.obtener(id_edicion)
                            moneda = coleccion.editar(
                                id_edicion,
                                pais=pais,
                                valor_texto=valor_texto,
                                anio=anio_valor,
                                ceca=ceca,
                                variante=variante,
                                notas=notas,
                                estado=estado,
                            )
                            _guardar_fotos(
                                moneda.id,
                                foto_anverso_img,
                                foto_reverso_img,
                                foto_detalle_img,
                                anterior,
                            )
                    except TipoDuplicadoError as exc:
                        aviso = gr.update(visible=True, value=_texto_duplicado(exc.existente))
                        return (
                            gr.update(visible=False),  # panel_lista
                            gr.update(visible=True),  # panel_formulario
                            gr.update(visible=False),  # panel_ficha
                            gr.update(),  # ficha_titulo
                            gr.update(),  # ficha_foto_anverso
                            gr.update(),  # ficha_foto_reverso
                            gr.update(),  # ficha_foto_detalle
                            gr.update(),  # ficha_detalles
                            aviso,
                            gr.update(),
                            gr.update(),
                        )

                    moneda = coleccion.obtener(moneda.id)
                    titulo, foto_a, foto_r, foto_d, detalles = _datos_ficha(moneda)
                    return (
                        gr.update(visible=False),  # panel_lista
                        gr.update(visible=False),  # panel_formulario
                        gr.update(visible=True),  # panel_ficha
                        titulo,
                        foto_a,
                        foto_r,
                        foto_d,
                        detalles,
                        gr.update(visible=False, value=""),
                        moneda.id,
                        None,  # id_en_edicion se limpia
                    )

                def _comprobar(
                    pais, valor_texto, anio, ceca, variante, foto_anverso_img, foto_reverso_img
                ):
                    """Consulta "¿la tengo?" (RF-2) con los campos ya confirmados por el humano."""
                    datos, error = _parsear_campos_formulario(
                        pais, valor_texto, anio, ceca, variante
                    )
                    if error:
                        return (
                            gr.update(visible=True),  # panel_formulario
                            gr.update(visible=False),  # panel_resultado_comprobacion
                            gr.update(visible=True, value=error),  # aviso_formulario
                            "",  # resultado_texto
                            gr.update(visible=False),  # resultado_fotos_comparacion
                            None,  # resultado_foto_existente_anverso
                            None,  # resultado_foto_existente_reverso
                            foto_anverso_img,  # resultado_foto_capturada_anverso
                            foto_reverso_img,  # resultado_foto_capturada_reverso
                            gr.update(visible=False, choices=[], value=None),  # resultado_selector
                            gr.update(visible=False),  # boton_ver_ficha_resultado
                            gr.update(visible=False),  # boton_guardar_de_todos_modos
                            None,  # id_resultado_exacta
                        )

                    categoria, exacta, posibles = coleccion.comprobar_tipo(
                        pais=datos["pais"],
                        valor_texto=datos["valor_texto"],
                        anio=datos["anio"],
                        ceca=datos["ceca"],
                        variante=datos["variante"],
                    )

                    if categoria == "exacta":
                        foto_e_a = (
                            str(imagenes.ruta_completa(exacta.foto_anverso))
                            if exacta.foto_anverso
                            else None
                        )
                        foto_e_r = (
                            str(imagenes.ruta_completa(exacta.foto_reverso))
                            if exacta.foto_reverso
                            else None
                        )
                        return (
                            gr.update(visible=False),
                            gr.update(visible=True),
                            gr.update(visible=False, value=""),
                            _texto_resultado_exacta(exacta),
                            gr.update(visible=True),
                            foto_e_a,
                            foto_e_r,
                            foto_anverso_img,
                            foto_reverso_img,
                            gr.update(visible=False, choices=[], value=None),
                            gr.update(visible=True),
                            gr.update(visible=False),
                            exacta.id,
                        )

                    if categoria == "parcial":
                        return (
                            gr.update(visible=False),
                            gr.update(visible=True),
                            gr.update(visible=False, value=""),
                            _texto_resultado_parcial(posibles),
                            gr.update(visible=False),
                            None,
                            None,
                            foto_anverso_img,
                            foto_reverso_img,
                            gr.update(
                                visible=True, choices=_opciones_selector(posibles), value=None
                            ),
                            gr.update(visible=False),
                            gr.update(visible=True),
                            None,
                        )

                    return (
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False, value=""),
                        _texto_resultado_ninguna(),
                        gr.update(visible=False),
                        None,
                        None,
                        foto_anverso_img,
                        foto_reverso_img,
                        gr.update(visible=False, choices=[], value=None),
                        gr.update(visible=False),
                        gr.update(visible=True),
                        None,
                    )

                def _guardar_desde_resultado(
                    pais,
                    valor_texto,
                    anio,
                    ceca,
                    variante,
                    notas,
                    estado,
                    foto_anverso_img,
                    foto_reverso_img,
                    foto_detalle_img,
                ):
                    """ "No la tienes" / "posible coincidencia" -> guardar de todos modos
                    (RF-5), reutilizando los mismos campos ya confirmados en el formulario."""
                    resultado = _guardar(
                        None,
                        pais,
                        valor_texto,
                        anio,
                        ceca,
                        variante,
                        notas,
                        estado,
                        foto_anverso_img,
                        foto_reverso_img,
                        foto_detalle_img,
                    )
                    return (*resultado, gr.update(visible=False))

                def _cancelar_formulario(id_edicion):
                    if id_edicion is not None:
                        return _abrir_ficha(id_edicion)
                    return (
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        None,
                    )

                def _volver_al_listado():
                    monedas = coleccion.listar()
                    return (
                        gr.update(visible=True),  # panel_lista
                        gr.update(visible=False),  # panel_captura
                        gr.update(visible=False),  # panel_formulario
                        gr.update(visible=False),  # panel_ficha
                        gr.update(visible=False),  # panel_confirmar_borrado
                        gr.update(visible=False),  # panel_resultado_comprobacion
                        _filas_tabla(monedas),
                        gr.update(choices=_opciones_selector(monedas), value=None),
                    )

                def _pedir_confirmacion_borrado():
                    return gr.update(visible=True)

                def _cancelar_borrado():
                    return gr.update(visible=False)

                def _confirmar_borrado(moneda_id):
                    if moneda_id is not None:
                        coleccion.borrar(int(moneda_id))
                    monedas = coleccion.listar()
                    return (
                        gr.update(visible=True),  # panel_lista
                        gr.update(visible=False),  # panel_captura
                        gr.update(visible=False),  # panel_formulario
                        gr.update(visible=False),  # panel_ficha
                        gr.update(visible=False),  # panel_confirmar_borrado
                        gr.update(visible=False),  # panel_resultado_comprobacion
                        _filas_tabla(monedas),
                        gr.update(choices=_opciones_selector(monedas), value=None),
                    )

                def _leer_con_ia(imagen_anverso, imagen_reverso, imagen_detalle, modo):
                    """Llama a CoinReader.leer() y abre el formulario prerrellenado
                    (RF-1 en modo "nueva", RF-2 en modo "comprobar").

                    La foto de detalle/macro NUNCA se envía a la IA (RF-8): es solo
                    apoyo humano para confirmar campos dudosos, y la foto "completa"
                    (anverso) es obligatoria para leer, así que un macro extremo no
                    puede colarse como única entrada de la lectura.
                    """
                    datos_anverso = _imagen_a_bytes(imagen_anverso)
                    if datos_anverso is None:
                        return (
                            gr.update(),  # panel_captura
                            gr.update(),  # panel_formulario
                            gr.update(),  # titulo_formulario
                            gr.update(),  # campo_pais
                            gr.update(),  # campo_valor
                            gr.update(),  # campo_anio
                            gr.update(),  # campo_ceca
                            gr.update(),  # campo_variante
                            gr.update(),  # campo_estado
                            gr.update(),  # campo_notas
                            gr.update(),  # campo_foto_anverso
                            gr.update(),  # campo_foto_reverso
                            gr.update(),  # campo_foto_detalle
                            gr.update(),  # aviso_formulario
                            gr.update(),  # id_en_edicion
                            gr.update(),  # boton_guardar
                            gr.update(),  # boton_comprobar_bd
                            gr.update(visible=True, value="⚠️ Sube al menos la foto del anverso."),
                        )

                    datos_reverso = _imagen_a_bytes(imagen_reverso)
                    lectura = ClaudeCoinReader().leer(datos_anverso, datos_reverso)
                    dudosos = lectura.campos_dudosos
                    boton_guardar_u, boton_comprobar_u = _botones_formulario_para_modo(modo)

                    return (
                        gr.update(visible=False),  # panel_captura
                        gr.update(visible=True),  # panel_formulario
                        _titulo_formulario_para_modo(modo, con_ia=True),
                        _campo_ia(lectura.pais, "pais", dudosos),
                        _campo_ia(lectura.valor, "valor", dudosos),
                        _campo_ia(
                            str(lectura.anio) if lectura.anio is not None else "",
                            "anio",
                            dudosos,
                        ),
                        _campo_ia(lectura.ceca, "ceca", dudosos),
                        _campo_ia(lectura.variante, "variante", dudosos),
                        modelo.EN_COLECCION,
                        "",
                        imagen_anverso,
                        imagen_reverso,
                        imagen_detalle,
                        gr.update(visible=True, value=_aviso_lectura_ia(lectura)),
                        None,  # id_en_edicion
                        boton_guardar_u,
                        boton_comprobar_u,
                        gr.update(visible=False, value=""),  # aviso_captura
                    )

                def _abrir_captura_manual(modo):
                    """Botón "rellenar a mano": formulario en blanco, sin pasar por la IA."""
                    # panel_ficha no está en _salidas_formulario_ia: ya está oculto y
                    # este flujo no lo toca, así que se descarta junto con panel_lista.
                    _, panel_formulario_u, _panel_ficha_u, *resto = _abrir_formulario_nuevo()
                    (
                        _titulo_en_blanco,
                        pais,
                        valor,
                        anio,
                        ceca,
                        variante,
                        estado,
                        notas,
                        foto_a,
                        foto_r,
                        foto_d,
                        aviso,
                        id_edicion,
                    ) = resto
                    boton_guardar_u, boton_comprobar_u = _botones_formulario_para_modo(modo)
                    return (
                        gr.update(visible=False),  # panel_captura
                        panel_formulario_u,
                        _titulo_formulario_para_modo(modo, con_ia=False),
                        pais,
                        valor,
                        anio,
                        ceca,
                        variante,
                        estado,
                        notas,
                        foto_a,
                        foto_r,
                        foto_d,
                        aviso,
                        id_edicion,
                        boton_guardar_u,
                        boton_comprobar_u,
                    )

                def _preparar_flujo(modo: str):
                    """Botones "Enseñar moneda nueva"/"¿La tengo?" de Inicio: abre la
                    captura para IA, o el formulario en blanco si no hay IA (RF-6). Se
                    ejecuta después de cambiar de pestaña (ver ``.then()`` más abajo): si
                    el cambio de panel va en la misma llamada que el cambio de pestaña,
                    Gradio a veces ignora la actualización a ``visible=False`` de un panel
                    que ya estaba visible en la pestaña de origen.
                    """
                    # Reutiliza el reseteo de campos de un formulario en blanco; solo
                    # cambian qué paneles quedan visibles y los textos según el modo.
                    _, _, _, _, pais, valor, anio, ceca, variante, estado, *resto = (
                        _abrir_formulario_nuevo()
                    )
                    notas, foto_a, foto_r, foto_d, aviso, id_edicion = resto
                    if config.hay_ia():
                        paneles = (
                            gr.update(visible=False),  # panel_lista
                            gr.update(visible=True),  # panel_captura
                            gr.update(visible=False),  # panel_formulario
                            gr.update(visible=False),  # panel_ficha
                        )
                    else:
                        paneles = (
                            gr.update(visible=False),  # panel_lista
                            gr.update(visible=False),  # panel_captura
                            gr.update(visible=True),  # panel_formulario
                            gr.update(visible=False),  # panel_ficha
                        )
                    boton_guardar_u, boton_comprobar_u = _botones_formulario_para_modo(modo)
                    return (
                        *paneles,
                        gr.update(visible=False),  # panel_resultado_comprobacion
                        _titulo_captura_para_modo(modo),
                        _instrucciones_captura_para_modo(modo),
                        _titulo_formulario_para_modo(modo, con_ia=False),
                        pais,
                        valor,
                        anio,
                        ceca,
                        variante,
                        estado,
                        notas,
                        foto_a,
                        foto_r,
                        foto_d,
                        aviso,
                        id_edicion,
                        modo,
                        boton_guardar_u,
                        boton_comprobar_u,
                    )

                def _preparar_enseñar():
                    return _preparar_flujo("nueva")

                def _preparar_comprobar():
                    return _preparar_flujo("comprobar")

                boton_buscar.click(
                    _buscar,
                    inputs=[filtro_texto, filtro_pais, filtro_valor, filtro_anio, filtro_estado],
                    outputs=[tabla, selector],
                )
                boton_limpiar.click(
                    _limpiar_filtros,
                    outputs=[
                        filtro_texto,
                        filtro_pais,
                        filtro_valor,
                        filtro_anio,
                        filtro_estado,
                        tabla,
                        selector,
                    ],
                )
                boton_exportar_csv.click(_exportar_csv, outputs=[boton_exportar_csv])
                boton_exportar_json.click(_exportar_json, outputs=[boton_exportar_json])
                boton_nueva.click(
                    _abrir_formulario_nuevo,
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        titulo_formulario,
                        campo_pais,
                        campo_valor,
                        campo_anio,
                        campo_ceca,
                        campo_variante,
                        campo_estado,
                        campo_notas,
                        campo_foto_anverso,
                        campo_foto_reverso,
                        campo_foto_detalle,
                        aviso_formulario,
                        id_en_edicion,
                    ],
                ).then(
                    lambda: ("nueva", *_botones_formulario_para_modo("nueva")),
                    outputs=[modo_flujo, boton_guardar, boton_comprobar_bd],
                )
                selector.change(
                    _abrir_ficha,
                    inputs=[selector],
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        ficha_titulo,
                        ficha_foto_anverso,
                        ficha_foto_reverso,
                        ficha_foto_detalle,
                        ficha_detalles,
                        id_ficha_actual,
                    ],
                )
                boton_editar.click(
                    _iniciar_edicion,
                    inputs=[id_ficha_actual],
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        titulo_formulario,
                        campo_pais,
                        campo_valor,
                        campo_anio,
                        campo_ceca,
                        campo_variante,
                        campo_estado,
                        campo_notas,
                        campo_foto_anverso,
                        campo_foto_reverso,
                        campo_foto_detalle,
                        aviso_formulario,
                        id_en_edicion,
                    ],
                ).then(
                    lambda: ("nueva", *_botones_formulario_para_modo("nueva")),
                    outputs=[modo_flujo, boton_guardar, boton_comprobar_bd],
                )
                boton_guardar.click(
                    _guardar,
                    inputs=[
                        id_en_edicion,
                        campo_pais,
                        campo_valor,
                        campo_anio,
                        campo_ceca,
                        campo_variante,
                        campo_notas,
                        campo_estado,
                        campo_foto_anverso,
                        campo_foto_reverso,
                        campo_foto_detalle,
                    ],
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        ficha_titulo,
                        ficha_foto_anverso,
                        ficha_foto_reverso,
                        ficha_foto_detalle,
                        ficha_detalles,
                        aviso_formulario,
                        id_ficha_actual,
                        id_en_edicion,
                    ],
                )
                boton_cancelar_formulario.click(
                    _cancelar_formulario,
                    inputs=[id_en_edicion],
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        ficha_titulo,
                        ficha_foto_anverso,
                        ficha_foto_reverso,
                        ficha_foto_detalle,
                        ficha_detalles,
                        id_ficha_actual,
                    ],
                )
                paneles_y_lista = [
                    panel_lista,
                    panel_captura,
                    panel_formulario,
                    panel_ficha,
                    panel_confirmar_borrado,
                    panel_resultado_comprobacion,
                    tabla,
                    selector,
                ]
                boton_volver.click(_volver_al_listado, outputs=paneles_y_lista)
                boton_borrar.click(_pedir_confirmacion_borrado, outputs=[panel_confirmar_borrado])
                boton_cancelar_borrado.click(_cancelar_borrado, outputs=[panel_confirmar_borrado])
                boton_confirmar_borrado.click(
                    _confirmar_borrado,
                    inputs=[id_ficha_actual],
                    outputs=paneles_y_lista,
                )

                _salidas_formulario_ia = [
                    panel_captura,
                    panel_formulario,
                    titulo_formulario,
                    campo_pais,
                    campo_valor,
                    campo_anio,
                    campo_ceca,
                    campo_variante,
                    campo_estado,
                    campo_notas,
                    campo_foto_anverso,
                    campo_foto_reverso,
                    campo_foto_detalle,
                    aviso_formulario,
                    id_en_edicion,
                    boton_guardar,
                    boton_comprobar_bd,
                ]
                boton_leer_ia.click(
                    _leer_con_ia,
                    inputs=[captura_anverso, captura_reverso, captura_detalle, modo_flujo],
                    outputs=[*_salidas_formulario_ia, aviso_captura],
                )
                boton_manual_en_vez.click(
                    _abrir_captura_manual,
                    inputs=[modo_flujo],
                    outputs=_salidas_formulario_ia,
                )
                boton_cancelar_captura.click(
                    _volver_al_listado,
                    outputs=paneles_y_lista,
                )

                _salidas_resultado_comprobacion = [
                    panel_formulario,
                    panel_resultado_comprobacion,
                    aviso_formulario,
                    resultado_texto,
                    resultado_fotos_comparacion,
                    resultado_foto_existente_anverso,
                    resultado_foto_existente_reverso,
                    resultado_foto_capturada_anverso,
                    resultado_foto_capturada_reverso,
                    resultado_selector,
                    boton_ver_ficha_resultado,
                    boton_guardar_de_todos_modos,
                    id_resultado_exacta,
                ]
                boton_comprobar_bd.click(
                    _comprobar,
                    inputs=[
                        campo_pais,
                        campo_valor,
                        campo_anio,
                        campo_ceca,
                        campo_variante,
                        campo_foto_anverso,
                        campo_foto_reverso,
                    ],
                    outputs=_salidas_resultado_comprobacion,
                )

                _salidas_ficha_desde_resultado = [
                    panel_lista,
                    panel_formulario,
                    panel_ficha,
                    ficha_titulo,
                    ficha_foto_anverso,
                    ficha_foto_reverso,
                    ficha_foto_detalle,
                    ficha_detalles,
                    id_ficha_actual,
                ]
                boton_ver_ficha_resultado.click(
                    _abrir_ficha,
                    inputs=[id_resultado_exacta],
                    outputs=_salidas_ficha_desde_resultado,
                ).then(
                    lambda: gr.update(visible=False),
                    outputs=[panel_resultado_comprobacion],
                )

                def _ver_ficha_desde_resultado(moneda_id):
                    # ``_comprobar`` fuerza el desplegable a ``value=None`` al
                    # mostrar/ocultar resultados, y eso también dispara este
                    # ``.change`` (Gradio lo hace en cualquier gr.update con
                    # ``value``, no solo en una selección real del humano). Sin
                    # este no-op, ese reseteo interno ocultaría el propio panel
                    # de resultado que acabamos de mostrar.
                    if moneda_id is None:
                        return (gr.update(),) * len(_salidas_ficha_desde_resultado)
                    return _abrir_ficha(moneda_id)

                resultado_selector.change(
                    _ver_ficha_desde_resultado,
                    inputs=[resultado_selector],
                    outputs=_salidas_ficha_desde_resultado,
                ).then(
                    lambda moneda_id: (
                        gr.update(visible=False) if moneda_id is not None else gr.update()
                    ),
                    inputs=[resultado_selector],
                    outputs=[panel_resultado_comprobacion],
                )
                boton_guardar_de_todos_modos.click(
                    _guardar_desde_resultado,
                    inputs=[
                        campo_pais,
                        campo_valor,
                        campo_anio,
                        campo_ceca,
                        campo_variante,
                        campo_notas,
                        campo_estado,
                        campo_foto_anverso,
                        campo_foto_reverso,
                        campo_foto_detalle,
                    ],
                    outputs=[
                        panel_lista,
                        panel_formulario,
                        panel_ficha,
                        ficha_titulo,
                        ficha_foto_anverso,
                        ficha_foto_reverso,
                        ficha_foto_detalle,
                        ficha_detalles,
                        aviso_formulario,
                        id_ficha_actual,
                        id_en_edicion,
                        panel_resultado_comprobacion,
                    ],
                )
                boton_volver_resultado.click(_volver_al_listado, outputs=paneles_y_lista)

        _salidas_preparar_flujo = [
            panel_lista,
            panel_captura,
            panel_formulario,
            panel_ficha,
            panel_resultado_comprobacion,
            titulo_captura,
            instrucciones_captura,
            titulo_formulario,
            campo_pais,
            campo_valor,
            campo_anio,
            campo_ceca,
            campo_variante,
            campo_estado,
            campo_notas,
            campo_foto_anverso,
            campo_foto_reverso,
            campo_foto_detalle,
            aviso_formulario,
            id_en_edicion,
            modo_flujo,
            boton_guardar,
            boton_comprobar_bd,
        ]

        # Dos pasos encadenados a propósito: cambiar de pestaña y ocultar/mostrar
        # paneles en la misma llamada hace que Gradio ignore a veces el cambio a
        # visible=False de un panel de la pestaña de origen (visto en pruebas
        # manuales). Separarlo en un .then() evita esa condición de carrera.
        boton_ir_enseñar.click(
            lambda: gr.Tabs(selected="coleccion"),
            outputs=[pestañas],
        ).then(
            _preparar_enseñar,
            outputs=_salidas_preparar_flujo,
        )
        boton_ir_comprobar.click(
            lambda: gr.Tabs(selected="coleccion"),
            outputs=[pestañas],
        ).then(
            _preparar_comprobar,
            outputs=_salidas_preparar_flujo,
        )

    return app


def lanzar() -> None:
    """Arranca el servidor Gradio en la red local (escritorio + móvil por wifi)."""
    config.asegurar_directorios()
    construir().launch(server_name="0.0.0.0", server_port=config.PUERTO, css=_CSS)
