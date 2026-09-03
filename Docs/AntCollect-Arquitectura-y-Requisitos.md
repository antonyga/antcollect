# AntCollect — Documento de Arquitectura y Requisitos

> **Propósito de este documento.** Especificación funcional y técnica de *AntCollect*, una aplicación personal para catalogar una colección de monedas y comprobar, con ayuda de IA de visión, si una moneda encontrada ya está en la colección. Está escrito para servir de entrada a **Claude Code**: define *qué* construir y *cómo* montarlo, dejando margen razonable en los detalles de implementación.
>
> **Autor/usuario:** un único coleccionista (uso personal, sin multiusuario).
> **Estado:** v1 — lectura por IA desde el inicio.

---

## 1. Visión del producto

AntCollect resuelve un problema concreto: *"me encuentro una moneda en la calle y no sé si ya la tengo"*. El usuario fotografía la moneda, la IA lee sus atributos, y la app responde de forma fiable **tengo / no tengo**, mostrando la ficha guardada para que el usuario confirme con su propio ojo.

El segundo flujo es enseñarle monedas nuevas a la app, que consiste en el mismo proceso de captura + lectura, terminando en "guardar" en lugar de "consultar".

### Principio de diseño rector

**La máquina propone, el humano dispone.** La IA nunca guarda ni decide sola. Lee los atributos y los propone; el usuario los confirma o corrige antes de que nada se escriba en la base de datos. Todo el diseño gira en torno a esto para evitar una colección contaminada con años o cecas mal leídos.

### Qué NO es AntCollect (no-objetivos de la v1)

- No es un clasificador entrenado. No hay entrenamiento de modelos ni reentrenar al añadir monedas.
- No cataloga por ejemplar físico individual (grado, desgaste concreto de *esta* pieza). Cataloga por **tipo**.
- No es multiusuario, no tiene cuentas, no tiene sincronización en la nube en v1.
- No valora monedas ni consulta precios de mercado.

---

## 2. Modelo de dominio

### 2.1 Concepto central: el "tipo"

La unidad de colección es el **tipo**, definido por la combinación de:

| Campo | Descripción | Ejemplo |
|---|---|---|
| `pais` | País o entidad emisora | España |
| `valor` | Denominación / valor facial | 2 euros |
| `anio` | Año de acuñación | 2002 |
| `ceca` | Marca de ceca / casa de moneda | (a veces vacío) |
| `variante` | Distintivo opcional cuando los 4 anteriores coinciden pero hay una diferencia relevante (conmemorativa, error de cuño, leyenda distinta) | "conmemorativa Grimaldi" |

**Regla de identidad:** dos monedas son "el mismo tipo" si coinciden `pais` + `valor` + `anio` + `ceca` + `variante`. La comprobación "¿la tengo?" es, por tanto, una consulta exacta sobre estos campos — no una comparación de imágenes. Esto es lo que hace la respuesta fiable.

> **Nota sobre "fijarse en los detalles":** el usuario colecciona por tipo, pero le importan los detalles finos (que un 2002 no se cuele como 2003, que una ceca no se confunda). Esos detalles *son* precisamente los campos `anio` y `ceca`. "Fijarse en los detalles" se traduce en **leer bien esos campos y forzar confirmación humana**, no en comparar píxeles.

### 2.2 Normalización

Para que la comparación exacta funcione, los campos deben normalizarse antes de guardar y antes de consultar:

- `pais`, `ceca`, `variante`: minúsculas, sin acentos para la comparación (guardar también la versión "bonita" para mostrar), espacios colapsados.
- `valor`: normalizar a una forma canónica (p. ej. guardar `valor_texto` = "2 euros" para mostrar y `valor_normalizado` para comparar). Considerar separar en `valor_num` + `moneda`/`unidad` si se quiere robustez.
- `anio`: entero. Permitir `NULL`/desconocido (monedas sin año visible o ilegible).
- La app debe **detectar duplicados por los campos normalizados**, no por el texto crudo.

---

## 3. Requisitos funcionales

Identificadores `RF-n` para que Claude Code pueda referenciarlos.

