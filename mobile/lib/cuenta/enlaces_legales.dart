import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../auth/sesion.dart';
import '../captura/dispositivo.dart';

/// Abre la política de privacidad (`privacidad`) o los términos (`terminos`)
/// del backend en el navegador (RNF-M3).
Future<void> abrirEnlaceLegal(BuildContext context, String pagina) async {
  final enlace = AmbitoSesion.api(context).enlaceLegal(pagina);
  final mensajero = ScaffoldMessenger.of(context);
  final abierto = await AmbitoDispositivo.de(context).abrirEnlace(enlace);
  if (!abierto) {
    mensajero.showSnackBar(SnackBar(content: Text('No se pudo abrir $enlace')));
  }
}

/// "Al crear una cuenta aceptas los Términos y la Política de privacidad",
/// con los dos enlaces. Para la pantalla de registro.
class AvisoLegalRegistro extends StatefulWidget {
  const AvisoLegalRegistro({super.key});

  @override
  State<AvisoLegalRegistro> createState() => _AvisoLegalRegistroState();
}

class _AvisoLegalRegistroState extends State<AvisoLegalRegistro> {
  late final TapGestureRecognizer _terminos;
  late final TapGestureRecognizer _privacidad;

  @override
  void initState() {
    super.initState();
    _terminos = TapGestureRecognizer()..onTap = () => abrirEnlaceLegal(context, 'terminos');
    _privacidad = TapGestureRecognizer()..onTap = () => abrirEnlaceLegal(context, 'privacidad');
  }

  @override
  void dispose() {
    _terminos.dispose();
    _privacidad.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final enlace = TextStyle(color: tema.colorScheme.primary, decoration: TextDecoration.underline);
    return Text.rich(
      key: const Key('acceso.avisoLegal'),
      TextSpan(
        style: tema.textTheme.bodySmall?.copyWith(color: tema.colorScheme.onSurfaceVariant),
        children: [
          const TextSpan(text: 'Al crear una cuenta aceptas los '),
          TextSpan(text: 'Términos del servicio', style: enlace, recognizer: _terminos),
          const TextSpan(text: ' y la '),
          TextSpan(text: 'Política de privacidad', style: enlace, recognizer: _privacidad),
          const TextSpan(text: '.'),
        ],
      ),
      textAlign: TextAlign.center,
    );
  }
}
