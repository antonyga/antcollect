# AntCollect

App web local, de un solo usuario, para catalogar una colección de monedas y
responder con fiabilidad a: *"me he encontrado esta moneda, ¿ya la tengo?"*.

La comprobación no compara imágenes: es una **consulta exacta** sobre los campos
normalizados que definen el *tipo* de moneda (`pais` + `valor` + `anio` + `ceca`
+ `variante`). La IA de visión solo **propone** los campos leídos de la foto; el
usuario los **confirma o corrige** antes de que nada se guarde.

- Especificación completa: [Docs/AntCollect-Arquitectura-y-Requisitos.md](Docs/AntCollect-Arquitectura-y-Requisitos.md)
- Instrucciones de desarrollo: [CLAUDE.md](CLAUDE.md)
- Plan de fases y estado: [PLAN.md](PLAN.md)

## Estado

Fases 0 a 4 completadas (esqueleto, CRUD manual, lectura por IA, comprobar
"¿la tengo?", captura y modos). **Fase 5 (pulido)** en curso. Ver [PLAN.md](PLAN.md).

## Stack

| Pieza | Elección |
|---|---|
| Lenguaje | Python 3.11 (gestionado con [uv](https://docs.astral.sh/uv/)) |
| UI | Gradio |
| Base de datos | SQLite de archivo (`antcollect.db`), sin ORM ni servidor |
| Imágenes | Pillow para redimensionar; carpeta local `imagenes/` |
| Lectura IA | SDK `anthropic`, detrás de la interfaz `CoinReader` (intercambiable) |

## Decisiones de diseño

- **UI: Gradio.** Subida de imagen, webcam, selección de fuente de cámara
  (microscopio USB) y formularios con poco código; buen comportamiento en móvil.
- **Unicidad `NULL` vs `''`:** `ceca` y `variante` vacías se guardan como `''`
  (cuentan como un único valor). `anio` desconocido se guarda como `NULL` real y
  nunca produce un "ya la tienes": se muestra como *posible coincidencia*.
- **Modelo IA por defecto:** `claude-sonnet-5` (configurable en `.env`).

## Instalación

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.11.

```bash
uv sync
cp .env.example .env      # y rellena ANTHROPIC_API_KEY
```

> El proyecto fija `system-certs = true` en `pyproject.toml` para funcionar tras
> un proxy TLS corporativo. Si `uv` da un error de certificado igualmente, usa
> `uv sync --system-certs`.

La clave de API solo hace falta para la lectura por IA. Catalogar, consultar,
editar, listar y buscar funcionan sin conexión.

## Arrancar

```bash
uv run python -m antcollect
```

Abre `http://localhost:7860` en el navegador del escritorio.

### Desde el móvil

Con el PC encendido y sirviendo, en la misma red wifi, abre en el navegador del
móvil `http://<IP-local-del-PC>:7860` (p. ej. `http://192.168.1.42:7860`).
Para conocer la IP del PC: `ipconfig` (Windows). La UI se adapta a pantallas
estrechas (botones y campos más grandes, cámara trasera por defecto en el móvil).

## Uso

Dos flujos desde la pestaña **Inicio**, ambos con el mismo pipeline
*capturar → leer → confirmar*:

- **📖 Enseñar moneda nueva** — para catalogar una moneda que no tienes fichada.
  Termina **guardando** en la colección tras tu confirmación.
- **🔎 ¿La tengo?** — para comprobar si una moneda que te has encontrado ya está
  en tu colección. Termina **consultando**: coincidencia exacta, posible
  coincidencia (revisa tú los detalles) o "no la tienes" con opción de guardarla.

En la captura puedes subir foto, usar la webcam (con selector de fuente si hay
varias, útil con un microscopio USB para cecas/variantes) o el campo opcional
de *detalle/macro* como apoyo visual — nunca se envía a la IA, solo la foto
completa de anverso/reverso.

La IA solo **propone** los campos; tú los confirmas o corriges antes de que se
guarde nada. Los campos que no pudo leer con seguridad quedan resaltados. Sin
`ANTHROPIC_API_KEY` configurada, o si la lectura falla, la app pasa
automáticamente al formulario en blanco (modo manual) sin interrumpir el flujo.

### Estados de la colección

Cada moneda tiene un estado editable: **en colección**, **duplicada** o **para
intercambio**. Se fija al guardar/editar y se puede filtrar desde el listado.

### Exportar la colección

Desde el listado, los botones **Exportar CSV** y **Exportar JSON** generan un
volcado de los campos "bonitos" de la colección (sin las columnas internas
`*_norm`). Nota de uso: el botón de Gradio necesita **dos clics** — el primero
genera el archivo (la etiqueta cambia a "pulsa para descargar"), el segundo
dispara la descarga del navegador.

Esto es un export puntual y legible, no sustituye a la copia de seguridad real
(ver siguiente sección).

## Copia de seguridad

Toda la información vive en dos sitios dentro de la carpeta del proyecto:

- `antcollect.db` — la base de datos
- `imagenes/` — las fotos

Respaldar = copiar esos dos a lugar seguro. Restaurar = cerrar la app y volver
a copiarlos a su sitio (sobrescribiendo). Ninguno de los dos se sube a git.

## Desarrollo

```bash
uv run ruff check .        # lint
uv run ruff format .       # formatear
uv run pytest              # tests
```

Flujo de versiones: rama por fase + Pull Request a `main`, Conventional Commits.
Detalle en [CLAUDE.md](CLAUDE.md#8-flujo-de-trabajo-git--github-control-de-versiones-profesional).