- **RF-1 — Enseñar moneda nueva.** El usuario captura/sube foto(s) de una moneda; la IA propone los campos del tipo; el usuario los edita; la app guarda el tipo con sus imágenes.
- **RF-2 — Comprobar moneda encontrada.** El usuario captura/sube foto(s); la IA propone los campos; el usuario los ajusta; la app consulta la base y responde **tengo / no tengo**.
- **RF-3 — Confirmación obligatoria.** Ningún registro se escribe sin un paso explícito de confirmación del usuario sobre los campos leídos.
- **RF-4 — Ver coincidencia con imagen.** Cuando la app dice "ya la tienes", muestra la ficha guardada (con su foto) junto a la foto recién capturada, para verificación visual humana.
- **RF-5 — Guardar desde comprobación.** Si el resultado de RF-2 es "no la tienes", un botón permite guardarla directamente sin repetir la captura ni la lectura.
- **RF-6 — Entrada manual y edición.** El usuario puede rellenar/editar todos los campos a mano (sin IA) y editar cualquier ficha existente después.
- **RF-7 — Dos fotos por moneda.** Soporte para anverso y reverso (ambos opcionales pero recomendados). La lectura de IA debe poder usar ambas.
- **RF-8 — Dos modos de captura.** "Moneda completa" (para identificar) y "detalle/macro" (microscopio, para cecas/variantes). Ver §9.
- **RF-9 — Listado y búsqueda.** Ver toda la colección en una lista/galería, con filtro por país, valor y año, y búsqueda de texto.
- **RF-10 — Ficha de moneda.** Vista de detalle de un tipo con todos sus campos, fotos y notas.
- **RF-11 — Borrar / archivar.** Eliminar un tipo (con confirmación).
- **RF-12 — Campos libres.** Notas de texto libre y campo de estado (p. ej. "en colección", "duplicada", "para intercambio").
- **RF-13 — Copia de seguridad / exportación.** Exportar la colección (CSV/JSON) y respaldar imágenes. La restauración puede ser manual en v1 (copiar carpeta), pero el formato debe ser portable.
- **RF-14 — Aviso de posible duplicado al enseñar.** Al guardar un tipo nuevo, si ya existe uno con los mismos campos normalizados, avisar antes de crear un duplicado.

---

## 4. Requisitos no funcionales

- **RNF-1 — Un solo código, dos plataformas.** Arrancar en escritorio, pero la arquitectura debe permitir usar la misma app desde el navegador del móvil sin reescribir. Ver §5 y §10.
- **RNF-2 — Datos locales y portables.** Toda la información vive en el equipo del usuario: una base de datos de archivo (SQLite) + una carpeta de imágenes. Respaldar = copiar esos ficheros.
- **RNF-3 — Sin dependencia dura de internet salvo para la lectura IA.** La app debe funcionar (catalogar, consultar, editar) sin conexión; solo el paso de lectura automática requiere red. Si no hay red, se cae con elegancia al modo manual (RF-6).
- **RNF-4 — Coste controlado.** El paso de IA es de pago por consulta (céntimos). La app debe minimizar tokens (redimensionar imágenes antes de enviar) y no llamar a la IA salvo cuando el usuario lo pide.
- **RNF-5 — Clave de API fuera del código.** La clave de la API se lee de variable de entorno o fichero de configuración local, nunca hardcodeada ni subida a control de versiones.
- **RNF-6 — Proveedor de IA desacoplado.** La lógica de lectura vive detrás de una interfaz (`CoinReader`) para poder cambiar de proveedor o pasar a un modelo local en el futuro sin tocar el resto.
- **RNF-7 — Robustez de datos.** Nunca corromper la base por un fallo de IA o de red. Las escrituras son transaccionales y siempre posteriores a la confirmación humana.
- **RNF-8 — Simplicidad.** Es una app de un usuario. Evitar sobreingeniería: nada de colas, microservicios, ORM pesados ni autenticación.

---

## 5. Arquitectura

Arquitectura de **app web local**: un backend ligero que sirve una interfaz web en `localhost`. En escritorio se abre en el navegador (o en una ventana dedicada); desde el móvil, en la misma red wifi, se abre por la IP local. Un único código base cubre ambos (satisface RNF-1).

