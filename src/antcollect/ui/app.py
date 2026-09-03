"""Interfaz Gradio de AntCollect.

Fase 0: solo la pantalla de inicio con los dos botones grandes. Los flujos
"Enseñar moneda nueva" (RF-1) y "¿La tengo?" (RF-2) se conectan en fases
posteriores.
"""

from __future__ import annotations

import gradio as gr

from .. import config

_AVISO_SIN_IA = (
    "ℹ️ No hay `ANTHROPIC_API_KEY` configurada: la lectura por IA estará "
    "desactivada. El modo manual funciona sin conexión."
)


def construir() -> gr.Blocks:
    """Construye la app Gradio."""
    with gr.Blocks(title="AntCollect") as app:
        gr.Markdown(
            "# AntCollect\n"
            "**La máquina propone, el humano dispone.** La IA solo sugiere los "
            "campos leídos de la foto; tú los confirmas antes de guardar nada."
        )
        with gr.Row(equal_height=True):
            gr.Button("📖  Enseñar moneda nueva", variant="primary", size="lg")
            gr.Button("🔎  ¿La tengo?", variant="secondary", size="lg")

        if not config.hay_ia():
            gr.Markdown(_AVISO_SIN_IA)

    return app


def lanzar() -> None:
    """Arranca el servidor Gradio en la red local (escritorio + móvil por wifi)."""
    config.asegurar_directorios()
    construir().launch(server_name="0.0.0.0", server_port=config.PUERTO)
