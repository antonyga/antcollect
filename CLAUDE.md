# CLAUDE.md — Instrucciones para trabajar en AntCollect

> Este archivo lo lee Claude Code al empezar cada sesión. Es la fuente de verdad
> operativa del proyecto. La especificación completa está en
> [Docs/AntCollect-Arquitectura-y-Requisitos.md](Docs/AntCollect-Arquitectura-y-Requisitos.md);
> el plan de fases en [PLAN.md](PLAN.md). Si algo aquí contradice al doc de
> arquitectura, gana el doc de arquitectura salvo que el usuario diga lo contrario.

---

## 1. Qué es AntCollect

App web local, **de un solo usuario**, para catalogar una colección de monedas y
responder con fiabilidad a: *"me he encontrado esta moneda, ¿ya la tengo?"*.

La respuesta NO se basa en comparar imágenes. Se basa en una **consulta exacta**
sobre campos normalizados que definen "el tipo":

    pais + valor + anio + ceca + variante

Dos monedas son "el mismo tipo" si esos cinco campos normalizados coinciden.

Hay dos flujos, que son **el mismo flujo** con distinto final:

| Flujo | Pasos | Final |
|---|---|---|
| Enseñar moneda nueva (RF-1) | capturar → leer → confirmar | **guardar** en la BD |
| Comprobar moneda encontrada (RF-2) | capturar → leer → confirmar | **consultar** la BD |

Implementarlos como un pipeline compartido. No duplicar código entre ambos.

---

## 2. Principio rector (no negociable)

**La máquina propone, el humano dispone.**

- La IA SOLO rellena un formulario editable. Nunca escribe en la BD, nunca decide.
- Ningún registro se crea ni modifica sin un paso explícito de confirmación humana
  sobre los campos (RF-3).
- Los campos que la IA no leyó con seguridad (`campos_dudosos`) se **resaltan** en
  la UI para que el humano los revise.
- El lenguaje de la UI es de **propuesta**, no de resultado definitivo:
  "campos propuestos", "revisa el año", nunca "resultado" ni "identificado".

Todo el diseño existe para evitar una colección contaminada con años o cecas mal
leídos. Ante la duda, forzar revisión humana.

---

## 3. Reglas de arquitectura que NO se rompen

- **RNF-5 / clave de API fuera de git.** `ANTHROPIC_API_KEY` se lee de `.env`
  (via `python-dotenv`) o entorno. Nunca hardcodeada, nunca commiteada.
  `.env` e `/imagenes/` están en `.gitignore`; mantenerlos ahí.
- **RNF-6 / IA desacoplada.** Toda la lógica de lectura vive detrás de la
  interfaz `CoinReader` (clase abstracta). El resto del código NO importa el SDK
  de Anthropic directamente. Cambiar de proveedor = añadir un adaptador.
- **RNF-2 / datos locales y portables.** SQLite de archivo (`antcollect.db`) +
  carpeta `imagenes/`. Sin servidor de BD. Backup = copiar esos dos.
- **RNF-3 / offline salvo lectura IA.** Catalogar, consultar, editar, listar y
  buscar funcionan SIN red. Solo `CoinReader.leer()` necesita internet, y si falla
  la app informa y ofrece el modo manual (RF-6). Nunca peta.
- **RNF-7 / robustez de datos.** Las escrituras a BD son transaccionales y
  SIEMPRE posteriores a la confirmación humana. Un fallo de IA o de red jamás
  corrompe la BD.
- **RNF-4 / coste controlado.** Redimensionar imágenes con Pillow ANTES de
  enviarlas a la IA (lado largo ~1568 px máx). Solo llamar a la IA cuando el
  usuario lo pide explícitamente. Loguear coste/errores en `antcollect.log`.
- **RNF-8 / simplicidad.** App de un usuario. Nada de colas, microservicios,
  ORM pesados, autenticación ni multiusuario. Si dudas, elige la opción simple.

---

## 4. Decisiones tomadas (registrar cambios aquí y en el README)

