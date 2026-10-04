import 'dart:typed_data';

import 'package:flutter/widgets.dart';
import 'package:image_picker/image_picker.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

enum OrigenFoto { camara, galeria }

/// Lo que la app necesita del teléfono: hacer o elegir una foto, entregar un
/// archivo al usuario y abrir un enlace. Detrás de una interfaz para poder probar las pantallas
/// sin cámara real (los tests usan un dispositivo falso).
abstract class Dispositivo {
  /// `null` si el usuario cancela.
  Future<Uint8List?> elegirFoto(OrigenFoto origen);

  /// Abre la hoja de compartir del sistema (en web, descarga el archivo).
  Future<void> compartirArchivo(List<int> bytes, {required String nombre, required String tipo});

  /// Abre [enlace] en el navegador del sistema. `false` si no se pudo.
  Future<bool> abrirEnlace(Uri enlace);
}

class DispositivoReal implements Dispositivo {
  final _selector = ImagePicker();

  /// Lado largo máximo de la foto antes de subirla: el mismo con el que el
  /// backend la guarda (`RESIZE_ALMACENAMIENTO`). Reducirla ya en el teléfono
  /// ahorra datos móviles; el backend la vuelve a normalizar igualmente.
  static const _ladoMaximo = 2000.0;

  @override
  Future<Uint8List?> elegirFoto(OrigenFoto origen) async {
    final foto = await _selector.pickImage(
      source: origen == OrigenFoto.camara ? ImageSource.camera : ImageSource.gallery,
      maxWidth: _ladoMaximo,
      maxHeight: _ladoMaximo,
      imageQuality: 90,
      // Sin pedir acceso a la ubicación de la foto: no la queremos.
      requestFullMetadata: false,
    );
    return foto?.readAsBytes();
  }

  @override
  Future<void> compartirArchivo(
    List<int> bytes, {
    required String nombre,
    required String tipo,
  }) async {
    await SharePlus.instance.share(
      ShareParams(
        files: [XFile.fromData(Uint8List.fromList(bytes), name: nombre, mimeType: tipo)],
        fileNameOverrides: [nombre],
      ),
    );
  }

  @override
  Future<bool> abrirEnlace(Uri enlace) async {
    try {
      return await launchUrl(enlace, mode: LaunchMode.externalApplication);
    } on Exception {
      return false;
    }
  }
}

/// Da acceso al [Dispositivo] desde cualquier pantalla.
class AmbitoDispositivo extends InheritedWidget {
  const AmbitoDispositivo({super.key, required this.dispositivo, required super.child});

  final Dispositivo dispositivo;

  static Dispositivo de(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AmbitoDispositivo>()!.dispositivo;

  @override
  bool updateShouldNotify(AmbitoDispositivo anterior) => dispositivo != anterior.dispositivo;
}
