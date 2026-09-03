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

En construcción — Fase 0 (esqueleto) completada; **Fase 1 (CRUD manual)** en curso. Ver [PLAN.md](PLAN.md).

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
Para conocer la IP del PC: `ipconfig` (Windows).

## Copia de seguridad

Toda la información vive en dos sitios dentro de la carpeta del proyecto:

- `antcollect.db` — la base de datos
- `imagenes/` — las fotos

Respaldar = copiar esos dos a lugar seguro. Restaurar = volver a copiarlos.
Ninguno de los dos se sube a git.

## Desarrollo

```bash
uv run ruff check .        # lint
uv run ruff format .       # formatear
uv run pytest              # tests
```

Flujo de versiones: rama por fase + Pull Request a `main`, Conventional Commits.
Detalle en [CLAUDE.md](CLAUDE.md#8-flujo-de-trabajo-git--github-control-de-versiones-profesional).
