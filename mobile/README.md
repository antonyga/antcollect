# AntCollect — app móvil (v2, Flutter)

App nativa (iOS + Android) de AntCollect, publicada en App Store y Play Store.
Habla con el backend en `../backend/` — no incluye lógica de IA ni acceso
directo a base de datos (eso vive en el backend, ver RNF-5/RNF-M1 del doc de
arquitectura).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

**Fase M4** — la app cubre el objetivo central de principio a fin:

- **Capturar → leer → confirmar**, un solo pipeline para los dos flujos de
  la v1 (`lib/captura/`): fotos de anverso, reverso y detalle con la cámara
  o la galería; lectura IA a petición (`POST /lecturas`); formulario de
  confirmación con los campos propuestos y los dudosos resaltados. Al final,
  **"Enseñar moneda nueva"** guarda y **"¿La tengo?"** consulta
  (`POST /coleccion/comprobar`): *Ya la tienes* (con tu foto al lado de la
  encontrada), *No la tienes* (con "Guardar esta") o *Posible coincidencia*
  (parecidas, señalando qué campo cambia; decide el usuario).
- Si la IA no puede leer, no hay red, no está configurada o se agotó la
  cuota del día, se pasa al mismo formulario a mano explicando por qué.
- Fotos también al editar una moneda (añadir, cambiar, quitar).
- Exportar la colección en CSV o JSON desde "Mi colección", con la hoja de
  compartir del sistema (en web, descarga).

De M3: cuenta (registro, inicio y cierre de sesión), listado con búsqueda y
filtros, ficha, edición y borrado con confirmación.

## Requisitos

- Flutter **3.47** (stable) — instalado en `C:\Users\Administrator\flutter`
  y añadido al PATH del usuario (abre una terminal nueva para que lo vea).
- Para Android: Android Studio (trae el SDK, el emulador y un JDK
  compatible). Para iOS: un Mac con Xcode. Sin ellos se puede desarrollar
  igualmente en Chrome (ver abajo).

## Arrancar en desarrollo

1. Backend local (desde `../backend/`):

   ```bash
   uv run alembic upgrade head
   uv run uvicorn app.main:app --port 8000
   ```

2. App:

   ```bash
   flutter pub get
   flutter run                      # emulador/dispositivo conectado
   ```

   Sin `--dart-define`, la app usa `http://10.0.2.2:8000` en el emulador de
   Android (es el PC anfitrión) y `http://localhost:8000` en iOS/web. Para
   otro backend (p. ej. el desplegado, o un móvil físico apuntando a la IP
   del PC en la misma wifi):

   ```bash
   flutter run --dart-define=ANTCOLLECT_API=http://192.168.1.50:8000
   ```

   Para un móvil físico el backend debe escuchar en todas las interfaces:
   `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.

   El tráfico `http://` sin cifrar solo está permitido en builds de debug
   (Android) y hacia la red local (iOS); el backend desplegado debe ir por
   `https://`.

### En el navegador (sin Android Studio)

```bash
# backend/.env (o entorno): CORS_ORIGENES=http://localhost:5000
flutter run -d chrome --web-port 5000
```

El navegador exige CORS; la app nativa no. Por eso el backend lo tiene
desactivado salvo que se configure `CORS_ORIGENES`.

## Calidad

```bash
flutter analyze        # lint (flutter_lints)
dart format lib test   # formato (ancho 100, en analysis_options.yaml)
flutter test           # tests
```

Los tests no necesitan backend: `test/backend_falso.dart` imita la API en
memoria (mismas rutas, códigos y JSON) y se enchufa como adaptador HTTP de
Dio, así que ejercitan el cliente real — cabeceras, renovación del token,
traducción de errores — además de las pantallas. La cámara y la hoja de
compartir se sustituyen por `test/dispositivo_falso.dart` (la app las usa a
través de la interfaz `Dispositivo`, `lib/captura/dispositivo.dart`).

## Estructura

```
mobile/
├── lib/
│   ├── main.dart        # arranque, URL del backend, tema, raíz según sesión
│   ├── api/             # ClienteApi (dio) + modelos espejo de backend/app/esquemas.py
│   ├── auth/            # sesión, tokens en almacenamiento seguro, pantalla de acceso
│   ├── inicio/          # pantalla de inicio (¿la tengo?, enseñar, colección)
│   ├── coleccion/       # listado + filtros + exportar, ficha, formulario (confirmar/editar)
│   ├── captura/         # pipeline: fotos, lectura IA, resultado "¿la tengo?", guardado
│   └── cuenta/          # (Fase M5) ajustes, borrar cuenta
└── test/
```

## Decisiones

- **Sin paquete de estado** (ni provider ni riverpod): un `ChangeNotifier`
  (`Sesion`) expuesto con un `InheritedNotifier` (`AmbitoSesion`). La
  colección no se cachea: cada pantalla la pide al backend (RF-M2, app
  "online" — ver doc de arquitectura §1).
- **Sin router**: `Navigator` con `MaterialPageRoute`. Al cerrar sesión o
  caducar, se descartan las pantallas abiertas y la raíz muestra el acceso.
- **Tokens** en `flutter_secure_storage` (Keychain / Keystore). El cliente
  renueva el access token con el refresh token ante un 401, una sola vez
  aunque fallen varias peticiones a la vez; si el refresco también falla,
  cierra la sesión.
- **Fotos** descargadas a través del backend con el token (el bucket es
  privado), con una pequeña caché en memoria.
- **Identificador de la app**: `com.antonyga.antcollect` (Android
  `applicationId` e iOS bundle id). Es el que verán las tiendas; cambiarlo
  después de publicar no es posible sin crear otra ficha.
- **Cámara con `image_picker`** (cámara nativa del sistema, no un visor
  propio): sin selector de dispositivo USB ni modo microscopio — el detalle
  es una foto más de cerca con la cámara trasera (doc de arquitectura §8) y
  **nunca se envía a la IA** (RF-8). Las fotos se reducen en el teléfono a
  2000 px de lado largo (lo mismo que guarda el backend) para ahorrar datos,
  y se piden sin metadatos de ubicación.
- **Los campos dudosos solo condicionan la revisión, no la búsqueda**: igual
  que en la v1, "¿la tengo?" se consulta con los campos *ya confirmados* por
  el usuario. Los dudosos se resaltan en el formulario para obligar a
  mirarlos; un año vacío nunca da "ya la tienes" (solo posible coincidencia).
- **Las fotos se suben después de guardar los datos**: si falla alguna, la
  moneda ya está guardada y se avisa para reintentarlo desde Editar.
- **Exportación con `share_plus`**: el archivo se entrega a la hoja de
  compartir (guardar en Archivos, enviar por correo...), sin pedir permisos
  de almacenamiento.
- **Permisos de iOS**: `NSCameraUsageDescription` y
  `NSPhotoLibraryUsageDescription` en `Info.plist` (Apple los exige y
  revisa el texto). Android no necesita permisos (usa los intents del
  sistema).

## Pendiente conocido

- **Android puede cerrar la app mientras la cámara está abierta** si va
  justo de memoria; al volver, la foto se pierde y hay que repetirla
  (`ImagePicker.retrieveLostData`). Se valorará al probar en dispositivos
  reales (Fase M5): recuperarla bien exige restaurar todo el flujo.
