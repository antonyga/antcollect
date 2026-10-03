# PLAN-MOVIL.md — Plan de construcción de AntCollect Móvil por fases

> Estado vivo de la **v2 móvil** (app nativa + backend + publicación en
> tiendas). Hermano de [PLAN.md](PLAN.md), que sigue describiendo la v1 de
> escritorio (completa, sin tocar por esta iniciativa). Especificación
> completa en
> [Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md).
>
> Decidido con el usuario (2026-10-03): Flutter, datos sincronizados entre
> dispositivos, servicio **público** para cualquier coleccionista.

---

## Fase actual: **M2 — Backend: imágenes + IA + exportación** (completa, pendiente de PR)

> M1 está en PR #10 (recuperación: su primer PR, #9, se mergeó en la rama de M0 y no llegó a `main`). La rama de M2 sale de la de M1; su PR apunta a `main` directamente para no repetir ese problema.

---

## Fase M0 — Fundaciones y documentación  ·  rama `feat/fase-m0-fundaciones`

- [x] Documento de arquitectura: `Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md`
- [x] Este plan de fases (`PLAN-MOVIL.md`)
- [x] `CLAUDE.md` ampliado con una sección que señale a ambos documentos y dejando explícito que `src/antcollect/` (v1) no se toca por esta iniciativa
- [x] Estructura de carpetas `backend/` (FastAPI) y `mobile/` (Flutter) como esqueletos vacíos/mínimos
- [ ] Infraestructura en Railway: PostgreSQL + bucket de object storage + servicio backend (skill `use-railway`) — **bloqueado**: el MCP de Railway no conectó en esta sesión (`CONNECTION_CLOSED`). Reintentar al empezar la Fase M1.
- [ ] Aviso al usuario de las cuentas que debe crear él mismo: Apple Developer Program (~99 $/año) y Google Play Console (25 $ una vez) — no delegable
- [ ] Instalar el SDK de Flutter antes de la Fase M3 (no está instalado en esta máquina — ver `mobile/README.md`)

**Sale usable:** documentación y esqueleto listos para empezar a programar el backend en la Fase M1.

---

## Fase M1 — Backend: autenticación + dominio multiusuario  ·  rama `feat/fase-m1-backend-auth` (recuperada en `fix/recupera-fase-m1`)  ·  ✅ completada, PR #10 pendiente de merge

Cubre: RF-M1, RNF-M1.

- [x] Esqueleto FastAPI + SQLAlchemy async (`app/main.py`, `app/db.py`) + Alembic (`alembic/`, migración inicial `ba74a016b044`)
- [x] Modelo `Usuario` (email único, hash de contraseña con `bcrypt`, fecha de alta) — `app/modelos.py`
- [x] Auth: registro, login, refresco de JWT, borrar cuenta (`POST /auth/registro`, `/login`, `/refresco`, `GET /auth/yo`, `DELETE /auth/cuenta`) — `app/auth.py` + `app/seguridad.py` (JWT con `pyjwt`, access 30 min / refresh 30 días por defecto, configurable)
- [x] `normalizacion.py` copiado tal cual desde `src/antcollect/`
- [x] `modelos.py`: `Moneda` ORM con `usuario_id`, esquemas Pydantic de entrada/salida separados en `app/esquemas.py` (en vez de SQLModel, para no acoplar la forma de la API al esquema de BD)
- [x] `coleccion.py` adaptado: mismo contrato (`crear`, `editar`, `borrar`, `listar`, `comprobar_tipo`, `existe_tipo_exacto`, `buscar_posibles_coincidencias`, `TipoDuplicadoError`), scopeado por `usuario_id`, sesiones async de SQLAlchemy
- [x] Esquema con `UNIQUE(usuario_id, pais_norm, valor_norm, anio, ceca_norm, variante_norm)` — migración de Alembic generada y verificada (aplica limpio en una BD vacía); portable a PostgreSQL, probada contra SQLite por no tener aún Postgres provisionado (ver Fase M0)
- [x] Tests migrados de `tests/test_coleccion.py` (normalización, duplicados, "¿la tengo?": exacta/parcial/ninguna) al nuevo dominio multiusuario — 18 tests
- [x] **Añadido más allá del checklist original**: suite de tests de aislamiento entre usuarios (`tests/test_auth.py`, 14 tests) — confirma que dos usuarios pueden tener el mismo "tipo" sin chocar, que uno no puede leer/editar/borrar la moneda de otro (404, no 403, para no filtrar su existencia), y que borrar una cuenta borra en cascada su colección sin dejar rastro. Es la propiedad de seguridad más nueva y más crítica de la v2 frente a la v1.

