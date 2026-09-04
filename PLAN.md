# PLAN.md — Plan de construcción de AntCollect por fases

> Estado vivo del proyecto. Claude Code lo lee al empezar cada sesión.
> Marcar `[x]` al completar y validar cada fase. Cada fase = una rama + un PR.
>
> **Orden ajustado por decisión del usuario: "IA lo antes posible".**
> Respecto al plan de hitos del doc de arquitectura (§13), la lectura por IA se
> adelanta: va justo después del CRUD manual, antes de pulir la comprobación.

---

## Fase actual: **4 — Captura y modos**

---

## Fase 0 — Esqueleto  ·  rama `feat/fase-0-esqueleto`  ·  ✅ completada

Objetivo: el proyecto arranca y sirve una página vacía. Infra y control de versiones listos.

- [x] `git init`, `.gitignore` / `.gitattributes`, primer commit
- [x] `gh auth login` → repo `antonyga/antcollect` público → push de `main`
- [x] `main` protegida (PR obligatorio, historial lineal, sin force-push)
- [x] `pyproject.toml` con uv, Python 3.11, deps base (gradio, pillow, python-dotenv, anthropic) + dev (ruff, pytest)
- [x] `.env.example` con `ANTHROPIC_API_KEY` y `ANTCOLLECT_MODELO`
- [x] `src/antcollect/config.py`: carga `.env`, rutas de BD e imágenes, modelo, tamaño de resize
- [x] `src/antcollect/db.py`: conexión SQLite + esquema (tabla `monedas` + `idx_tipo`) + `transaccion()`
- [x] Carpeta `imagenes/` creada en runtime si no existe
- [x] `src/antcollect/ui/app.py`: Gradio arranca, pantalla de inicio con los 2 botones grandes
- [x] `README.md` inicial: instalar, configurar clave, arrancar en escritorio, abrir desde móvil, backup
- [x] `ruff` y `pytest` configurados; `uv run pytest` pasa (2 tests)
- [x] `[tool.uv] system-certs = true` (el entorno usa un proxy TLS con CA propia)

**Sale usable:** la app abre en el navegador y muestra la pantalla de inicio.

---

## Fase 1 — Núcleo de datos + CRUD manual  ·  rama `feat/fase-1-crud`  ·  ✅ completada

Cubre: RF-6, RF-7, RF-9, RF-10, RF-11, RF-12, RF-14. Sin IA.

- [x] `modelo.py`: dataclass `Moneda`
- [x] `normalizacion.py`: minúsculas + sin acentos + espacios colapsados para `pais`/`ceca`/`variante`; `NULL`→`''` en `ceca`/`variante`; forma canónica de `valor` (`valor_texto` para mostrar, `valor_norm` para comparar); `anio` entero o `NULL`. Tests.
- [x] `coleccion.py`: alta, edición, borrado (con confirmación), búsqueda de texto, filtro por país/valor/año
- [x] Detección de duplicados (RF-14): al dar de alta, si ya existe un tipo con los mismos campos normalizados → aviso antes de crear. Tests (exacto / parcial / distinto).
- [x] `imagenes.py`: guardar anverso y reverso (ambos opcionales), nombres derivados del `id`, redimensionado razonable para almacenamiento
- [x] UI: formulario de alta/edición manual con todos los campos
- [x] UI: listado/galería de la colección con filtros y búsqueda (RF-9)
- [x] UI: ficha de detalle de un tipo (RF-10) — campos, fotos, notas, estado
- [x] UI: borrar con confirmación (RF-11)
- [x] Campos libres: notas y `estado` (RF-12)

**Sale usable:** catálogo manual completo y consultable. Ya tiene valor real.
Probado en navegador con Playwright contra el servidor real: alta con/sin
foto, año en blanco, aviso de duplicado, edición y borrado con confirmación.

---

## Fase 2 — Lectura por IA (`CoinReader`)  ·  rama `feat/fase-2-coinreader`  ·  ✅ completada

Cubre: RF-1, RF-3, RF-7 (lectura con 2 fotos), RNF-4, RNF-6.
**Antes de codificar: confirmar id de modelo y API de visión/tool use en https://docs.claude.com.**
Confirmado: `claude-sonnet-5` es el id vigente (1M contexto, tool use estándar); se mantiene como modelo por defecto.

- [x] `ai/base.py`: `CoinReader` (ABC) + `LecturaMoneda` (dataclass con `campos_dudosos`)
- [x] `ai/claude.py`: `ClaudeCoinReader`
  - [x] redimensionar con Pillow antes de enviar (lado largo ~1568 px)
  - [x] imágenes base64 antes del texto en el mensaje
  - [x] `tool use` con esquema = 5 campos + `campos_dudosos`
  - [x] prompt de sistema: no inventar, `null` + `campos_dudosos` si ilegible, año 4 cifras o `null`, usar anverso+reverso
  - [x] manejo de errores → lectura fallida, sin excepción al usuario, log en `antcollect.log`
