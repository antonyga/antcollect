"""Interfaz Gradio de AntCollect.

Fase 1: catálogo manual completo (RF-6, RF-9, RF-10, RF-11, RF-12) sin IA
todavía. Los flujos "Enseñar moneda nueva" (RF-1) y "¿La tengo?" (RF-2) se
conectan en fases posteriores reutilizando este mismo formulario.
"""

from __future__ import annotations

import gradio as gr

from .. import coleccion, config, imagenes, modelo
from ..coleccion import TipoDuplicadoError
from ..modelo import Moneda

_AVISO_SIN_IA = (
    "ℹ️ No hay `ANTHROPIC_API_KEY` configurada: la lectura por IA estará "
    "desactivada. El modo manual funciona sin conexión."
)

_ESTADOS_ETIQUETAS = [
    ("En colección", modelo.EN_COLECCION),
    ("Duplicada", modelo.DUPLICADA),
    ("Para intercambio", modelo.PARA_INTERCAMBIO),
]

_ENCABEZADOS_TABLA = ["id", "País", "Valor", "Año", "Ceca", "Variante", "Estado"]


def _fila_tabla(m: Moneda) -> list:
    return [
        m.id,
        m.pais,
        m.valor_texto,
        m.anio if m.anio is not None else "",
        m.ceca or "",
        m.variante or "",
        m.estado,
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


def _datos_ficha(m: Moneda) -> tuple[str, str | None, str | None, str]:
    titulo = f"### {m.pais} — {m.valor_texto}"
    detalles = (
        f"- **Año:** {m.anio if m.anio is not None else 'desconocido'}\n"
        f"- **Ceca:** {m.ceca or '—'}\n"
        f"- **Variante:** {m.variante or '—'}\n"
        f"- **Estado:** {dict((v, k) for k, v in _ESTADOS_ETIQUETAS).get(m.estado, m.estado)}\n"
        f"- **Notas:** {m.notas or '—'}\n"
        f"- **Añadida el:** {m.fecha_agregada}\n"
    )
    foto_anverso = str(imagenes.ruta_completa(m.foto_anverso)) if m.foto_anverso else None
    foto_reverso = str(imagenes.ruta_completa(m.foto_reverso)) if m.foto_reverso else None
    return titulo, foto_anverso, foto_reverso, detalles


def _texto_duplicado(existente: Moneda) -> str:
    return (
        "⚠️ **Ya existe un tipo igual** (mismos país, valor, año, ceca y variante): "
        f"{_etiqueta_moneda(existente)}.\n\n"
        "Si es una variante distinta, rellena el campo **Variante** para diferenciarla. "
        "Si no, cancela: puede que ya la tengas catalogada."
    )


def _guardar_fotos(
    moneda_id: int,
    foto_anverso_img,
    foto_reverso_img,
    anterior: Moneda | None,
) -> None:
    """Guarda/borra fotos según lo que haya en el formulario, comparado con lo anterior."""
    cambios: dict[str, str | None] = {}

    if foto_anverso_img is not None:
        cambios["foto_anverso"] = imagenes.guardar_imagen(foto_anverso_img, moneda_id, "anverso")
    elif anterior is not None and anterior.foto_anverso:
        imagenes.ruta_completa(anterior.foto_anverso).unlink(missing_ok=True)
        cambios["foto_anverso"] = None

    if foto_reverso_img is not None:
        cambios["foto_reverso"] = imagenes.guardar_imagen(foto_reverso_img, moneda_id, "reverso")
    elif anterior is not None and anterior.foto_reverso:
        imagenes.ruta_completa(anterior.foto_reverso).unlink(missing_ok=True)
        cambios["foto_reverso"] = None

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

        with gr.Tab("🏠 Inicio"):
            with gr.Row(equal_height=True):
                gr.Button("📖  Enseñar moneda nueva", variant="primary", size="lg")
                gr.Button("🔎  ¿La tengo?", variant="secondary", size="lg")
            if not config.hay_ia():
                gr.Markdown(_AVISO_SIN_IA)

        with gr.Tab("📚 Colección"):
            id_ficha_actual = gr.State(None)
            id_en_edicion = gr.State(None)

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
                with gr.Row():
                    boton_buscar = gr.Button("🔍 Buscar")
                    boton_limpiar = gr.Button("Limpiar filtros")
                    boton_nueva = gr.Button("➕ Añadir moneda", variant="primary")
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

            with gr.Group(visible=False) as panel_formulario:
                titulo_formulario = gr.Markdown("### Nueva moneda")
                with gr.Row():
                    campo_pais = gr.Textbox(label="País *")
                    campo_valor = gr.Textbox(label="Valor *", placeholder="p. ej. 2 euros")
                    campo_anio = gr.Textbox(
                        label="Año (vacío si es ilegible)", placeholder="p. ej. 2002"
                    )
                with gr.Row():
                    campo_ceca = gr.Textbox(label="Ceca")
                    campo_variante = gr.Textbox(label="Variante")
                    campo_estado = gr.Dropdown(
                        label="Estado",
                        choices=_ESTADOS_ETIQUETAS,
                        value=modelo.EN_COLECCION,
                    )
                campo_notas = gr.Textbox(label="Notas", lines=3)
                with gr.Row():
                    campo_foto_anverso = gr.Image(label="Foto anverso", type="pil")
                    campo_foto_reverso = gr.Image(label="Foto reverso", type="pil")
                aviso_formulario = gr.Markdown(visible=False)
                with gr.Row():
                    boton_guardar = gr.Button("💾 Guardar", variant="primary")
                    boton_cancelar_formulario = gr.Button("Cancelar")

            with gr.Group(visible=False) as panel_ficha:
                ficha_titulo = gr.Markdown()
                with gr.Row():
                    ficha_foto_anverso = gr.Image(label="Anverso", interactive=False)
                    ficha_foto_reverso = gr.Image(label="Reverso", interactive=False)
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

            def _buscar(texto, pais, valor, anio):
                anio_texto = (anio or "").strip()
                anio_filtro = int(anio_texto) if anio_texto.isdigit() else None
                monedas = coleccion.listar(
                    texto=texto or None, pais=pais or None, valor=valor or None, anio=anio_filtro
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
                    _filas_tabla(monedas),
                    gr.update(choices=_opciones_selector(monedas), value=None),
                )

            def _abrir_formulario_nuevo():
                return (
                    gr.update(visible=False),  # panel_lista
                    gr.update(visible=True),  # panel_formulario
                    gr.update(visible=False),  # panel_ficha
                    "### Nueva moneda",
                    "",
                    "",
                    "",
                    "",
                    "",
                    modelo.EN_COLECCION,
                    "",
                    None,
                    None,
                    gr.update(visible=False, value=""),
                    None,  # id_en_edicion
                )

            def _abrir_ficha(moneda_id):
                if moneda_id is None:
                    return (gr.update(),) * 7 + (None,)
                m = coleccion.obtener(int(moneda_id))
                if m is None:
                    return (gr.update(),) * 7 + (None,)
                titulo, foto_a, foto_r, detalles = _datos_ficha(m)
                return (
                    gr.update(visible=False),  # panel_lista
                    gr.update(visible=False),  # panel_formulario
                    gr.update(visible=True),  # panel_ficha
                    titulo,
                    foto_a,
                    foto_r,
                    detalles,
                    m.id,
                )

            def _iniciar_edicion(moneda_id):
                m = coleccion.obtener(moneda_id) if moneda_id is not None else None
                if m is None:
                    return (gr.update(),) * 15
                foto_a = str(imagenes.ruta_completa(m.foto_anverso)) if m.foto_anverso else None
                foto_r = str(imagenes.ruta_completa(m.foto_reverso)) if m.foto_reverso else None
                return (
                    gr.update(visible=False),  # panel_lista
                    gr.update(visible=True),  # panel_formulario
                    gr.update(visible=False),  # panel_ficha
                    f"### Editar: {m.pais} — {m.valor_texto}",
                    m.pais,
                    m.valor_texto,
                    str(m.anio) if m.anio is not None else "",
                    m.ceca or "",
                    m.variante or "",
                    m.estado,
                    m.notas or "",
                    foto_a,
                    foto_r,
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
            ):
                pais = (pais or "").strip()
                valor_texto = (valor_texto or "").strip()
                anio_texto = (anio or "").strip()
                error = None
                if not pais or not valor_texto:
                    error = "⚠️ País y valor son obligatorios."
                elif anio_texto and not anio_texto.isdigit():
                    error = "⚠️ El año debe ser un número (déjalo vacío si es ilegible)."
                if error:
                    aviso = gr.update(visible=True, value=error)
                    return (
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        aviso,
                        gr.update(),
                        gr.update(),
                    )

                anio_valor = int(anio_texto) if anio_texto else None
                ceca = (ceca or "").strip() or None
                variante = (variante or "").strip() or None
                notas = (notas or "").strip() or None

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
                        _guardar_fotos(moneda.id, foto_anverso_img, foto_reverso_img, None)
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
                        _guardar_fotos(moneda.id, foto_anverso_img, foto_reverso_img, anterior)
                except TipoDuplicadoError as exc:
                    aviso = gr.update(visible=True, value=_texto_duplicado(exc.existente))
                    return (
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        aviso,
                        gr.update(),
                        gr.update(),
                    )

                moneda = coleccion.obtener(moneda.id)
                titulo, foto_a, foto_r, detalles = _datos_ficha(moneda)
                return (
                    gr.update(visible=False),  # panel_lista
                    gr.update(visible=False),  # panel_formulario
                    gr.update(visible=True),  # panel_ficha
                    titulo,
                    foto_a,
                    foto_r,
                    detalles,
                    gr.update(visible=False, value=""),
                    moneda.id,
                    None,  # id_en_edicion se limpia
                )

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
                    None,
                )

            def _volver_al_listado():
                monedas = coleccion.listar()
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
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
                    gr.update(visible=False),  # panel_formulario
                    gr.update(visible=False),  # panel_ficha
                    gr.update(visible=False),  # panel_confirmar_borrado
                    _filas_tabla(monedas),
                    gr.update(choices=_opciones_selector(monedas), value=None),
                )

            boton_buscar.click(
                _buscar,
                inputs=[filtro_texto, filtro_pais, filtro_valor, filtro_anio],
                outputs=[tabla, selector],
            )
            boton_limpiar.click(
                _limpiar_filtros,
                outputs=[filtro_texto, filtro_pais, filtro_valor, filtro_anio, tabla, selector],
            )
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
                    aviso_formulario,
                    id_en_edicion,
                ],
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
                    aviso_formulario,
                    id_en_edicion,
                ],
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
                ],
                outputs=[
                    panel_lista,
                    panel_formulario,
                    panel_ficha,
                    ficha_titulo,
                    ficha_foto_anverso,
                    ficha_foto_reverso,
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
                    ficha_detalles,
                    id_ficha_actual,
                ],
            )
            paneles_y_lista = [
                panel_lista,
                panel_formulario,
                panel_ficha,
                panel_confirmar_borrado,
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

    return app


def lanzar() -> None:
    """Arranca el servidor Gradio en la red local (escritorio + móvil por wifi)."""
    config.asegurar_directorios()
    construir().launch(server_name="0.0.0.0", server_port=config.PUERTO)