```
┌──────────────────────────────────────────────────────────┐
│                    Interfaz (navegador)                    │
│     Escritorio (localhost)   ·   Móvil (IP local, wifi)    │
│   Captura/subida de fotos · formularios · listado · ficha  │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP local
┌───────────────────────────┴──────────────────────────────┐
│                        Backend                            │
│                                                           │
│   ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │
│   │  Rutas /    │  │  Servicio de │  │   CoinReader   │   │
│   │  controlad. │──│  colección   │  │  (interfaz IA) │   │
│   └─────────────┘  └──────┬───────┘  └───────┬────────┘   │
│                           │                  │            │
│                    ┌──────┴──────┐    ┌───────┴────────┐   │
│                    │  SQLite     │    │ Adaptador API  │   │
│                    │  (datos)    │    │  Claude visión │   │
│                    └─────────────┘    └───────┬────────┘   │
│                    ┌─────────────┐            │            │
│                    │  Carpeta    │            │            │
│                    │  imágenes   │            ▼            │
│                    └─────────────┘   (red, solo al leer)   │
└──────────────────────────────────────────────────────────┘
```

### Componentes

- **Interfaz.** Páginas para los dos flujos (enseñar / comprobar), listado, ficha y ajustes. Debe funcionar con subida de archivo *y* con cámara del dispositivo (el `<input type="file" accept="image/*" capture>` de HTML permite usar la cámara del móvil directamente).
- **Servicio de colección.** Lógica de negocio: normalización, alta, edición, borrado, búsqueda, detección de duplicados (RF-14), consulta "¿la tengo?" (RF-2).
- **CoinReader (interfaz de IA).** Contrato único: recibe una o dos imágenes y devuelve un objeto con los campos propuestos + un indicador de confianza + campos que la IA marca como dudosos. Implementación por defecto: adaptador de la API de Claude (§8). Sustituible (RNF-6).
- **Persistencia.** SQLite para datos; sistema de ficheros para imágenes. Sin servidor de base de datos.

---

## 6. Stack tecnológico recomendado

Recomendación por defecto (Claude Code puede proponer alternativas equivalentes si lo justifica):

- **Lenguaje/back:** Python. Es el camino más corto para hablar con APIs de visión y tiene buenas librerías de imagen.
- **Interfaz:**
  - **Opción rápida (recomendada para v1):** *Gradio* o *Streamlit*. Dan subida de imágenes, webcam y formularios con muy poco código; ideal para un solo usuario y para tener el esqueleto vivo pronto.
  - **Opción a medida (si se quiere control fino de UI/UX o preparar mejor el móvil):** *FastAPI* + frontend web sencillo (HTML/JS, o un framework ligero). Más trabajo, más flexibilidad.
  - Empezar por la opción rápida y migrar solo si la UI se queda corta.
- **Base de datos:** SQLite (módulo estándar de Python o una capa fina encima).
- **Imágenes:** Pillow para redimensionar/normalizar antes de enviar a la IA (RNF-4).
- **Cliente de IA:** SDK oficial de Anthropic para Python (`anthropic`).
- **Config:** variables de entorno (`.env` con `python-dotenv`), fuera de git.

> **Decisión abierta para Claude Code:** elegir entre Gradio/Streamlit y FastAPI. Recomendación: **empezar con Gradio o Streamlit**. Documentar la elección en el README.

---

## 7. Modelo de datos

### 7.1 Esquema SQLite (orientativo)

```sql
CREATE TABLE monedas (
    id              INTEGER PRIMARY KEY,
    pais            TEXT NOT NULL,
    valor_texto     TEXT NOT NULL,     -- para mostrar: "2 euros"
    anio            INTEGER,           -- NULL si desconocido/ilegible
    ceca            TEXT,              -- puede ser NULL/vacío
    variante        TEXT,              -- opcional
    notas           TEXT,
    estado          TEXT DEFAULT 'en_coleccion',
    foto_anverso    TEXT,              -- ruta relativa a la carpeta de imágenes
    foto_reverso    TEXT,
    fecha_agregada  TEXT NOT NULL,     -- ISO 8601

    -- columnas normalizadas para comparación exacta (RF-2, RF-14)
    pais_norm       TEXT NOT NULL,
    valor_norm      TEXT NOT NULL,
    ceca_norm       TEXT,
    variante_norm   TEXT
);

-- La identidad de "tipo" (evita duplicados exactos, RF-14)
CREATE UNIQUE INDEX idx_tipo
    ON monedas (pais_norm, valor_norm, anio, ceca_norm, variante_norm);
```

