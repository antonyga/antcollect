import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import '../coleccion/foto_moneda.dart';
import '../coleccion/pantalla_ficha.dart';

/// Da de alta una moneda nueva con sus fotos. Solo se llama cuando el usuario
/// ha pulsado un botón de guardar sobre campos que ha revisado (RF-3).
///
/// Devuelve la moneda guardada, o `null` si no se guardó (duplicado o error,
/// ya avisados al usuario). Si la moneda se guarda pero falla alguna foto, se
/// devuelve igualmente y se avisa: los datos ya están a salvo.
Future<Moneda?> guardarMonedaNueva(
  BuildContext context,
  DatosMoneda datos,
  Map<String, Uint8List> fotos,
) async {
  final api = AmbitoSesion.api(context);
  final mensajero = ScaffoldMessenger.of(context);
  Moneda moneda;
  try {
    moneda = await api.crear(datos);
  } on TipoDuplicadoError catch (e) {
    // Sin esperar al diálogo: quien llama deja de mostrar "guardando".
    if (context.mounted) unawaited(avisarDuplicado(context, e));
    return null;
  } on ErrorApi catch (e) {
    mensajero.showSnackBar(SnackBar(content: Text(e.mensaje)));
    return null;
  }
  return await _subirFotos(api, mensajero, moneda, fotos, const {});
}

/// Aplica los cambios de fotos de una moneda ya guardada: sube las nuevas
/// (reemplazando las que hubiera) y borra las quitadas.
Future<Moneda> actualizarFotos(
  BuildContext context,
  Moneda moneda,
  Map<String, Uint8List> nuevas,
  Set<String> quitadas,
) =>
    _subirFotos(AmbitoSesion.api(context), ScaffoldMessenger.of(context), moneda, nuevas, quitadas);

Future<Moneda> _subirFotos(
  ClienteApi api,
  ScaffoldMessengerState mensajero,
  Moneda moneda,
  Map<String, Uint8List> nuevas,
  Set<String> quitadas,
) async {
  var fallos = 0;
  for (final MapEntry(key: cara, value: bytes) in nuevas.entries) {
    try {
      moneda = await api.subirFoto(moneda.id, cara, bytes);
      // La ruta de una cara no cambia al reemplazarla: olvidar la vieja.
      FotoMoneda.olvidar(moneda.fotos[cara]!);
    } on ErrorApi {
      fallos++;
    }
  }
  for (final cara in quitadas.difference(nuevas.keys.toSet())) {
    final ruta = moneda.fotos[cara];
    if (ruta == null) continue;
    try {
      await api.borrarFoto(moneda.id, cara);
      FotoMoneda.olvidar(ruta);
      moneda = moneda.conFotos({...moneda.fotos}..remove(cara));
    } on ErrorApi {
      fallos++;
    }
  }
  if (fallos > 0) {
    mensajero.showSnackBar(
      const SnackBar(
        content: Text(
          'Los datos se guardaron, pero no se pudo actualizar alguna foto. '
          'Puedes volver a intentarlo desde Editar.',
        ),
      ),
    );
  }
  return moneda;
}

/// RF-14: el tipo ya existe. Se ofrece ver la que ya tienes, sin guardar.
Future<void> avisarDuplicado(BuildContext context, TipoDuplicadoError e) async {
  final verla = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Ya tienes este tipo'),
      content: const Text(
        'En tu colección ya hay una moneda con el mismo país, valor, año, ceca y variante. '
        'Revisa los campos o abre la que ya tienes.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Revisar campos'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Ver la que ya tengo'),
        ),
      ],
    ),
  );
  if (verla == true && context.mounted) {
    await Navigator.of(context)
        .push(MaterialPageRoute<void>(builder: (_) => PantallaFicha(monedaId: e.existenteId)));
  }
}
