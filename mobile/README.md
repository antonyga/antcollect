# AntCollect — app móvil (v2, Flutter)

App nativa (iOS + Android) de AntCollect, publicada en App Store y Play Store.
Habla con el backend en `../backend/` — no incluye lógica de IA ni acceso
directo a base de datos (eso vive en el backend, ver RNF-5/RNF-M1 del doc de
arquitectura).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

**Fase M3** — cuenta (registro, inicio y cierre de sesión), inicio con dos
acciones, alta manual, listado con búsqueda y filtros, ficha con fotos,
edición y borrado con confirmación. Todo contra la API real.
Sin cámara ni lectura IA todavía (Fase M4).

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
traducción de errores — además de las pantallas.

## Estructura

```
mobile/
├── lib/
│   ├── main.dart        # arranque, URL del backend, tema, raíz según sesión
│   ├── api/             # ClienteApi (dio) + modelos espejo de backend/app/esquemas.py
│   ├── auth/            # sesión, tokens en almacenamiento seguro, pantalla de acceso
│   ├── inicio/          # pantalla de inicio (dos acciones)
│   ├── coleccion/       # listado + filtros, ficha, formulario alta/edición, fotos
│   ├── captura/         # (Fase M4) cámara + capturar → leer → confirmar
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