| Tema | Decisión | Motivo |
|---|---|---|
| Framework UI | **Gradio** | Subida de imagen + webcam + selección de fuente de cámara (microscopio) con poco código; buen soporte móvil. Migrar a FastAPI solo si la UI se queda corta. |
| `NULL` vs `''` en unicidad | `ceca` y `variante`: normalizar `NULL` → `''` antes de guardar y consultar. `anio`: se queda **`NULL` real** (año ilegible ≠ año 0). | Que el `UNIQUE INDEX` funcione de verdad (SQLite trata cada `NULL` como distinto). Un `anio` nulo nunca da "ya la tienes": se trata como "posible coincidencia". |
| Modelo IA por defecto | `claude-sonnet-5`, en configuración (no hardcodeado). **Confirmar el id de modelo vigente en https://docs.claude.com antes de codificar la Fase 2.** Alternativa barata: un Haiku actual. | Equilibrio lectura de detalle / coste. |
| Salida estructurada IA | **tool use** con un esquema de herramienta = campos del tipo + `campos_dudosos`. | Más robusto que pedir JSON en texto libre y parsear a mano. |
| Idioma del código | Dominio en **español** (`pais`, `valor`, `anio`, `ceca`, `variante`, `Moneda`, `CoinReader.leer`, `LecturaMoneda`). Comentarios técnicos e infra en inglés. | Coherencia con toda la documentación del proyecto. |
| Gestor de entorno | **uv** con **Python 3.11**. | Ya instalado; rápido y reproducible. |
| Idioma de la UI y los textos visibles | Español. | El usuario es hispanohablante; la app es personal. |

---

## 5. Stack y estructura del proyecto

- **Lenguaje:** Python 3.11, gestionado con `uv` (`pyproject.toml` + `uv.lock`).
- **UI:** Gradio.
- **BD:** SQLite via el módulo estándar `sqlite3` (o una capa fina propia). Sin ORM.
- **Imágenes:** Pillow para redimensionar/normalizar.
- **IA:** SDK oficial `anthropic`, SOLO dentro del adaptador de `CoinReader`.
- **Config:** `python-dotenv`, `.env` fuera de git, `.env.example` versionado.
- **Calidad:** `ruff` (lint + format), `pytest` para tests.

Estructura prevista (crear según avanzan las fases, no toda de golpe):

```
antcollect/
├── CLAUDE.md                # este archivo
├── PLAN.md                  # plan de fases y estado
├── README.md                # instalar, configurar, arrancar, móvil, backup
├── pyproject.toml
├── .env.example             # ANTHROPIC_API_KEY=..., ANTCOLLECT_MODELO=claude-sonnet-5
├── .gitignore
├── Docs/
│   └── AntCollect-Arquitectura-y-Requisitos.md
├── src/antcollect/
│   ├── __init__.py
│   ├── config.py            # carga .env, rutas, modelo, tamaños
│   ├── db.py                # conexión SQLite, migraciones/esquema, transacciones
│   ├── modelo.py            # dataclasses: Moneda, LecturaMoneda
│   ├── normalizacion.py     # minúsculas, sin acentos, espacios, NULL→'' , valor canónico
│   ├── coleccion.py         # servicio: alta, edición, borrado, búsqueda, duplicados, ¿la tengo?
│   ├── imagenes.py          # guardar/redimensionar, nombres derivados del id
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── base.py          # CoinReader (ABC) + LecturaMoneda contract
│   │   └── claude.py        # ClaudeCoinReader: adaptador API Anthropic + tool use
│   └── ui/
│       └── app.py           # Gradio: pantalla inicio (2 botones), flujos, listado, ficha
├── tests/
├── antcollect.db            # (generado, ignorado por git)
└── imagenes/                # (generado, ignorado por git)
```

---

## 6. Modelo de datos (resumen; detalle en §7 del doc de arquitectura)

Tabla `monedas` con columnas "bonitas" para mostrar (`pais`, `valor_texto`,
`anio`, `ceca`, `variante`, `notas`, `estado`, `foto_anverso`, `foto_reverso`,
`fecha_agregada`) + columnas normalizadas para comparar (`pais_norm`,
`valor_norm`, `ceca_norm`, `variante_norm`).

```sql
CREATE UNIQUE INDEX idx_tipo
    ON monedas (pais_norm, valor_norm, anio, ceca_norm, variante_norm);
```

- `estado` por defecto `'en_coleccion'`. Otros: `'duplicada'`, `'para_intercambio'`.
- Imágenes: nombres derivados del `id` (`0001_anverso.jpg`) para trazabilidad.
- La **detección de duplicados (RF-14)** compara columnas normalizadas, nunca texto crudo.
- Consulta "¿la tengo?" (RF-2):
  - Coincidencia exacta en los 5 campos → "✅ Ya la tienes" + ficha con foto al
    lado de la recién capturada (RF-4).
  - Sin coincidencia → "🆕 No la tienes" + botón "Guardar esta" que reutiliza los
    campos ya leídos (RF-5).
  - Mismo pais+valor+anio pero distinta ceca/variante, o algún campo dudoso, o
    `anio` nulo → **"posible coincidencia"**, decide el humano. Este caso importa:
    es el corazón del "fíjate en los detalles".

---

