# AntCollect Móvil — Ficha y cumplimiento en las tiendas

> Respuestas preparadas para rellenar App Store Connect y Google Play Console
> (Fase M5, RNF-M3). Se derivan del código tal como está en la rama
> `feat/fase-m5-cumplimiento`; si cambia lo que se recoge o a quién se envía,
> hay que actualizar a la vez este documento, la política de privacidad
> (`backend/app/legal/privacidad.html`) y los formularios de las dos tiendas.

---

## 1. URLs que piden las tiendas

Las sirve el propio backend. Con el dominio de producción (pendiente del
despliegue en Railway) quedarán así:

| Para qué | URL | Dónde se pega |
|---|---|---|
| Política de privacidad | `https://<dominio>/privacidad` | App Store Connect → App Privacy; Play Console → Contenido de la app → Política de privacidad |
| Términos del servicio | `https://<dominio>/terminos` | App Store Connect → licencia/EULA personalizada (opcional); descripción de la ficha |
| Borrar la cuenta sin la app | `https://<dominio>/borrar-cuenta` | Play Console → Seguridad de los datos → "Eliminación de cuenta" |

Antes de publicar, configurar en el backend `LEGAL_RESPONSABLE` (nombre o
razón social) y `LEGAL_CONTACTO` (email que aparecerá publicado). Sin ellos,
las páginas muestran a la vista "[… sin configurar]".

---

## 2. Qué datos trata la app (inventario)

| Dato | Para qué | Obligatorio | Dónde vive | Quién más lo recibe |
|---|---|---|---|---|
| Email | Cuenta (login) | Sí | BD del backend (Railway) | Nadie |
| Contraseña | Cuenta | Sí | Solo su hash bcrypt | Nadie |
| Id interno de usuario | Aislar los datos de cada cuenta | Sí | BD | Nadie |
| Datos de cada moneda (país, valor, año, ceca, variante, estado, notas) | La colección | Sí, si se usa la app | BD | Nadie |
| Fotos de monedas (sin EXIF ni GPS) | La colección | No (se puede catalogar sin fotos) | Bucket privado (Railway) | Anverso/reverso a Anthropic → OpenAI → DeepSeek **solo** al pulsar "Leer con IA", como encargados del tratamiento |
| Fecha/hora de cada lectura IA | Cuota diaria | Sí, si se usa la IA | BD | Nadie |
| IP y ruta de cada petición | Logs técnicos del servidor | — | Logs de Railway | Nadie |

**No** se recogen: nombre, ubicación (las fotos se guardan sin GPS y se piden
sin metadatos), contactos, identificadores publicitarios, analíticas, datos
de fallos (no hay SDK de crash reporting), historial de navegación ni
compras. No hay publicidad ni seguimiento (tracking).

---

## 3. Apple — App Privacy ("Etiquetas de privacidad")

App Store Connect → la app → **App Privacy** → *Get Started*.

**¿Recopilas datos de esta app?** Sí.

Marcar estos tipos y, en cada uno, responder:

| Tipo (Apple) | Uso | ¿Vinculado a la identidad? | ¿Para tracking? |
|---|---|---|---|
| Contact Info → **Email Address** | App Functionality | Sí | No |
| User Content → **Photos or Videos** | App Functionality | Sí | No |
| User Content → **Other User Content** (fichas de monedas y notas) | App Functionality | Sí | No |
| Identifiers → **User ID** | App Functionality | Sí | No |

No marcar: Location, Contacts, Health, Financial, Browsing/Search History,
Purchases, Usage Data, Diagnostics, Sensitive Info, Device ID.

Notas:
- Las fotos enviadas a la IA están cubiertas por "Photos or Videos" (Apple
  cuenta como recogido lo que va a socios externos; Anthropic, OpenAI y
  DeepSeek procesan por cuenta nuestra, no usan los datos para tracking).
- Los logs de IP del servidor no se usan para nada más que operar el
  servicio y no se vinculan a perfiles: Apple no exige declararlos.