**Sale usable:** API de auth + CRUD de colección + "¿la tengo?" funcionando (sin imágenes ni IA todavía — Fase M2), verificada con 32 tests (`pytest`) contra SQLite en memoria y con un smoke test manual del servidor real (`uvicorn`) sirviendo `/salud` y el flujo completo de un usuario. `ruff check`/`ruff format --check` en verde. La v1 de escritorio sigue intacta (58 tests propios sin tocar).

**Pendiente:** desplegar de verdad contra PostgreSQL en Railway (bloqueado desde la Fase M0, el MCP de Railway no conectó) — el código ya es compatible (driver `asyncpg`), solo falta la infraestructura real para probarlo end-to-end contra el motor de producción.

---

## Fase M2 — Backend: imágenes + IA + exportación  ·  rama `feat/fase-m2-backend-ia`  ·  ✅ completada (código), pendiente de PR

Cubre: RF-7/RF-8 (subida de imágenes), RF-M3, RNF-M2, RF-13.

- [x] Subida/descarga/borrado de imágenes (anverso/reverso/detalle): `PUT/GET/DELETE /coleccion/{id}/imagenes/{cara}`, reutilizando `imagenes.redimensionar()` tal cual. Interfaz `Almacen` con dos implementaciones: `AlmacenLocal` (dev/tests) y `AlmacenS3` (producción, cualquier S3 compatible — Railway Buckets). Claves `usuarios/{usuario_id}/monedas/{id:04d}_{cara}.jpg`
- [x] **Añadido**: las fotos se enderezan según EXIF (fotos de móvil) y se re-codifican a JPEG **sin metadatos** — no se guarda la geolocalización GPS que muchos móviles incrustan (privacidad, RNF-M3)
- [x] **Añadido**: borrar una moneda borra sus fotos; borrar la cuenta borra todo su prefijo en el almacén (antes solo se borraban las filas). Fotos primero, para no dejar nunca fotos personales huérfanas
- [x] Endpoint de lectura IA `POST /lecturas` reutilizando `ai/base.py` tal cual y `ai/claude.py` con cambios mínimos (config, EXIF, `tool_choice: auto` + `strict` porque los modelos actuales rechazan el forzado — ver `backend/README.md`). Solo propone: no escribe en la colección
- [x] Cuota diaria configurable por usuario (`LECTURAS_IA_CUOTA_DIARIA`, tabla `lecturas_ia`, migración `ef7bec6a4a6f`), `GET /lecturas/cuota`; lectura fallida no gasta cuota; `429`/`503`/`fallida: true` → la app pasa a modo manual
- [x] Endpoints de exportación CSV/JSON en streaming: `GET /exportar?formato=csv|json` (adaptado de `exportar.py`)
- [x] Documentación OpenAPI servida (`/docs`, `/openapi.json`) y revisada: todas las rutas aparecen con sus tipos de contenido
- [x] Tests: 93 en total (61 nuevos) — imágenes (normalización, aislamiento entre usuarios, limpieza), lecturas + cuota (por usuario, renovación diaria, sin gastar en fallos), exportación, adaptador Claude (migrados de la v1), contrato del almacén contra local y S3 simulado (`moto`)

**Sale usable:** backend completo — todo lo que necesita la app móvil ya tiene API. Verificado con `pytest` + smoke test manual contra `uvicorn` (registro → moneda → foto → descarga → lectura sin clave = 503 → exportar → borrar moneda y cuenta = almacén vacío).

**Pendiente (fuera de esta fase):** probar una lectura real contra la API de Anthropic (requiere `ANTHROPIC_API_KEY` en `backend/.env`) y desplegar en Railway con Postgres + bucket (bloqueado desde M0).

---

## Fase M3 — App Flutter: esqueleto + auth + colección  ·  rama `feat/fase-m3-flutter-base`

Cubre: RF-M1 (cliente), RF-M2, RF-9, RF-10, RF-11, RF-12.

- [ ] Proyecto Flutter (`mobile/`), estructura de carpetas, cliente HTTP (`dio`), almacenamiento seguro del token (`flutter_secure_storage`)
- [ ] Pantallas: login/registro, inicio (2 botones), listado + filtros + ficha + editar/borrar — contra la API real
- [ ] Sin cámara ni IA todavía

**Sale usable:** se puede instalar en un emulador/dispositivo, iniciar sesión y gestionar la colección a mano.