> Nota: con `UNIQUE` sobre columnas que admiten `NULL`, SQLite trata cada `NULL` como distinto. Si se quiere que "ceca vacía" cuente como un único valor a efectos de unicidad, normalizar `NULL` a cadena vacía `''` antes de guardar. Definir esta política explícitamente.

### 7.2 Estructura de ficheros

```
antcollect/
├── antcollect.db            # base de datos SQLite
├── imagenes/                # una subcarpeta o convención de nombres por moneda
│   ├── 0001_anverso.jpg
│   ├── 0001_reverso.jpg
│   └── ...
├── .env                     # ANTHROPIC_API_KEY, NO se sube a git
├── config....               # ajustes (modelo, tamaños, etc.)
└── (código de la app)
```

- Guardar las imágenes con nombres derivados del `id` para trazabilidad.
- Backup (RF-13) = copiar `antcollect.db` + carpeta `imagenes/`.

---

## 8. Módulo de IA — `CoinReader`

Este es el corazón técnico. Su trabajo: **de imagen(es) → campos del tipo, con honestidad sobre la incertidumbre.**

### 8.1 Contrato

```
CoinReader.leer(imagen_anverso, imagen_reverso=None) -> LecturaMoneda
```

`LecturaMoneda` incluye: `pais`, `valor`, `anio`, `ceca`, `variante`, y por cada campo un nivel de confianza o una lista de `campos_dudosos` que la IA no pudo leer con seguridad. Esto permite a la interfaz **resaltar en la UI lo que conviene que el humano revise** (por ejemplo, un año borroso), enlazando directamente con el principio "la máquina propone, el humano dispone".

### 8.2 Implementación por defecto: API de Claude (visión)

Detalles verificados en la documentación de Anthropic:

- **Todos los modelos actuales de Claude admiten entrada de imagen (visión).** Para este caso conviene un modelo con buena lectura de texto pequeño pero coste contenido.
  - **Recomendado por equilibrio:** un modelo Sonnet actual (p. ej. `claude-sonnet-5`) por su buena lectura de detalle a coste razonable.
  - **Alternativa más barata:** un modelo Haiku actual (p. ej. `claude-haiku-4-5`) si el volumen de consultas crece y la precisión resulta suficiente.
  - Poner el nombre del modelo en configuración (no hardcodeado) y **que Claude Code confirme el identificador de modelo vigente en la documentación** al construir, porque los nombres evolucionan.
- **Formato de imagen:** enviar como bloque de imagen base64 (o vía Files API si se reutiliza mucho). JPEG/PNG/WebP/GIF admitidos.
- **Orden:** colocar la(s) imagen(es) **antes** del texto en el mensaje; Claude rinde mejor con estructura imagen-luego-texto.
- **Tamaño / coste (RNF-4):** redimensionar antes de enviar. Si el lado largo supera ~1568 px, el servicio lo reescala igualmente sin ganancia de calidad, así que **redimensionar en cliente** para ahorrar tokens y latencia. Redimensionar a ese orden de magnitud es un buen punto de partida.
- **Salida estructurada fiable:** usar **tool use / herramientas** para forzar que el modelo devuelva los campos como un objeto estructurado (definir una "herramienta" cuyo esquema de entrada sean exactamente los campos del tipo + `campos_dudosos`). Es más robusto que pedir "devuélveme JSON" en texto libre y parsear a mano. Alternativa aceptable: pedir JSON estricto en el prompt y parsear con manejo de errores.

### 8.3 Prompt (guía de contenido)

El prompt del sistema debe pedir explícitamente:

- Extraer **solo** lo que se ve en la moneda: país/emisor, valor facial, año, marca de ceca, y cualquier rasgo de variante evidente (conmemorativa, leyenda).
- **No inventar.** Si un campo no es legible, devolverlo vacío/`null` y añadirlo a `campos_dudosos`. Es preferible un hueco honesto a un año inventado.
- Cuando haya dos imágenes (anverso/reverso), usarlas de forma complementaria.
- Devolver el año como número de 4 cifras o `null`.

### 8.4 Manejo de errores y degradación

- Sin red / error de API / timeout → la app **no falla**: informa y ofrece el modo manual (RF-6, RNF-3).
- Respuesta no parseable → tratar como lectura fallida y pasar a manual.
- Coste/errores registrados de forma discreta (log local) para diagnóstico.

---

## 9. Flujos principales

### 9.1 Enseñar moneda nueva (RF-1)