**Otros apartados de App Store Connect:**
- **Borrado de cuenta (guideline 5.1.1(v))**: dentro de la app, menú de
  cuenta → *Mi cuenta* → *Borrar mi cuenta* (pide la contraseña y borra todo
  en el acto).
- **Sign in with Apple**: no hace falta; solo hay email/contraseña, sin
  login de terceros (guideline 4.8).
- **Cifrado de exportación**: `ITSAppUsesNonExemptEncryption = false` ya en
  `Info.plist` (solo HTTPS del sistema).
- **Clasificación por edad**: responder "Ninguno" a todo el cuestionario →
  **4+**. No hay contenido generado por usuarios visible para otros
  usuarios (cada colección es privada), ni web sin restricciones, ni chat.
- **Información para la revisión (App Review Information)**: la app exige
  iniciar sesión, así que hay que dar **una cuenta de demostración** con
  algunas monedas y fotos ya guardadas (email + contraseña) y una nota:
  > AntCollect cataloga una colección de monedas. Para probar la lectura con
  > IA: "¿La tengo?" o "Enseñar moneda nueva" → foto de una moneda → "Leer
  > con IA". La IA solo propone campos; el usuario los revisa antes de
  > guardar. El borrado de cuenta está en el icono de cuenta → Mi cuenta.

  Asegurarse de que esa cuenta tiene cuota de lecturas IA disponible el día
  de la revisión.

---

## 4. Google Play — Seguridad de los datos (Data safety)

Play Console → *Contenido de la app* → **Seguridad de los datos**.

**Recogida y compartición**
- ¿Recoge o comparte la app alguno de los tipos de datos obligatorios? **Sí**.
- ¿Todos los datos se cifran en tránsito? **Sí** (HTTPS; obligatorio en el
  backend desplegado).
- ¿Qué métodos de creación de cuenta ofrece? **Nombre de usuario (email) y
  contraseña**.
- URL para solicitar la eliminación de la cuenta: `https://<dominio>/borrar-cuenta`.
- ¿Se puede pedir que se eliminen algunos datos sin borrar la cuenta?
  **Sí**: cada moneda y cada foto se pueden borrar en la app.

**Tipos de datos** (para cada uno: *Recogido* sí, *Compartido* **no**: los
proveedores de IA y de alojamiento son proveedores de servicios que tratan
datos por cuenta nuestra, que Google excluye de "compartir"):

| Categoría → tipo | ¿Opcional? | Finalidad | ¿Efímero? |
|---|---|---|---|
| Información personal → **Dirección de correo electrónico** | No | Funcionalidad de la app; Gestión de la cuenta | No |
| Información personal → **ID de usuario** | No | Funcionalidad de la app; Gestión de la cuenta | No |
| Fotos y vídeos → **Fotos** | Sí | Funcionalidad de la app | No |
| Actividad en la app → **Otro contenido generado por el usuario** (fichas y notas) | No | Funcionalidad de la app | No |

No marcar: ubicación, mensajes, contactos, calendario, información
financiera, salud, archivos y documentos, audio, historial web, información
y rendimiento de la app (no hay crash reporting ni analíticas),
identificadores del dispositivo.

**Otros apartados de Contenido de la app:**
- **Acceso a la app**: "Todas o parte de las funciones están restringidas"
  → dar la misma cuenta de demostración que a Apple, con instrucciones.
- **Anuncios**: la app **no** contiene anuncios.
- **Clasificación de contenido (IARC)**: categoría "Utilidad, productividad,
  comunicación u otra"; responder no a violencia, sexo, lenguaje, drogas,
  apuestas; usuarios que interactúan entre sí: **no**; comparte la
  ubicación: **no** → resultado esperado PEGI 3 / Para todos.
