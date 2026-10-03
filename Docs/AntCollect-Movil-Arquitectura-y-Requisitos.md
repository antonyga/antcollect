# AntCollect Móvil — Documento de Arquitectura y Requisitos

> **Propósito de este documento.** Especificación funcional y técnica de la
> **v2 móvil** de AntCollect: una app nativa (Flutter, iOS + Android) con
> backend propio, publicada en App Store y Play Store para que **cualquier
> coleccionista** pueda registrarse y usarla. Es una iniciativa **aditiva**
> respecto a la v1 de escritorio — no la sustituye ni la modifica.
>
> **Relación con la v1:** [Docs/AntCollect-Arquitectura-y-Requisitos.md](AntCollect-Arquitectura-y-Requisitos.md)
> sigue describiendo `src/antcollect/` (Gradio, local, un solo usuario) tal
> cual está, completa y en producción. Este documento describe una segunda
> línea de trabajo que vive en `backend/` y `mobile/`, reutilizando la lógica
> de dominio de la v1 donde tiene sentido (ver §6).
>
> **Autor/usuario:** un desarrollador construyendo un servicio público para
> coleccionistas (multiusuario, con cuentas).
> **Estado:** en construcción — ver [PLAN-MOVIL.md](../PLAN-MOVIL.md) para el
> estado fase a fase.

---

## 1. Qué cambia respecto a la v1

| | v1 (escritorio) | v2 (móvil) |
|---|---|---|
| Usuarios | Uno, sin cuentas | Múltiples, con registro/login |
| Datos | SQLite de archivo, local al PC | PostgreSQL en la nube, por usuario |
| Imágenes | Carpeta local `imagenes/` | Object storage en la nube |
| Acceso | Navegador, misma wifi que el PC | App nativa, desde cualquier red |
| Disponibilidad | Depende de que el PC esté encendido | Backend siempre disponible |
| Sincronización | No aplica (un solo dispositivo) | Entre todos los dispositivos del usuario |
| Distribución | Clonar el repo y arrancar | App Store / Play Store |

