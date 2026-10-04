import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'api/cliente_api.dart';
import 'auth/almacen_tokens.dart';
import 'auth/pantalla_acceso.dart';
import 'auth/sesion.dart';
import 'captura/dispositivo.dart';
import 'inicio/pantalla_inicio.dart';

/// URL del backend. Se fija al compilar:
///   flutter run --dart-define=ANTCOLLECT_API=https://api.ejemplo.com
/// Sin ella, en desarrollo se usa el backend local (`uvicorn` en el puerto
/// 8000). El emulador de Android ve el PC anfitrión como 10.0.2.2.
String urlApiPorDefecto() {
  const definida = String.fromEnvironment('ANTCOLLECT_API');
  if (definida.isNotEmpty) return definida;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://localhost:8000';
}

void main() {
  // Antes de nada: restaurar() lee el almacenamiento seguro por un canal
  // nativo, que en Android/iOS exige el binding ya inicializado (en web no).
  WidgetsFlutterBinding.ensureInitialized();
  final tokens = AlmacenTokensSeguro();
  final api = ClienteApi(urlBase: urlApiPorDefecto(), tokens: tokens);
  final sesion = Sesion(api: api, tokens: tokens)..restaurar();
  runApp(AntCollectApp(sesion: sesion, dispositivo: DispositivoReal()));
}

class AntCollectApp extends StatefulWidget {
  const AntCollectApp({super.key, required this.sesion, required this.dispositivo});

  final Sesion sesion;
  final Dispositivo dispositivo;

  @override
  State<AntCollectApp> createState() => _AntCollectAppState();
}

class _AntCollectAppState extends State<AntCollectApp> {
  final _navegador = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    widget.sesion.addListener(_alCambiarSesion);
  }

  @override
  void dispose() {
    widget.sesion.removeListener(_alCambiarSesion);
    super.dispose();
  }

  /// Al cerrar sesión (o caducar) se descartan las pantallas abiertas encima
  /// de la raíz, que pasa a mostrar el acceso.
  void _alCambiarSesion() {
    if (widget.sesion.estado == EstadoSesion.sinSesion) {
      _navegador.currentState?.popUntil((ruta) => ruta.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) {
    const semilla = Color(0xFFB8860B); // dorado viejo
    return AmbitoSesion(
      sesion: widget.sesion,
      child: AmbitoDispositivo(
        dispositivo: widget.dispositivo,
        child: MaterialApp(
          navigatorKey: _navegador,
          title: 'AntCollect',
          debugShowCheckedModeBanner: false,
          theme: ThemeData(colorSchemeSeed: semilla),
          darkTheme: ThemeData(colorSchemeSeed: semilla, brightness: Brightness.dark),
          locale: const Locale('es'),
          supportedLocales: const [Locale('es')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: const _Raiz(),
        ),
      ),
    );
  }
}

/// Elige la pantalla según haya sesión o no.
class _Raiz extends StatelessWidget {
  const _Raiz();

  @override
  Widget build(BuildContext context) {
    return switch (AmbitoSesion.de(context).estado) {
      EstadoSesion.comprobando => const Scaffold(body: Center(child: CircularProgressIndicator())),
      EstadoSesion.sinSesion => const PantallaAcceso(),
      EstadoSesion.conSesion => const PantallaInicio(),
    };
  }
}
