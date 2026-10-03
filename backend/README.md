# AntCollect — backend (v2 móvil)

API FastAPI para la app móvil de AntCollect (Flutter, iOS + Android):
autenticación, colección multiusuario, lectura por IA y exportación.

No confundir con `src/antcollect/` (v1 de escritorio, Gradio + SQLite local,
completa y sin relación con este directorio salvo por la lógica de dominio
que se reutiliza desde aquí — ver el catálogo de reutilización).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

**Fases M1 + M2 completas** — el backend ya cubre todo lo que necesita la app:

- **Auth** (M1): registro, login, refresco de JWT, `GET /auth/yo`, borrado
  de cuenta (borra también todas sus fotos).
- **Colección** (M1): alta, edición, borrado, listado con filtros, "¿la
  tengo?" (`POST /coleccion/comprobar`), duplicados — scopeado por usuario.
- **Fotos** (M2): `PUT/GET/DELETE /coleccion/{id}/imagenes/{anverso|reverso|detalle}`.
  Se enderezan (EXIF), se reducen a 2000 px y se guardan como JPEG **sin
  metadatos** (no se guarda la geolocalización de la foto). Se sirven a
  través de la API con el JWT, nunca con URLs públicas del bucket.
- **Lectura IA** (M2): `POST /lecturas` (multipart `anverso` + `reverso`
  opcional) devuelve campos **propuestos** — no escribe nada en la
  colección. Cuota diaria por usuario (`GET /lecturas/cuota`); una lectura
  fallida no gasta cuota. Respuestas que la app debe tratar como "pasar a
  modo manual": `503` (IA no configurada), `429` (cuota agotada) y `200`
  con `fallida: true`.
- **Respaldo de IA** (M2): Claude es el proveedor principal; si falla
  (sin red, timeout, sobrecarga, error de la API, rechazo o respuesta
  inválida), la misma petición prueba al momento OpenAI y después DeepSeek,
  según qué claves haya en `.env`. Solo si fallan todos la app pasa al modo
  manual. Una foto ilegible *no* es un fallo: no se pregunta a otro
  proveedor.
- **Exportación** (M2): `GET /exportar?formato=csv|json`, en streaming.

## Arrancar en local

```bash
uv sync
cp .env.example .env   # valores por defecto ya sirven para desarrollo local
uv run alembic upgrade head   # crea el esquema (o usa db.crear_tablas() en pruebas rápidas)
uv run uvicorn app.main:app --reload
```

Por defecto, sin `DATABASE_URL` en `.env`, apunta a un SQLite local
(`antcollect_dev.db`, ignorado por git) — suficiente para desarrollar sin
Postgres a mano. En producción, `DATABASE_URL` debe ser una cadena
`postgresql+asyncpg://...` (Railway la da al aprovisionar la BD).

Documentación interactiva de la API una vez arrancada: `http://localhost:8000/docs`
(OpenAPI en `/openapi.json`).

Sin ninguna clave de IA (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`DEEPSEEK_API_KEY`), `POST /lecturas` responde `503` y todo lo demás
funciona. Por defecto las fotos se guardan en `./almacen_dev/` (ignorado por
git); en producción usar `ALMACEN=s3` (ver más abajo).

## Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Los tests corren contra SQLite en memoria (`aiosqlite`), sin necesitar
Postgres ni Railway — ver `tests/conftest.py`. Tampoco llaman nunca a la API
de Anthropic (lector IA falso) ni a un bucket real (almacén en `tmp_path`, y
el adaptador S3 se prueba contra un S3 simulado con `moto`).

## Estructura