1. Usuario pulsa **"Enseñar moneda nueva"**.
2. Captura o sube foto de anverso (y opcionalmente reverso). Puede elegir modo *completa* o *detalle* (§9.3 / §... captura).
3. App redimensiona y llama a `CoinReader.leer(...)`.
4. La UI muestra un formulario **prerrellenado** con los campos propuestos; los `campos_dudosos` aparecen resaltados.
5. Usuario **confirma o corrige** (aquí es donde puede usar el microscopio para leer una ceca o un año dudoso).
6. Al guardar, si ya existe un tipo idéntico (campos normalizados) → **aviso de duplicado** (RF-14): permitir cancelar, o guardar como variante.
7. Se persiste el registro + las imágenes.

### 9.2 Comprobar moneda encontrada (RF-2)

1. Usuario pulsa **"¿La tengo?"**.
2. Captura/sube foto(s).
3. App llama a `CoinReader.leer(...)`.
4. UI muestra los campos propuestos, resaltando dudosos; usuario **ajusta si hace falta**.
5. App consulta la base por campos normalizados:
   - **Coincidencia exacta →** "✅ Ya la tienes", mostrando la ficha guardada + foto junto a la recién capturada (RF-4). Verificación visual humana.
   - **Sin coincidencia →** "🆕 No la tienes", con botón **"Guardar esta"** (RF-5) que reutiliza los campos ya leídos.
   - **Coincidencia parcial** (mismo país+valor+año pero distinta ceca/variante, o algún campo dudoso) → mostrarla como **"posible coincidencia"** y dejar que el humano decida. Este caso es importante: cubre justo los "detalles" que le importan al usuario.

> Observación de diseño: enseñar y comprobar son **el mismo flujo** (capturar → leer → confirmar) con distinto final (guardar / consultar). Implementarlo así reduce código y bugs.

### 9.3 Captura de imagen

- **Escritorio + microscopio Jiusion:** el Jiusion es en esencia una webcam USB (UVC), así que la app puede leerlo como una fuente de cámara más. Permitir elegir qué cámara usar cuando haya varias (webcam normal vs. microscopio).
- **Móvil:** usar la cámara del teléfono (el microscopio USB en Android depende de OTG/UVC y es poco fiable; no asumirlo en v1).
- **Dos modos (RF-8):**
  - *Completa:* foto del anverso/reverso enteros → es la que se envía a la IA para **identificar**.
  - *Detalle/macro:* primeros planos (microscopio) para leer cecas, variantes o errores → apoyo para que el humano confirme campos dudosos; opcionalmente también se pueden guardar como imágenes adicionales de la ficha.
- La foto "completa" es la fuente de verdad para la lectura; el "detalle" es ayuda humana. No mezclar un macro extremo como única entrada de la IA (puede no verse la moneda entera).

---

## 10. Camino a móvil

- Al ser web local, el móvil ya puede usar la app desde el navegador (misma wifi, IP local). Eso cubre RNF-1 sin segunda base de código.
- Requisitos para que funcione bien en móvil desde el principio:
  - Interfaz **responsive** (botones grandes, formularios usables con el pulgar).
  - Captura con la cámara del teléfono vía `<input capture>` o el widget de cámara del framework.
  - Los dos botones grandes ("Enseñar" / "¿La tengo?") como pantalla de inicio.
- Empaquetado como app instalable (PWA) o app nativa: **fuera de alcance de v1**, anotado como evolución futura.
- Consideración de datos: en v1 los datos viven en el equipo de escritorio. Acceder desde el móvil implica que el escritorio esté encendido y sirviendo. Sincronización real móvil↔escritorio es trabajo futuro (ver §12).

---

## 11. Casos borde y reglas

- **Año ilegible / ausente:** permitir `anio = NULL`; en la comparación, un año nulo no debe dar falsos positivos de "ya la tienes". Tratar como "posible coincidencia" a revisar.
- **Ceca vacía:** decidir y documentar si `NULL` y `''` son el mismo valor a efectos de unicidad (§7.1).
- **Moneda no reconocida / la IA falla:** siempre hay salida manual.
- **Duplicado exacto al enseñar:** avisar (RF-14), no crear silenciosamente.
- **Dos tipos casi iguales** (mismo país/valor/año, distinta ceca o variante): son **tipos distintos**; la app no debe fusionarlos. Este es el corazón del "fíjate en los detalles".
- **Fotos de baja calidad / mala luz:** asumir que la lectura fallará a veces; el diseño lo tolera porque el humano confirma. No presentar la lectura de IA como verdad absoluta en la UI (lenguaje tipo "propuesta", no "resultado definitivo").
- **Imágenes muy grandes:** redimensionar siempre antes de enviar (coste/latencia).

