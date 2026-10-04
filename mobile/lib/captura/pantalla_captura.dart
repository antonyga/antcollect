import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import '../coleccion/pantalla_formulario.dart';
import 'flujo.dart';
import 'selector_fotos.dart';

/// Paso "capturar" (RF-7/RF-8) y "leer" (RF-1/RF-2) del pipeline: fotos de
/// la moneda y, si el usuario lo pide, lectura por IA. Tanto si la IA lee
/// como si no (fallo, sin red, cuota agotada: RF-6/RF-M3), se sigue al
/// formulario de confirmación; la app nunca se queda bloqueada.
///
/// Devuelve con `Navigator.pop` la [Moneda] si se acabó guardando.
class PantallaCaptura extends StatefulWidget {
  const PantallaCaptura({super.key, required this.modo});

  final ModoFlujo modo;

  @override
  State<PantallaCaptura> createState() => _PantallaCapturaState();
}

class _PantallaCapturaState extends State<PantallaCaptura> {
  final _fotos = <String, Uint8List>{};
  int? _restantes; // lecturas IA que quedan hoy; null = desconocido
  bool _leyendo = false;

  bool get _comprobar => widget.modo == ModoFlujo.comprobar;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_restantes == null) _cargarCuota();
  }

  Future<void> _cargarCuota() async {
    try {
      final cuota = await AmbitoSesion.api(context).cuota();
      if (mounted) setState(() => _restantes = cuota.restantesHoy);
    } on ErrorApi {
      // Solo informativo: si falla, ya avisará la lectura.
    }
  }

  /// Solo se llama a la IA cuando el usuario lo pide (RNF-4).
  Future<void> _leer() async {
    setState(() => _leyendo = true);
    LecturaPropuesta? propuesta;
    String? aviso;
    try {
      final lectura = await AmbitoSesion.api(context)
          .leer(_fotos['anverso']!, reverso: _fotos['reverso']);
      _restantes = lectura.restantesHoy;
      if (lectura.fallida) {
        aviso = 'No se pudo leer la moneda en la foto. Rellena los campos a mano.';
      } else {
        propuesta = lectura;
      }
    } on ErrorApi catch (e) {
      if (e.codigo == 429) _restantes = 0;
      aviso = switch (e.codigo) {
        null => 'No se pudo conectar para leer la moneda. Rellena los campos a mano.',
        429 || 503 => e.mensaje, // el backend ya invita a rellenar a mano
        _ => 'La lectura automática falló. Rellena los campos a mano.',
      };
    } finally {
      if (mounted) setState(() => _leyendo = false);
    }
    if (mounted) await _confirmar(propuesta: propuesta, aviso: aviso);
  }

  Future<void> _confirmar({LecturaPropuesta? propuesta, String? aviso}) async {
    final navegador = Navigator.of(context);
    final guardada = await navegador.push<Moneda>(
      MaterialPageRoute(
        builder: (_) => PantallaFormulario(
          modo: widget.modo,
          propuesta: propuesta,
          aviso: aviso,
          fotos: {..._fotos},
        ),
      ),
    );
    if (guardada != null) navegador.pop(guardada);
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final tieneAnverso = _fotos.containsKey('anverso');
    final sinCuota = _restantes == 0;
    final secundario = tema.textTheme.bodyMedium?.copyWith(
      color: tema.colorScheme.onSurfaceVariant,
    );

    return Scaffold(
      appBar: AppBar(title: Text(_comprobar ? '¿La tengo?' : 'Enseñar moneda nueva')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  _comprobar
                      ? 'Haz una foto del anverso (y del reverso si puedes: ayuda a leerla mejor). '
                            'Antes de buscar en tu colección revisarás los campos propuestos.'
                      : 'Haz una foto del anverso (y del reverso si puedes: ayuda a leerla mejor). '
                            'La IA solo propone los campos: los revisarás antes de guardar nada.',
                ),
                const SizedBox(height: 16),
                SelectorFotos(
                  nuevas: _fotos,
                  alElegir: (cara, bytes) => setState(() => _fotos[cara] = bytes),
                  alQuitar: (cara) => setState(() => _fotos.remove(cara)),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  key: const Key('captura.leer'),
                  onPressed: tieneAnverso && !sinCuota && !_leyendo ? _leer : null,
                  icon: _leyendo
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.auto_awesome_outlined),
                  label: Text(_leyendo ? 'Leyendo la moneda…' : 'Leer con IA'),
                ),
                const SizedBox(height: 8),
                Text(
                  sinCuota
                      ? 'Has usado tus lecturas automáticas de hoy. Puedes seguir rellenando '
                            'los campos a mano.'
                      : !tieneAnverso
                      ? 'Añade al menos la foto del anverso para leerla con IA.'
                      : _restantes != null
                      ? 'Te quedan $_restantes lecturas automáticas hoy.'
                      : '',
                  key: const Key('captura.cuota'),
                  style: secundario,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  key: const Key('captura.manual'),
                  onPressed: _leyendo ? null : () => _confirmar(),
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Rellenar a mano'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