- **Público objetivo**: 13+ (o 16+/18+); **no** marcar menores de 13, para no
  entrar en el programa de Familias. Coherente con la política ("no dirigida
  a menores de 14").
- **Aplicación de noticias / gubernamental / financiera / salud**: no.

---

## 5. Ficha de la tienda (borrador)

- **Nombre**: AntCollect
- **Subtítulo (Apple, 30 car.) / descripción breve (Google, 80 car.)**:
  "Cataloga tus monedas" / "Cataloga tu colección de monedas y comprueba al
  momento si ya la tienes."
- **Categoría**: Apple → *Estilo de vida* (secundaria *Referencia*);
  Google → *Estilo de vida*.
- **Descripción larga**:

  > ¿Te has encontrado una moneda y no sabes si ya la tienes? Hazle una foto
  > y AntCollect te lo dice.
  >
  > • **¿La tengo?** Fotografía la moneda y la app busca en tu colección por
  > país, valor, año, ceca y variante. Te dice si ya la tienes (con tu foto
  > al lado), si no la tienes o si tienes alguna parecida en la que fijarte.
  > • **Lectura con IA a petición.** La IA propone los datos que ve en la
  > moneda y te señala los que no ha leído con seguridad. Tú los revisas
  > siempre antes de guardar: nada entra en tu colección sin tu
  > confirmación.
  > • **Tu colección, en todos tus dispositivos.** Busca, filtra, edita y
  > añade fotos de anverso, reverso y detalle.
  > • **Tus datos son tuyos.** Exporta tu colección en CSV o JSON cuando
  > quieras. Sin publicidad y sin rastreo.
  >
  > Puedes rellenar los datos a mano en cualquier momento; la IA tiene un
  > límite diario de lecturas por cuenta.

- **Capturas**: hay que hacerlas en dispositivos o simuladores reales con
  los tamaños de cada tienda (iPhone 6,9" y 6,5"; teléfono Android). La
  vista web de Chrome sirve de borrador, pero Apple rechaza capturas que no
  muestren la app en el dispositivo.
- **Icono de la tienda**: `mobile/assets/icono/icono.png` (1024×1024, sin
  transparencia). Google pide además 512×512 (redimensionar el mismo) y un
  gráfico destacado de 1024×500.

---

## 6. Beta: TestFlight (iOS) y prueba interna (Android)

Lo que hace falta y quién lo hace. Nada de esto se puede hacer desde esta
máquina (Windows, sin Android SDK ni Xcode).

**Requisito previo común: backend desplegado con HTTPS.** Los testers usan
la app en sus teléfonos y necesitan un backend público. Pendiente desde M0:
Railway (Postgres + bucket + servicio) con `JWT_SECRET` aleatorio,
`ALMACEN=s3`, `LEGAL_*` y las claves de IA. La app se compila apuntando a él:
`--dart-define=ANTCOLLECT_API=https://<dominio>`.

**Android — prueba interna (Play Console)**
1. Instalar Android Studio (SDK + emulador + JDK compatible).
2. Crear la keystore de subida (una sola vez; guardarla fuera de git con
   copia de seguridad: perderla complica publicar actualizaciones) y
   configurar la firma de release en `android/app/build.gradle.kts` (hoy
   firma con la clave de debug). La prueba interna ya exige un `.aab`
   firmado, así que esto se adelanta de la Fase M6.
3. `flutter build appbundle --dart-define=ANTCOLLECT_API=https://<dominio>`.
4. Play Console → crear la app (`com.antonyga.antcollect`) → *Pruebas* →
   *Prueba interna* → subir el `.aab` → añadir los emails de los testers →
   compartir el enlace de inscripción.

**iOS — TestFlight**
1. Un Mac con Xcode (propio, alquilado en la nube, o un servicio de CI como
   Codemagic que compila iOS sin Mac propio).
2. App Store Connect → crear la app con el bundle id
   `com.antonyga.antcollect`.
3. `flutter build ipa --dart-define=ANTCOLLECT_API=https://<dominio>` y
   subirlo con Transporter o Xcode.
4. TestFlight → probadores internos (hasta 100, sin revisión de Apple) o
   externos (requiere una revisión beta ligera).