- [x] Registro discreto de coste/errores por llamada
- [x] Pipeline compartido **capturar → leer → confirmar** (formulario de la Fase 1 reutilizado tal cual)
- [x] Flujo "Enseñar moneda nueva" (RF-1): sube foto(s) → `CoinReader.leer()` → formulario **prerrellenado** con `campos_dudosos` resaltados → usuario confirma/corrige → aviso de duplicado (RF-14, ya cubierto por `coleccion.crear`) → guardar
- [x] Degradación: sin red / error → UI informa y ofrece modo manual (RF-6)
- [x] Tests: parseo de respuesta IA, mapeo a `LecturaMoneda`, camino de error

**Sale usable:** enseñar monedas con foto + lectura asistida y confirmación humana.
Probado en navegador con Playwright contra el servidor real: sin foto (aviso),
con clave de API inválida (degrada a manual con todos los campos resaltados),
"prefiero rellenarlo a mano", cancelar captura, y sin `ANTHROPIC_API_KEY`
configurada (va directo al formulario en blanco).

---

## Fase 3 — Comprobar "¿La tengo?"  ·  rama `feat/fase-3-comprobar`  ·  ✅ completada

Cubre: RF-2, RF-4, RF-5. Reutiliza el pipeline de la Fase 2.

- [x] Flujo "¿La tengo?": captura/sube foto(s) → `CoinReader.leer()` → campos propuestos, dudosos resaltados → usuario ajusta
- [x] Consulta por campos normalizados en `coleccion.py` (`comprobar_tipo`):
  - [x] Coincidencia exacta (5 campos) → "✅ Ya la tienes" + ficha guardada con foto al lado de la recién capturada (RF-4)
  - [x] Sin coincidencia → "🆕 No la tienes" + botón "Guardar esta" que reutiliza los campos leídos (RF-5)
  - [x] Coincidencia parcial (mismo país+valor+año, distinta ceca/variante) o `anio` NULL o campo dudoso → "posible coincidencia", decide el humano
- [x] Tests de la lógica de coincidencia: exacta / parcial / sin coincidencia / `anio` NULL no da falso positivo

**Sale usable:** el objetivo central de la app funciona de principio a fin.
Probado en navegador con Playwright contra el servidor real (sin
`ANTHROPIC_API_KEY`, modo manual directo al formulario "¿La tengo?"): ya la
tienes (con comparación de fotos y "ver ficha completa"), posible coincidencia
(distinta ceca, con selector para ver el candidato), sin coincidencia seguido
de "guardar esta como nueva", y que "Editar" desde una ficha resetea el modo
del formulario a "Guardar" (no se queda en "Buscar").

---

## Fase 4 — Captura y modos  ·  rama `feat/fase-4-captura`

Cubre: RF-8, §9.3 del doc.

- [ ] Selección de fuente de cámara cuando hay varias (webcam normal vs microscopio Jiusion UVC) en escritorio
- [ ] Modo *completa* (foto entera → es la que va a la IA) y modo *detalle/macro* (microscopio → apoyo humano para cecas/variantes; opcional guardar como imágenes adicionales)
- [ ] Captura desde la cámara del móvil (`<input capture>` / widget de Gradio)
- [ ] No permitir un macro extremo como única entrada de la IA

**Sale usable:** captura directa sin depender de subir archivos a mano.

---

## Fase 5 — Pulido  ·  rama `feat/fase-5-pulido`

Cubre: RF-13, §10, retoques de RF-12 y textos.

- [ ] Responsive / móvil: botones grandes, formularios usables con el pulgar, los 2 botones como pantalla de inicio
- [ ] Exportación de la colección a CSV y JSON (RF-13)
- [ ] Backup de imágenes documentado; formato portable; restauración manual (copiar carpeta) documentada
- [ ] Estados de colección ("en colección" / "duplicada" / "para intercambio")
- [ ] Repaso de todos los textos de UI: lenguaje de "propuesta", nunca "resultado definitivo"
- [ ] README completo y verificado

**Sale usable:** v1 lista.

---

## Futuro (fuera de v1 — §12 del doc, no cerrar puertas)

- Red de seguridad por similitud visual (embeddings CLIP/DINOv2). Dejar sitio en el modelo de datos para una tabla/campo de embeddings por imagen.
- Lectura por IA local (sustituir adaptador de `CoinReader`).
- App móvil nativa / PWA + sincronización móvil↔escritorio.
- Catálogos numismáticos externos para autocompletar.
- Estados de colección más ricos (wishlist).

---

## Registro de decisiones

| Fecha | Decisión | Dónde queda documentada |
|---|---|---|
| 2026-09-04 | UI: Gradio | CLAUDE.md §4, README |
| 2026-09-04 | `ceca`/`variante`: `NULL`→`''`; `anio`: `NULL` real | CLAUDE.md §4, README |
| 2026-09-04 | Modelo IA por defecto: `claude-sonnet-5` (confirmar id al llegar a Fase 2) | CLAUDE.md §4, README |
| 2026-09-04 | Orden de fases: IA adelantada a Fase 2 | este archivo |
| 2026-09-04 | Git: rama por fase + PR, Conventional Commits en español | CLAUDE.md §8 |
| 2026-09-04 | Repo: github.com/antonyga/antcollect, público | CLAUDE.md §8 |
| 2026-09-04 | Modelo IA confirmado: `claude-sonnet-5` sigue vigente | CLAUDE.md §4, PLAN.md Fase 2 |
