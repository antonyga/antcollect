import 'dart:typed_data';

import 'package:antcollect/captura/dispositivo.dart';

import 'backend_falso.dart';

/// Cámara/galería y hoja de compartir simuladas.
class DispositivoFalso implements Dispositivo {
  /// Orígenes pedidos, en orden.
  final origenes = <OrigenFoto>[];

  /// Si es true, el usuario cancela la cámara/galería.
  bool cancelar = false;

  /// Archivos entregados con la hoja de compartir.
  final compartidos = <({String nombre, String tipo, List<int> bytes})>[];

  /// Enlaces abiertos en el navegador.
  final enlaces = <Uri>[];

  @override
  Future<Uint8List?> elegirFoto(OrigenFoto origen) async {
    origenes.add(origen);
    return cancelar ? null : pngDePrueba;
  }

  @override
  Future<void> compartirArchivo(
    List<int> bytes, {
    required String nombre,
    required String tipo,
  }) async {
    compartidos.add((nombre: nombre, tipo: tipo, bytes: bytes));
  }

  @override
  Future<bool> abrirEnlace(Uri enlace) async {
    enlaces.add(enlace);
    return true;
  }
}
