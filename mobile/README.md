# AntCollect — app móvil (v2, Flutter)

App nativa (iOS + Android) de AntCollect, publicada en App Store y Play Store.
Habla con el backend en `../backend/` — no incluye lógica de IA ni acceso
directo a base de datos (eso vive en el backend, ver RNF-5/RNF-M1 del doc de
arquitectura).

- Arquitectura y requisitos: [../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md](../Docs/AntCollect-Movil-Arquitectura-y-Requisitos.md)
- Plan de fases: [../PLAN-MOVIL.md](../PLAN-MOVIL.md)

## Estado

Esqueleto de directorios (Fase M0). El proyecto Flutter real (`flutter
create`) y las pantallas se construyen en la Fase M3.

**Prerrequisito para la Fase M3:** el SDK de Flutter no está instalado en esta
máquina (`flutter`/`dart` no encontrados en el PATH al planificar esta fase).
Instalar antes de empezar la Fase M3: <https://docs.flutter.dev/get-started/install>.

## Estructura prevista

```
mobile/
├── lib/
│   ├── main.dart
│   ├── api/          # cliente HTTP (dio) + modelos
│   ├── auth/           # login/registro, almacenamiento seguro del token
│   ├── coleccion/       # listado, filtros, ficha, editar/borrar, exportar
│   ├── captura/           # cámara (anverso/reverso/detalle), pipeline capturar→leer→confirmar
│   └── cuenta/             # ajustes, cerrar sesión, borrar cuenta
└── test/
```