## 7. Contrato de `CoinReader`

```python
class CoinReader(ABC):
    @abstractmethod
    def leer(self, imagen_anverso: bytes, imagen_reverso: bytes | None = None) -> LecturaMoneda: ...

@dataclass
class LecturaMoneda:
    pais: str | None
    valor: str | None
    anio: int | None
    ceca: str | None
    variante: str | None
    campos_dudosos: list[str]   # nombres de campos que la IA no pudo leer con seguridad
```

Reglas del adaptador Claude (Fase 2):
- Imágenes como bloque base64, **antes** del texto en el mensaje.
- Redimensionar con Pillow antes de enviar (lado largo ~1568 px).
- `tool use` con esquema = los 5 campos + `campos_dudosos`.
- El prompt de sistema pide: extraer **solo** lo que se ve; **no inventar**; si un
  campo no es legible → `null` + añadirlo a `campos_dudosos`; año como número de
  4 cifras o `null`; usar anverso y reverso de forma complementaria.
- Errores (sin red / timeout / API / respuesta no parseable) → lectura fallida,
  la UI informa y pasa a modo manual. La app no lanza excepción al usuario.

---

## 8. Flujo de trabajo Git / GitHub (control de versiones profesional)

- **Repo:** `https://github.com/antonyga/antcollect` (público).
- **Rama principal:** `main`, protegida. No se commitea directo a `main`.
- **Una rama por fase:** `feat/fase-0-esqueleto`, `feat/fase-1-crud`, etc.
  Para trabajo suelto: `fix/...`, `docs/...`, `chore/...`, `refactor/...`.
- **Pull Request por fase.** Descripción del PR: qué RF/RNF cubre, cómo probarlo,
  decisiones tomadas. Merge (squash o merge commit) al terminar y validar la fase.
- **Conventional Commits** en español, imperativo, minúscula:
  - `feat: añade normalización de campos del tipo`
  - `fix: evita falso positivo de "ya la tienes" con anio NULL`
  - `docs: documenta política NULL vs '' en el README`
  - `chore: configura ruff y pytest`
  - Cuerpo del commit: el porqué, no el qué. Referenciar `RF-n` / `RNF-n` cuando aplique.
- **Commits pequeños y atómicos.** Uno por idea. Que cada commit deje el árbol
  en verde (lint + tests pasan).
- **Nunca** commitear: `.env`, `*.db`, `/imagenes/`, `*.log`, claves.
  Si algo secreto entra al índice por error, PARAR y avisar al usuario antes de
  hacer push.
- **Antes de cada commit:** `uv run ruff check . && uv run ruff format --check . && uv run pytest`.
- **No hacer `push` ni `merge` a `main` sin pedirlo al usuario.** Crear el commit
  local sí; publicar es decisión suya.
- Co-autoría en commits hechos por Claude:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

**Estado actual de auth:** `gh` CLI aún no autenticado. El usuario debe ejecutar
`gh auth login` una vez. La creación del repo remoto y el primer push quedan
pendientes de eso.

---

## 9. Comandos habituales

```bash
uv sync                       # instalar/actualizar dependencias
uv run python -m antcollect    # arrancar la app (cuando exista el entrypoint)
uv run ruff check .            # lint
uv run ruff format .           # formatear
uv run pytest                  # tests
uv run pytest -k nombre -q     # un test concreto
```

Arranque para móvil: Gradio con `server_name="0.0.0.0"`; el móvil abre
`http://<IP-local-del-PC>:<puerto>` en la misma wifi. El PC debe estar encendido
y sirviendo.

---

## 10. Cómo trabajar en este repo (para Claude Code)

- **Lee `PLAN.md`** al empezar: dice en qué fase estamos y qué toca.
- Trabaja **una fase a la vez**. Cada fase debe dejar la app usable y los datos a salvo.
- Tienes libertad en los detalles de implementación mientras respetes los
  `RF-*` / `RNF-*` y el principio rector (§2).
- **Confirma en https://docs.claude.com** el id de modelo de visión vigente y la
  forma exacta de la API de imágenes / tool use ANTES de codificar la Fase 2.
- Cuando tomes una decisión de las que pide documentar el doc (framework, política
  NULL, modelo IA), regístrala en §4 de este archivo y en el README.
- No añadas dependencias sin justificarlo. Preferir stdlib.
- Tests para: normalización, detección de duplicados, lógica "¿la tengo?"
  (exacta / parcial / sin coincidencia / anio NULL), parseo de la respuesta IA.
- Al terminar una fase: actualiza `PLAN.md` (marca la fase), abre PR, y pide
  al usuario que revise antes de mergear.
