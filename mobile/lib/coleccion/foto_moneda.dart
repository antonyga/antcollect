import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../auth/sesion.dart';

/// Foto de una moneda. Las fotos son privadas: se descargan a través del
/// backend con el token del usuario (no hay URLs públicas), así que no vale
/// `Image.network` a secas — se piden con [ClienteApi], que además renueva
/// el token si caduca.
class FotoMoneda extends StatefulWidget {
  const FotoMoneda({super.key, required this.ruta, this.tamano, this.ajuste = BoxFit.cover});

  final String ruta;
  final double? tamano;
  final BoxFit ajuste;

  // Caché en memoria de las últimas fotos vistas (el listado las repite).
  static final _cache = <String, Uint8List>{}; // conserva el orden de inserción
  static const _maxCache = 60;

  /// Para cuando una foto cambie (subida nueva) y haya que volver a pedirla.
  static void olvidar(String ruta) => _cache.remove(ruta);

  @override
  State<FotoMoneda> createState() => _FotoMonedaState();
}

class _FotoMonedaState extends State<FotoMoneda> {
  Future<Uint8List>? _bytes;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _bytes ??= _cargar();
  }

  @override
  void didUpdateWidget(FotoMoneda anterior) {
    super.didUpdateWidget(anterior);
    if (anterior.ruta != widget.ruta) _bytes = _cargar();
  }

  Future<Uint8List> _cargar() async {
    final cache = FotoMoneda._cache;
    final enCache = cache.remove(widget.ruta);
    if (enCache != null) return cache[widget.ruta] = enCache;

    final bytes = await AmbitoSesion.api(context).descargarFoto(widget.ruta);
    cache[widget.ruta] = bytes;
    if (cache.length > FotoMoneda._maxCache) cache.remove(cache.keys.first);
    return bytes;
  }

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.surfaceContainerHighest;
    return SizedBox(
      width: widget.tamano,
      height: widget.tamano,
      child: FutureBuilder(
        future: _bytes,
        builder: (context, snap) {
          if (snap.hasData) {
            return Image.memory(snap.data!, fit: widget.ajuste, gaplessPlayback: true);
          }
          return ColoredBox(
            color: color,
            child: Center(
              child: snap.hasError
                  ? const Icon(Icons.broken_image_outlined)
                  : const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
            ),
          );
        },
      ),
    );
  }
}

/// Hueco para monedas sin foto.
class SinFoto extends StatelessWidget {
  const SinFoto({super.key, this.tamano});

  final double? tamano;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return SizedBox(
      width: tamano,
      height: tamano,
      child: ColoredBox(
        color: esquema.surfaceContainerHighest,
        child: Icon(Icons.monetization_on_outlined, color: esquema.onSurfaceVariant),
      ),
    );
  }
}
