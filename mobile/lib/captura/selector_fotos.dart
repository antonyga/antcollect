import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/modelos.dart';
import '../coleccion/foto_moneda.dart';
import 'dispositivo.dart';

/// Las tres fotos de una moneda (anverso, reverso y detalle, RF-7/RF-8) con
/// la cámara del teléfono o la galería. No guarda estado: el padre decide.
///
/// Cada cara muestra, por orden: la foto nueva (aún solo en el teléfono), la
/// ya guardada en la colección (al editar) o un hueco para añadirla.
class SelectorFotos extends StatelessWidget {
  const SelectorFotos({
    super.key,
    required this.nuevas,
    this.guardadas = const {},
    required this.alElegir,
    required this.alQuitar,
  });

  /// Cara → bytes de la foto recién hecha/elegida.
  final Map<String, Uint8List> nuevas;

  /// Cara → ruta de la foto ya guardada (solo al editar).
  final Map<String, String> guardadas;

  final void Function(String cara, Uint8List bytes) alElegir;
  final void Function(String cara) alQuitar;

  Future<void> _opciones(BuildContext context, String cara) async {
    final tieneFoto = nuevas.containsKey(cara) || guardadas.containsKey(cara);
    final eleccion = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              key: const Key('fotos.camara'),
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('Hacer foto'),
              onTap: () => Navigator.pop(context, 'camara'),
            ),
            ListTile(
              key: const Key('fotos.galeria'),
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Elegir de la galería'),
              onTap: () => Navigator.pop(context, 'galeria'),
            ),
            if (tieneFoto)
              ListTile(
                key: const Key('fotos.quitar'),
                leading: const Icon(Icons.delete_outline),
                title: const Text('Quitar foto'),
                onTap: () => Navigator.pop(context, 'quitar'),
              ),
          ],
        ),
      ),
    );
    if (eleccion == null || !context.mounted) return;
    if (eleccion == 'quitar') return alQuitar(cara);

    final origen = eleccion == 'camara' ? OrigenFoto.camara : OrigenFoto.galeria;
    try {
      final bytes = await AmbitoDispositivo.de(context).elegirFoto(origen);
      if (bytes != null) alElegir(cara, bytes);
    } on Exception {
      // Permiso de cámara denegado, sin cámara, etc.
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              origen == OrigenFoto.camara
                  ? 'No se pudo abrir la cámara. Revisa los permisos de la app.'
                  : 'No se pudo abrir la galería. Revisa los permisos de la app.',
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final (i, MapEntry(key: cara, value: etiqueta))
                in carasMoneda.entries.indexed) ...[
              if (i > 0) const SizedBox(width: 12),
              Expanded(child: _hueco(context, cara, etiqueta)),
            ],
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'El detalle es una foto de cerca para que tú revises la ceca o la variante: '
          'no se envía a la IA.',
          style: tema.textTheme.bodySmall?.copyWith(color: tema.colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }

  Widget _hueco(BuildContext context, String cara, String etiqueta) {
    final esquema = Theme.of(context).colorScheme;
    final nueva = nuevas[cara];
    final guardada = guardadas[cara];
    final Widget contenido;
    if (nueva != null) {
      contenido = Image.memory(nueva, fit: BoxFit.cover, gaplessPlayback: true);
    } else if (guardada != null) {
      contenido = FotoMoneda(ruta: guardada);
    } else {
      contenido = ColoredBox(
        color: esquema.surfaceContainerHighest,
        child: Icon(Icons.add_a_photo_outlined, color: esquema.onSurfaceVariant),
      );
    }
    final tieneFoto = nueva != null || guardada != null;

    return Column(
      children: [
        Semantics(
          button: true,
          label: tieneFoto ? '$etiqueta: cambiar foto' : '$etiqueta: añadir foto',
          excludeSemantics: true,
          child: AspectRatio(
            aspectRatio: 1,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  key: Key('fotos.$cara'),
                  onTap: () => _opciones(context, cara),
                  child: SizedBox.expand(child: contenido),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(etiqueta, style: Theme.of(context).textTheme.labelMedium),
      ],
    );
  }
}