El **principio rector no cambia**: *la máquina propone, el humano dispone*. La
IA sigue sin escribir nunca directamente en la base de datos; el usuario
confirma los campos leídos antes de guardar. El modelo de dominio (el "tipo"
de moneda, los 5 campos, la normalización, la detección de duplicados y la
lógica "¿la tengo?") es el mismo — ver [el documento de la v1, §2](AntCollect-Arquitectura-y-Requisitos.md#2-modelo-de-dominio).

### Qué NO es esta iniciativa

- No sustituye la v1 de escritorio: `src/antcollect/` sigue funcionando igual.
- No es una comparación de imágenes (embeddings) — sigue siendo consulta
  exacta sobre campos normalizados, igual que la v1 (ver nota en el doc v1,
  §2.1).
- No incluye sincronización offline-first con resolución de conflictos en v1
  de esta iniciativa: la app móvil llama a la API en vivo (ver §5).
- No ofrece login social (Google/Apple) en la primera versión — solo
  email/contraseña (ver §7, motivo relacionado con la revisión de Apple).

---

## 2. Hecho técnico que condiciona toda la arquitectura

La `ANTHROPIC_API_KEY` no puede embeberse en el binario de la app (`.ipa`/
`.apk`): cualquiera podría extraerla y gastar el saldo de la cuenta. Por
tanto, a diferencia de la v1 (donde `CoinReader` vivía en el mismo proceso que
la UI), **la lectura por IA tiene que pasar por un backend propio** que
custodie la clave — igual de cierto que RNF-5 en la v1, aplicado a un
contexto donde el cliente ya no es de confianza.

Esto implica que, aunque "solo" quisiéramos publicar la app en las tiendas, no
hay forma de hacerlo sin un backend real. Dado que además se decidió
sincronización entre dispositivos y servicio público, ese backend también
aloja la base de datos multiusuario y las imágenes.

---

## 3. Requisitos funcionales (heredados y nuevos)

Los `RF-n` de la v1 se mantienen conceptualmente; aquí solo se listan los que
cambian o se añaden. Para el resto (RF-1 a RF-14), ver el documento de la v1.

- **RF-M1 — Cuenta de usuario.** Registro con email/contraseña, inicio de
  sesión, cierre de sesión, y **borrado de cuenta** (con confirmación) que
  elimina los datos del usuario. El borrado de cuenta es obligatorio para
  pasar la revisión de Apple si la app permite crear cuentas dentro de ella.
- **RF-M2 — Sincronización entre dispositivos.** La colección de un usuario es
  la misma vista desde cualquier dispositivo en el que inicie sesión. No hace
  falta soporte offline en v1 de esta iniciativa: cada pantalla llama a la API
  en el momento.
- **RF-M3 — Cuota de lectura por IA.** Cada usuario tiene un límite diario de
  lecturas por IA (RF-1/RF-2), para controlar el coste del backend al ser un
  servicio público. Al superarlo, la app ofrece el modo manual (igual que
  RF-6 ante un fallo de red).
- **RF-7 / RF-8 (adaptados) — Captura en móvil.** Foto de anverso y reverso
  con la cámara del teléfono. El modo "detalle/macro" de la v1 (pensado para
  un microscopio USB conectado al PC) se adapta a la cámara trasera del móvil
  (zoom óptico/macro si el modelo lo soporta) — ver §8.

---

## 4. Requisitos no funcionales (heredados y nuevos)

- **RNF-M1 (sustituye a RNF-2/RNF-3 de la v1) — Datos en la nube, por
  usuario.** Los datos de cada usuario viven en el backend, aislados de los
  de otros usuarios (scoping por `usuario_id` en cada consulta). La app
  necesita red para todo (no solo para la IA), a cambio de estar disponible
  desde cualquier dispositivo.
- **RNF-M2 — Coste de IA acotado por diseño.** La cuota por usuario (RF-M3) no
  es opcional: sin ella, el coste de la API de Anthropic escala con cada
  registro público sin control. Configurable, no hardcodeada.
- **RNF-5 (se mantiene) — Clave de API fuera del cliente.** Ahora además fuera
  del *cliente* (la app), no solo fuera de git: vive solo en el backend.
- **RNF-6 (se mantiene) — Proveedor de IA desacoplado.** `CoinReader` se
  reutiliza tal cual (ver §6); sigue siendo sustituible.
- **RNF-7 (se mantiene) — Robustez de datos.** Transacciones en el backend;
  nunca se escribe sin confirmación humana.
- **RNF-M3 — Cumplimiento de tienda.** Política de privacidad y términos de
  servicio publicados; formularios de privacidad de datos de cada tienda
  completados con precisión (qué se recoge: email, fotos, uso de un
  procesador de terceros — Anthropic — para la lectura por IA).
- **RNF-8 (ya no aplica igual)** — la v1 evitaba deliberadamente
  autenticación/servidores por ser de un solo usuario; esta iniciativa los
  necesita porque el alcance cambió a "servicio público". Se mantiene el
  espíritu (no añadir infraestructura que no haga falta: sin colas, sin
  microservicios más allá de "backend" + "base de datos" + "almacenamiento de
  objetos").

---

## 5. Arquitectura

```
┌─────────────────────────────┐        ┌─────────────────────────────┐
│   App Flutter (iOS/Android)  │        │   App Gradio v1 (sin cambios) │
│   api/ · auth/ · coleccion/  │        │        src/antcollect/        │
│   captura/ · cuenta/         │        │                               │
└───────────────┬──────────────┘        └───────────────────────────────┘
                │ HTTPS + JWT
┌───────────────┴──────────────────────────────────────────────────┐
│                     Backend (FastAPI, Railway)                     │
│                                                                     │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  auth    │  │   coleccion   │  │  lecturas IA │  │ exportar  │  │
│  │ (JWT,    │──│  (scopeada    │──│ (CoinReader, │  │ (CSV/JSON │  │
│  │ borrado) │  │  por usuario) │  │  cuota/día)  │  │ streaming)│  │
│  └──────────┘  └───────┬───────┘  └──────┬───────┘  └───────────┘  │
│                         │                 │                        │
│                 ┌───────┴───────┐  ┌──────┴───────┐                │
│                 │  PostgreSQL   │  │ Object storage│                │
│                 │ (usuarios +   │  │  (imágenes,   │                │
│                 │  monedas)     │  │  por usuario) │                │
│                 └───────────────┘  └───────┬───────┘                │
└────────────────────────────────────────────┼────────────────────────┘
                                              │ (red, solo al leer)
                                       Anthropic API (Claude, visión)
```

### Componentes

- **App Flutter.** Dos flujos (enseñar / comprobar) + listado/ficha/filtros +
  exportación + cuenta (login, cerrar sesión, borrar cuenta). Llama a la API
  en vivo; sin caché offline en v1.
- **Backend FastAPI.** Expone rutas REST para auth, colección, lecturas IA y
  exportación. Lógica de dominio adaptada de `coleccion.py`/`normalizacion.py`
  (§6), scopeada por `usuario_id` extraído del JWT.
- **PostgreSQL.** Sustituye a SQLite; mismo esquema conceptual que la v1 (ver
  §7) más `usuario_id`.
- **Object storage.** Sustituye a la carpeta `imagenes/` local; una imagen por
  anverso/reverso/detalle, con clave que incluye el `usuario_id` para aislar
  datos entre usuarios.
- **CoinReader (sin cambios).** Mismo contrato y misma implementación
  (`ClaudeCoinReader`) que la v1 — es stateless y no sabe nada de usuarios ni
  de persistencia, por eso se reutiliza tal cual.

---

## 6. Reutilización de la v1 (catálogo)

Confirmado por exploración directa de `src/antcollect/` al planificar esta
iniciativa:

| Módulo v1 | Qué pasa en v2 |
|---|---|
| `normalizacion.py` | Se copia tal cual — funciones puras. |
| `ai/base.py` (`CoinReader`, `LecturaMoneda`) + `ai/claude.py` (`ClaudeCoinReader`) | Se copian tal cual — stateless, sin DB ni usuario. |
| `imagenes.redimensionar()` | Se copia tal cual (Pillow puro). |
| `modelo.py` | Se adapta: añade `usuario_id`, pasa a Pydantic/ORM, deja de depender de `sqlite3.Row`. |
| `coleccion.py` | Se adapta: mismo contrato (`crear`, `editar`, `borrar`, `listar`, `comprobar_tipo`, `existe_tipo_exacto`, `TipoDuplicadoError`), ahora async y scopeado por `usuario_id`. |
| `exportar.py` | Se adapta: devuelve streams para respuesta HTTP en vez de escribir a disco del servidor. |
| `imagenes.py` (resto), `db.py`, `ui/app.py` | Se descartan / reescriben — ligados a filesystem local, SQLite sin servidor, o Gradio. |

El dominio en español (`pais`, `valor`, `anio`, `ceca`, `Moneda`,
`comprobar_tipo`...) se mantiene como convención también en el backend nuevo,
siguiendo la decisión ya tomada para la v1 (`CLAUDE.md` §4).

---

## 7. Autenticación y cuentas

- Email + contraseña, JWT (access + refresh). **Sin login social en v1** de
  esta iniciativa: Apple exige ofrecer "Sign in with Apple" únicamente si se
  ofrece *algún* login de terceros (Google, Facebook...); evitando el login
  social se evita también ese requisito adicional.
- Endpoint de **borrado de cuenta**, accesible desde la app (obligatorio para
  pasar la revisión de Apple, guideline 5.1.1, cuando la app permite crear
  cuentas).
- Las contraseñas se guardan con hash (nunca en claro); los tokens JWT llevan
  expiración corta + refresh token de vida más larga.

---

## 8. Captura de imagen en móvil

- Cámara trasera del teléfono para anverso y reverso (es la fuente de verdad
  para la lectura por IA, igual que en la v1).
- El modo "detalle/macro" de la v1 dependía de un microscopio USB conectado al
  PC (una fuente de cámara más entre varias). Un móvil no tiene eso: se
  sustituye por la cámara trasera con zoom/macro nativo del propio teléfono si
  el modelo lo soporta. Sigue sin enviarse nunca a la IA — solo apoyo visual
  humano para confirmar cecas/variantes dudosas, igual que en la v1.

---

## 9. Control de coste de IA

Al ser un servicio público, cada lectura por IA (RF-1/RF-2) cuesta dinero real
al operador del backend, no al usuario. Se implementa una cuota diaria por
usuario (valor inicial configurable, p. ej. 20 lecturas/día — a revisar según
uso real) en el endpoint de lecturas. Al superarla, la API devuelve un error
claro y la app cae al formulario manual, igual que ante un fallo de red (RF-6
de la v1).

---

## 10. Cumplimiento de tiendas

- **Apple Developer Program** (~99 $/año) y **Google Play Console** (25 $ una
  vez) — cuentas personales del usuario, no delegables a Claude Code.
- Política de privacidad y términos de servicio publicados en una URL
  accesible, enlazados desde la ficha de la app en ambas tiendas.
- Formularios de privacidad de datos: App Privacy (Apple) / Data Safety
  (Google) — deben reflejar con precisión qué se recoge (email, fotos) y que
  las fotos se envían a un procesador de terceros (Anthropic) para la lectura
  por IA.
- Borrado de cuenta accesible desde dentro de la app (§7).
- Icono, splash, capturas de pantalla, descripción, categoría, clasificación
  por edad.
- Beta antes de publicar: TestFlight (iOS) / pista interna (Android).

---

## 11. Plan de construcción por fases

Ver [PLAN-MOVIL.md](../PLAN-MOVIL.md) para el desglose fase a fase (M0 a M6) y
el estado actual.

---

## 12. Notas para Claude Code

- Este documento describe el *qué* y el *cómo* de alto nivel de la v2 móvil.
  Para el modelo de dominio compartido (el "tipo" de moneda, reglas de
  normalización y de "¿la tengo?"), la referencia sigue siendo
  [el documento de la v1](AntCollect-Arquitectura-y-Requisitos.md).
- **No tocar `src/antcollect/`** por trabajo de esta iniciativa salvo que el
  usuario lo pida explícitamente — es la v1, completa y en uso.
- Seguir el mismo flujo de Git que la v1 (`CLAUDE.md` §8): una rama + un PR
  por fase, Conventional Commits en español, nunca commitear secretos
  (`.env`, credenciales de base de datos/object storage).
- Confirmar en la documentación oficial cualquier detalle de API que pueda
  haber cambiado (modelo de IA vigente, SDKs de FastAPI/SQLAlchemy/Flutter)
  antes de depender de él.