---

## Fase M4 — App Flutter: captura + lectura IA  ·  rama `feat/fase-m4-flutter-ia`

Cubre: RF-1, RF-2, RF-3, RF-4, RF-5, RF-7, RF-8 (cliente), RF-13 (cliente).

- [ ] Integración de cámara (anverso/reverso/detalle con la cámara del propio teléfono, sin selector de dispositivo USB — ver doc de arquitectura §8)
- [ ] Pipeline compartido capturar → leer → confirmar, igual que en la v1
- [ ] Flujo "enseñar moneda nueva" completo
- [ ] Flujo "¿la tengo?" completo (exacta / parcial / ninguna)
- [ ] Exportación desde la app

**Sale usable:** la app cubre el objetivo central de principio a fin, igual que la v1 pero multiusuario y en el móvil.

---

## Fase M5 — Pulido y cumplimiento de tiendas  ·  rama `feat/fase-m5-cumplimiento`

Cubre: RF-M1 (borrado de cuenta visible), RNF-M3.

- [ ] Icono, splash, repaso de textos
- [ ] Política de privacidad + términos de servicio publicados
- [ ] Borrado de cuenta accesible desde la app
- [ ] Formularios de privacidad de datos (App Privacy / Data Safety) completados
- [ ] Beta en TestFlight (iOS) / pista interna (Android)

**Sale usable:** build candidato a publicación, probado por el usuario en sus propios dispositivos.

---

## Fase M6 — Publicación  ·  rama `feat/fase-m6-publicacion`

- [ ] Alta en App Store Connect / Play Console (cuentas de pago del usuario — ver Fase M0)
- [ ] Build de release firmado (certificados/provisioning iOS, keystore Android)
- [ ] Envío a revisión
- [ ] Resolver feedback de los revisores si lo hay
- [ ] Publicación

**Sale usable:** AntCollect Móvil disponible en App Store y Play Store.

---

## Registro de decisiones

| Fecha | Decisión | Dónde queda documentada |
|---|---|---|
| 2026-10-03 | Framework móvil: Flutter (un solo código iOS + Android) | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md |
| 2026-10-03 | Datos sincronizados entre dispositivos (no solo local al móvil) | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §1, §5 |
| 2026-10-03 | Servicio público — cualquier coleccionista puede registrarse | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §1 |
| 2026-10-03 | Backend: FastAPI + PostgreSQL + object storage, hospedado en Railway | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §5 |
| 2026-10-03 | Auth: email/contraseña, sin login social en v1 (evita el requisito de "Sign in with Apple") | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §7 |
| 2026-10-03 | Cuota diaria de lecturas IA por usuario (coste acotado) | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §9 |
| 2026-10-03 | App móvil v1 = "online" (sin caché offline-first ni sync de conflictos) | Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md §1 |
| 2026-10-03 | `src/antcollect/` (v1 escritorio) no se toca por esta iniciativa | CLAUDE.md, este archivo |
| 2026-10-03 | Backend: ORM SQLAlchemy 2.0 (no SQLModel) + esquemas Pydantic separados en `app/esquemas.py` — evita acoplar la forma de la API al esquema de BD y evita exponer columnas internas (p. ej. `password_hash`) por error | `backend/app/modelos.py`, `backend/app/esquemas.py` |
| 2026-10-03 | Auth: JWT access (30 min) + refresh (30 días) por defecto, configurable por entorno; contraseñas con `bcrypt` directo (no `passlib`, menos mantenido) | `backend/app/seguridad.py` |
| 2026-10-03 | Tests de backend contra SQLite en memoria (`aiosqlite` + `StaticPool`), no contra Postgres real — no bloquea desarrollo mientras Railway no esté disponible; el esquema generado por Alembic es portable | `backend/tests/conftest.py` |
| 2026-10-03 | Fotos servidas a través del backend con JWT (bucket privado), no URLs públicas/prefirmadas | `backend/app/rutas/imagenes.py`, `backend/README.md` |
| 2026-10-03 | Cuota IA con "reservar y devolver", día natural UTC; la lectura fallida no gasta | `backend/app/lecturas.py` |
| 2026-10-03 | Adaptador Claude del backend: `tool_choice: auto` + `strict: true` (el forzado da 400 en modelos actuales); modelo por defecto sigue `claude-sonnet-5` | `backend/app/ai/claude.py` |
| 2026-10-03 | Fotos re-codificadas a JPEG sin EXIF (sin geolocalización) | `backend/app/imagenes.py` |
