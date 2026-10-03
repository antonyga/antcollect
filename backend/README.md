# AntCollect — backend (v2 móvil)

API FastAPI para la app móvil de AntCollect (Flutter, iOS + Android):
autenticación, colección multiusuario, lectura por IA y exportación.

No confundir con `src/antcollect/` (v1 de escritorio, Gradio + SQLite local,
completa y sin relación con este directorio salvo por la lógica de dominio
que se reutiliza desde aquí — ver el catálogo de reutilización).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

**Fase M1 completa:** autenticación (registro/login/refresco/borrado de
cuenta) y colección multiusuario (alta, edición, borrado, listado, "¿la
tengo?", detección de duplicados) scopeada por `usuario_id`. Sin imágenes ni
lectura por IA todavía — eso es la Fase M2.

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

Documentación interactiva de la API una vez arrancada: `http://localhost:8000/docs`.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Los tests corren contra SQLite en memoria (`aiosqlite`), sin necesitar
Postgres ni Railway — ver `tests/conftest.py`.

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
│   ├── dependencias.py               # sesión de BD + usuario autenticado (FastAPI Depends)
│   ├── ai/                            # (Fase M2) copia de src/antcollect/ai/
│   └── rutas/
│       ├── auth.py                     # /auth/*
│       └── coleccion.py                 # /coleccion/*
├── alembic/                              # migraciones (fuente de verdad del esquema)
└── tests/
    ├── conftest.py                        # BD de pruebas en memoria + cliente HTTP
    ├── test_coleccion.py                   # migrado de tests/test_coleccion.py (v1)
    └── test_auth.py                         # auth + aislamiento entre usuarios (RNF-M1)
```

## Infraestructura (Railway)

PostgreSQL + object storage + servicio backend, aprovisionados en Railway
(pendiente — bloqueado en la Fase M0 por fallo de conexión del MCP de Railway
en esa sesión; reintentar antes de desplegar de verdad. El código ya funciona
en local contra SQLite mientras tanto).