```
backend/
├── app/
│   ├── main.py            # FastAPI app, registra los routers
│   ├── config.py           # settings por variable de entorno (.env)
│   ├── db.py                 # engine/sesión async, Base declarativa
│   ├── modelos.py             # ORM: Usuario, Moneda (usuario_id, UNIQUE por usuario)
│   ├── esquemas.py             # Pydantic: entrada/salida de la API
│   ├── normalizacion.py         # copia tal cual de src/antcollect/normalizacion.py
│   ├── coleccion.py              # adaptado de src/antcollect/coleccion.py (usuario_id, async)
│   ├── seguridad.py                # hash de contraseñas + JWT
│   ├── auth.py                      # registro/login/refresco/borrar cuenta
│   ├── dependencias.py               # sesión, usuario autenticado, almacén, lector IA
│   ├── ai/                            # CoinReader (copia v1) + adaptadores:
│   │   ├── comun.py                    #   prompt/esquema/parseo compartidos
│   │   ├── claude.py                    #   principal (Anthropic)
│   │   ├── gpt.py                        #   respaldo 1 (OpenAI, Responses API)
│   │   ├── deepseek.py                    #   respaldo 2 (DeepSeek, compatible OpenAI)
│   │   └── respaldo.py                     #   cadena: Claude → OpenAI → DeepSeek
│   ├── almacen.py                      # Almacen: local (dev/tests) o S3 (producción)
│   ├── imagenes.py                      # redimensionar (copia v1) + normalizar a JPEG
│   ├── lecturas.py                       # cuota diaria de lecturas IA
│   ├── exportar.py                        # CSV/JSON por trozos (adaptado de la v1)
│   └── rutas/
│       ├── auth.py                     # /auth/*
│       ├── coleccion.py                 # /coleccion/*
│       ├── imagenes.py                   # /coleccion/{id}/imagenes/{cara}
│       ├── lecturas.py                    # /lecturas, /lecturas/cuota
│       └── exportar.py                     # /exportar
├── alembic/                              # migraciones (fuente de verdad del esquema)
└── tests/
    ├── conftest.py                        # BD de pruebas en memoria + cliente HTTP
    ├── test_coleccion.py                   # migrado de tests/test_coleccion.py (v1)
    ├── test_auth.py                         # auth + aislamiento entre usuarios (RNF-M1)
    ├── test_imagenes.py                      # fotos: normalización, aislamiento, limpieza
    ├── test_lecturas.py                       # lectura IA + cuota diaria
    ├── test_exportar.py                        # CSV/JSON
    ├── test_ai_claude.py                        # adaptador Claude (migrado de la v1)
    ├── test_ai_proveedores_respaldo.py           # adaptadores OpenAI y DeepSeek
    ├── test_ai_respaldo.py                        # cadena de respaldo y su montaje
    └── test_almacen.py                           # contrato del almacén: local y S3 (moto)
```

## Decisiones de la Fase M2

- **Fotos a través del backend, no URLs públicas/firmadas del bucket.** El
  aislamiento entre usuarios lo garantiza la misma comprobación de
  propiedad que el resto de la API, y el bucket puede ser privado. Coste:
  el tráfico de imágenes pasa por el servicio (aceptable a esta escala;
  revisable con URLs prefirmadas si hiciera falta).
- **La lectura IA no guarda las fotos.** Se leen y se descartan; si el
  usuario guarda la moneda, la app sube después las fotos a
  `/coleccion/{id}/imagenes/...`. Así `POST /lecturas` no escribe nada.
- **Cuota con "reservar y devolver".** Se cuenta la lectura antes de llamar
  a la IA (nunca se supera la cuota aunque lleguen peticiones a la vez) y se
  devuelve si la IA no pudo leer nada. Día natural en UTC.
- **`tool_choice: auto` + `strict: true`** en el adaptador Claude, en vez del
  `tool_choice` forzado de la v1: los modelos actuales (`claude-sonnet-5-5`,
  `claude-opus-5-5`) rechazan el forzado con un 400, y así cambiar
  `ANTCOLLECT_MODELO` no rompe la lectura. Modelo por defecto:
  `claude-sonnet-5` (misma decisión que la v1).
- **Respaldo OpenAI → DeepSeek** (decisión del usuario): mismo prompt y
  mismo esquema para los tres (`ai/comun.py`), porque el usuario no sabe
  qué proveedor respondió. Timeout de 45 s y sin reintentos del SDK por
  proveedor, para que el respaldo entre al momento. OpenAI usa la Responses
  API (los modelos GPT-6 la exigen para tool calling); DeepSeek usa su API
  compatible con OpenAI con el SDK `openai`. Ambos SDK solo se importan
  dentro de `ai/` (RNF-6). La cuota cuenta una lectura por petición, la
  sirva quien la sirva.

## Infraestructura (Railway)

PostgreSQL + bucket de object storage + servicio backend, aprovisionados en
Railway (pendiente — el MCP de Railway no conectó en las sesiones de M0–M2;
reintentar antes de desplegar de verdad. El código ya funciona en local
contra SQLite y almacén en disco mientras tanto).

Variables del servicio backend en producción:

- `DATABASE_URL` → la del Postgres de Railway, con el esquema
  `postgresql+asyncpg://`.
- `JWT_SECRET` → un secreto largo y aleatorio.
- `ANTHROPIC_API_KEY`, y opcionalmente `ANTCOLLECT_MODELO` y
  `LECTURAS_IA_CUOTA_DIARIA`.
- Respaldo (opcional): `OPENAI_API_KEY` + `ANTCOLLECT_MODELO_OPENAI`,
  `DEEPSEEK_API_KEY` + `ANTCOLLECT_MODELO_DEEPSEEK`. Cada cuenta necesita
  saldo y acceso al modelo elegido.
- `ALMACEN=s3` + `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`,
  `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` → las credenciales del bucket
  de Railway (referenciándolas desde el servicio bucket, no copiándolas).
- Antes de arrancar: `alembic upgrade head`.
