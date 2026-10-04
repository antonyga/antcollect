import 'package:flutter/material.dart';

import '../api/modelos.dart';
import '../coleccion/pantalla_ficha.dart';
import 'pantalla_captura.dart';

/// Los dos flujos son el mismo pipeline capturar → leer → confirmar con
/// distinto final (CLAUDE.md §1): guardar en la colección o consultarla.
enum ModoFlujo {
  /// RF-1: enseñar una moneda nueva → guardar.
  ensenar,

  /// RF-2: comprobar una moneda encontrada → "¿la tengo?".
  comprobar,
}

/// Abre el pipeline y, si acaba guardando una moneda, muestra su ficha.
/// Devuelve la moneda guardada, o `null` si no se guardó nada.
Future<Moneda?> abrirFlujo(BuildContext context, ModoFlujo modo) async {
  final navegador = Navigator.of(context);
  final guardada = await navegador.push<Moneda>(
    MaterialPageRoute(builder: (_) => PantallaCaptura(modo: modo)),
  );
  if (guardada != null) {
    await navegador.push(
      MaterialPageRoute<void>(builder: (_) => PantallaFicha(monedaId: guardada.id)),
    );
  }
  return guardada;
}
