# AntCollect — backend (v2 móvil)

API FastAPI para la app móvil de AntCollect (Flutter, iOS + Android):
autenticación, colección multiusuario, lectura por IA y exportación.

No confundir con `src/antcollect/` (v1 de escritorio, Gradio + SQLite local,
completa y sin relación con este directorio salvo por la lógica de dominio
que se reutiliza desde aquí — ver el catálogo de reutilización).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

Esqueleto de directorios (Fase M0). El código (FastAPI + SQLAlchemy async +
Alembic + auth + dominio multiusuario) se construye en la Fase M1.

## Estructura prevista

```
backend/
├── app/
│   ├── main.py
│   ├── config.py           # equivalente a src/antcollect/config.py, adaptado
│   ├── db.py                # SQLAlchemy async engine/session
│   ├── modelos.py           # Usuario, Moneda (Pydantic/ORM)
│   ├── normalizacion.py     # copia tal cual de src/antcollect/normalizacion.py
│   ├── coleccion.py         # adaptado de src/antcollect/coleccion.py (usuario_id, async)
│   ├── imagenes.py          # adaptado: sube/baja de object storage
│   ├── exportar.py          # adaptado: devuelve streams
│   ├── ai/                  # copia de src/antcollect/ai/ (base.py + claude.py)
│   ├── auth.py               # registro/login/JWT/borrar cuenta
│   └── rutas/                 # routers: auth, coleccion, lecturas, exportar
├── alembic/                  # migraciones
└── tests/
```

## Infraestructura (Railway)

PostgreSQL + object storage + servicio backend, aprovisionados en Railway
(pendiente — bloqueado en Fase M0 por fallo de conexión del MCP de Railway en
esta sesión; reintentar cuando esté disponible).
