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

## Fase actual: **M0 — Fundaciones y documentación**

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

## Fase M1 — Backend: autenticación + dominio multiusuario  ·  rama `feat/fase-m1-backend-auth`

Cubre: RF-M1, RNF-M1.

- [ ] Esqueleto FastAPI + SQLAlchemy async + Alembic
- [ ] Modelo `Usuario` (email, hash de contraseña, fecha de alta)
- [ ] Auth: registro, login, refresh de JWT, borrar cuenta
- [ ] `normalizacion.py` copiado tal cual desde `src/antcollect/`
- [ ] `modelo.py` adaptado: `Moneda` con `usuario_id`, Pydantic/ORM en vez de `sqlite3.Row`
- [ ] `coleccion.py` adaptado: mismo contrato (`crear`, `editar`, `borrar`, `listar`, `comprobar_tipo`, `existe_tipo_exacto`, `TipoDuplicadoError`), scopeado por `usuario_id`, sesiones async
- [ ] Esquema PostgreSQL con `UNIQUE(usuario_id, pais_norm, valor_norm, anio, ceca_norm, variante_norm)`
- [ ] Tests migrados de `tests/test_coleccion.py` (normalización, duplicados, "¿la tengo?": exacta/parcial/ninguna/año NULL) al nuevo dominio multiusuario

**Sale usable:** API de auth + CRUD de colección funcionando (sin imágenes ni IA todavía), verificable con Swagger UI/`httpx`.

---

## Fase M2 — Backend: imágenes + IA + exportación  ·  rama `feat/fase-m2-backend-ia`

Cubre: RF-7/RF-8 (subida de imágenes), RF-M3, RNF-M2, RF-13.

- [ ] Subida/descarga de imágenes a object storage (anverso/reverso/detalle), reutilizando `imagenes.redimensionar()` tal cual
- [ ] Endpoint de lectura IA reutilizando `ai/base.py` + `ai/claude.py` tal cual, con cuota diaria configurable por usuario
- [ ] Endpoints de exportación CSV/JSON en streaming (adaptado de `exportar.py`)
- [ ] Documentación OpenAPI servida y revisada

**Sale usable:** backend completo — todo lo que necesita la app móvil ya tiene API.

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
