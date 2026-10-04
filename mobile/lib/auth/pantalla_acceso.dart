import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../cuenta/enlaces_legales.dart';
import 'sesion.dart';

/// Inicio de sesión y registro (RF-M1), en la misma pantalla.
class PantallaAcceso extends StatefulWidget {
  const PantallaAcceso({super.key});

  @override
  State<PantallaAcceso> createState() => _PantallaAccesoState();
}

class _PantallaAccesoState extends State<PantallaAcceso> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _contrasena = TextEditingController();
  bool _registro = false;
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _contrasena.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _enviando = true;
      _error = null;
    });
    final sesion = AmbitoSesion.leer(context);
    final email = _email.text.trim();
    try {
      if (_registro) {
        await sesion.registrarse(email, _contrasena.text);
      } else {
        await sesion.iniciarSesion(email, _contrasena.text);
      }
    } on ErrorApi catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Icon(Icons.monetization_on_outlined, size: 64, color: tema.colorScheme.primary),
                    const SizedBox(height: 8),
                    Text(
                      'AntCollect',
                      textAlign: TextAlign.center,
                      style: tema.textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _registro ? 'Crea tu cuenta' : 'Inicia sesión para ver tu colección',
                      textAlign: TextAlign.center,
                      style: tema.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 32),
                    TextFormField(
                      key: const Key('acceso.email'),
                      controller: _email,
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: TextInputAction.next,
                      validator: (v) {
                        final texto = v?.trim() ?? '';
                        if (texto.isEmpty) return 'Escribe tu email';
                        if (!texto.contains('@') || !texto.contains('.')) {
                          return 'Ese email no parece válido';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      key: const Key('acceso.contrasena'),
                      controller: _contrasena,
                      decoration: InputDecoration(
                        labelText: 'Contraseña',
                        border: const OutlineInputBorder(),
                        helperText: _registro ? 'Entre 8 y 72 caracteres' : null,
                      ),
                      obscureText: true,
                      autofillHints: [
                        _registro ? AutofillHints.newPassword : AutofillHints.password,
                      ],
                      onFieldSubmitted: (_) => _enviar(),
                      validator: (v) {
                        final texto = v ?? '';
                        if (texto.isEmpty) return 'Escribe tu contraseña';
                        if (_registro && texto.length < 8) return 'Mínimo 8 caracteres';
                        if (_registro && texto.length > 72) return 'Máximo 72 caracteres';
                        return null;
                      },
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 16),
                      Text(_error!, style: TextStyle(color: tema.colorScheme.error)),
                    ],
                    if (_registro) ...[const SizedBox(height: 16), const AvisoLegalRegistro()],
                    const SizedBox(height: 24),
                    FilledButton(
                      key: const Key('acceso.enviar'),
                      onPressed: _enviando ? null : _enviar,
                      child: _enviando
                          ? const SizedBox.square(
                              dimension: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(_registro ? 'Crear cuenta' : 'Entrar'),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: _enviando
                          ? null
                          : () => setState(() {
                              _registro = !_registro;
                              _error = null;
                            }),
                      child: Text(
                        _registro
                            ? '¿Ya tienes cuenta? Inicia sesión'
                            : '¿No tienes cuenta? Regístrate',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
