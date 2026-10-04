import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../auth/sesion.dart';
import 'enlaces_legales.dart';

/// "Mi cuenta" (RF-M1): email, documentos legales, cerrar sesión y borrar la
/// cuenta. El borrado tiene que estar dentro de la app para pasar la revisión
/// de Apple (guideline 5.1.1(v)) si la app permite crear cuentas.
class PantallaCuenta extends StatelessWidget {
  const PantallaCuenta({super.key});

  static String _fecha(DateTime f) {
    final local = f.toLocal();
    return '${local.day}/${local.month}/${local.year}';
  }

  @override
  Widget build(BuildContext context) {
    final usuario = AmbitoSesion.de(context).usuario;
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Mi cuenta')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: ListView(
              children: [
                if (usuario != null)
                  ListTile(
                    leading: const Icon(Icons.account_circle_outlined),
                    title: Text(usuario.email),
                    subtitle: Text('Cuenta creada el ${_fecha(usuario.creadoEn)}'),
                  ),
                const Divider(),
                ListTile(
                  key: const Key('cuenta.privacidad'),
                  leading: const Icon(Icons.privacy_tip_outlined),
                  title: const Text('Política de privacidad'),
                  trailing: const Icon(Icons.open_in_new),
                  onTap: () => abrirEnlaceLegal(context, 'privacidad'),
                ),
                ListTile(
                  key: const Key('cuenta.terminos'),
                  leading: const Icon(Icons.description_outlined),
                  title: const Text('Términos del servicio'),
                  trailing: const Icon(Icons.open_in_new),
                  onTap: () => abrirEnlaceLegal(context, 'terminos'),
                ),
                const Divider(),
                ListTile(
                  key: const Key('cuenta.cerrarSesion'),
                  leading: const Icon(Icons.logout),
                  title: const Text('Cerrar sesión'),
                  onTap: () => confirmarCierreSesion(context),
                ),
                ListTile(
                  key: const Key('cuenta.borrar'),
                  leading: Icon(Icons.delete_forever_outlined, color: tema.colorScheme.error),
                  title: Text('Borrar mi cuenta', style: TextStyle(color: tema.colorScheme.error)),
                  subtitle: const Text('Se borran tu colección y tus fotos para siempre'),
                  onTap: () => _borrarCuenta(context),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _borrarCuenta(BuildContext context) async {
    final mensajero = ScaffoldMessenger.of(context);
    final sesion = AmbitoSesion.leer(context);
    final borrada = await showDialog<bool>(
      context: context,
      builder: (_) => const _DialogoBorrarCuenta(),
    );
    if (borrada == true) {
      // Con el diálogo ya cerrado: cerrar la sesión vuelve al acceso
      // descartando las pantallas abiertas.
      await sesion.cerrarSesion();
      mensajero.showSnackBar(
        const SnackBar(content: Text('Tu cuenta y todos sus datos se han borrado.')),
      );
    }
  }
}

/// Pide confirmación y cierra la sesión (también desde el menú de inicio).
Future<void> confirmarCierreSesion(BuildContext context) async {
  final sesion = AmbitoSesion.leer(context);
  final confirmado = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('¿Cerrar sesión?'),
      content: const Text('Tu colección sigue guardada en tu cuenta.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
        FilledButton(
          key: const Key('cerrarSesion.confirmar'),
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Cerrar sesión'),
        ),
      ],
    ),
  );
  if (confirmado == true) await sesion.cerrarSesion();
}

/// Confirmación con contraseña. Se cierra con `true` solo si el backend ha
/// borrado la cuenta (entonces quien lo abrió cierra la sesión); los errores (contraseña incorrecta, sin red) se
/// muestran dentro del diálogo para poder reintentar.
class _DialogoBorrarCuenta extends StatefulWidget {
  const _DialogoBorrarCuenta();

  @override
  State<_DialogoBorrarCuenta> createState() => _DialogoBorrarCuentaState();
}

class _DialogoBorrarCuentaState extends State<_DialogoBorrarCuenta> {
  final _contrasena = TextEditingController();
  bool _borrando = false;
  String? _error;

  @override
  void dispose() {
    _contrasena.dispose();
    super.dispose();
  }

  Future<void> _borrar() async {
    if (_contrasena.text.isEmpty) {
      setState(() => _error = 'Escribe tu contraseña');
      return;
    }
    setState(() {
      _borrando = true;
      _error = null;
    });
    final navegador = Navigator.of(context);
    try {
      await AmbitoSesion.api(context).borrarCuenta(_contrasena.text);
      navegador.pop(true);
    } on ErrorApi catch (e) {
      if (mounted) {
        setState(() {
          _borrando = false;
          _error = e.mensaje;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return AlertDialog(
      icon: Icon(Icons.warning_amber_rounded, color: tema.colorScheme.error),
      title: const Text('¿Borrar tu cuenta?'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Se borrarán para siempre tu cuenta, todas tus monedas y todas sus '
              'fotos. No se puede deshacer.',
            ),
            const SizedBox(height: 8),
            const Text(
              'Si quieres conservar una copia, exporta antes tu colección desde '
              '«Mi colección».',
            ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('borrarCuenta.contrasena'),
              controller: _contrasena,
              obscureText: true,
              enabled: !_borrando,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(
                labelText: 'Tu contraseña, para confirmar',
                border: const OutlineInputBorder(),
                errorText: _error,
              ),
              onSubmitted: (_) => _borrar(),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _borrando ? null : () => Navigator.pop(context, false),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          key: const Key('borrarCuenta.confirmar'),
          style: FilledButton.styleFrom(
            backgroundColor: tema.colorScheme.error,
            foregroundColor: tema.colorScheme.onError,
          ),
          onPressed: _borrando ? null : _borrar,
          child: _borrando
              ? const SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Borrar para siempre'),
        ),
      ],
    );
  }
}