---

## 12. Extensiones futuras (fuera de v1, anotadas para no cerrar puertas)

- **Red de seguridad por similitud visual (embeddings).** Guardar un vector por imagen (modelo tipo CLIP/DINOv2) para avisos del tipo *"dices que es nueva pero se parece muchísimo a esta que ya tienes — ¿seguro que no es la misma con el año mal leído?"*. Es un **extra** que atrapa errores de lectura, no el mecanismo principal. Diseñar la tabla de imágenes dejando sitio para un campo/tabla de embeddings.
- **Lectura por IA local** (modelo de visión en el equipo): privacidad total y sin coste por consulta, a cambio de más montaje y hoy peor lectura de detalle. Gracias a la interfaz `CoinReader` (RNF-6) sería sustituir un adaptador.
- **App móvil nativa / PWA + sincronización** de datos móvil↔escritorio.
- **Catálogos externos** (autocompletar país/valor/año a partir de una base de referencia numismática) — mejoraría la precisión más allá de la lectura visual.
- **Estados de colección más ricos** (duplicadas para intercambio, wishlist).

---

## 13. Plan de construcción por hitos (para Claude Code)

Construir de forma incremental, con esqueleto vivo cuanto antes:

- **Hito 0 — Esqueleto.** Proyecto, dependencias, base SQLite con el esquema, carpeta de imágenes, config con clave de API fuera de git. App arranca y sirve una página vacía.
- **Hito 1 — CRUD manual (sin IA).** Alta/edición/borrado de monedas a mano (RF-6, RF-10, RF-11), listado y búsqueda (RF-9), guardado de imágenes (RF-7), normalización + detección de duplicados (RF-14). *En este punto ya es un catálogo consultable útil.*
- **Hito 2 — Comprobación por campos.** Flujo "¿La tengo?" consultando la base con los campos introducidos a mano (RF-2, RF-4), incluidas coincidencias parciales. Sin IA todavía.
- **Hito 3 — Lectura por IA.** Implementar `CoinReader` con el adaptador de la API de Claude (§8): visión + salida estructurada + `campos_dudosos`, redimensionado previo, manejo de errores con degradación a manual. Enchufarlo en los flujos de enseñar (RF-1) y comprobar (RF-2), con formulario prerrellenado y confirmación (RF-3).
- **Hito 4 — Captura y modos.** Cámara/webcam, selección de fuente (incluida la Jiusion en escritorio), modos completa/detalle (RF-8), captura desde móvil.
- **Hito 5 — Pulido.** Responsive/móvil (§10), exportación y backup (RF-13), estados y notas (RF-12), mensajes de UI que dejen claro que la IA "propone".
- **Futuro.** Lo de §12 según interese.

> Cada hito debe dejar la app en estado usable y con datos a salvo. Priorizar Hitos 0–2 para tener valor real antes de tocar la IA.

---

## 14. Notas para Claude Code

- **Este documento describe el *qué* y el *cómo* de alto nivel.** Tienes libertad en los detalles de implementación siempre que respetes los requisitos `RF-*` / `RNF-*` y el principio rector (§1).
- **Confirma en la documentación oficial** el identificador de modelo de visión vigente y la forma exacta de la API de imágenes/tool use antes de codificar el Hito 3 (los nombres y detalles evolucionan): docs de la API de Claude en `https://docs.claude.com`.
- **Decisiones que debes tomar y documentar en el README:** framework de UI elegido (Gradio/Streamlit vs FastAPI), política de `NULL` vs `''` en unicidad, y modelo de IA por defecto.
- **No hardcodees la clave de API.** Léela de entorno/config y añade `.env` e `imagenes/` al `.gitignore`.
- **Mantén `CoinReader` detrás de una interfaz** para poder cambiar a IA local en el futuro sin refactorizar el resto.
- **Escribe un README** con: cómo instalar, cómo configurar la clave, cómo arrancar en escritorio, cómo abrir desde el móvil (IP local), y cómo hacer backup.
```
