import 'package:antcollect/api/cliente_api.dart';
import 'package:antcollect/api/modelos.dart';
import 'package:antcollect/auth/almacen_tokens.dart';
import 'package:antcollect/auth/sesion.dart';
import 'package:antcollect/captura/dispositivo.dart';
import 'package:antcollect/coleccion/foto_moneda.dart';
import 'package:antcollect/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'backend_falso.dart';
import 'dispositivo_falso.dart';

// Fase M4: pipeline capturar → leer → confirmar, "¿la tengo?" y exportación.

const _email = 'ana@example.com';

void main() {
  late BackendFalso backend;
  late DispositivoFalso dispositivo;

  setUp(() {
    FotoMoneda.olvidarTodas(); // la caché es estática: que no pase de un test a otro
    backend = BackendFalso()..crearUsuario(_email, 'contrasena-segura');
    dispositivo = DispositivoFalso();
  });

  Future<void> arrancar(WidgetTester tester) async {
    final t = backend.emitirTokens(_email);
    final tokens = AlmacenTokensMemoria(
      ParDeTokens(accessToken: t.acceso, refreshToken: t.refresco),
    );
    final api = ClienteApi(urlBase: 'http://api.test', tokens: tokens, adaptador: backend);
    final sesion = Sesion(api: api, tokens: tokens);
    await tester.pumpWidget(AntCollectApp(sesion: sesion, dispositivo: dispositivo));
    await tester.runAsync(sesion.restaurar);
    await tester.pumpAndSettle();
  }

  Future<void> pulsar(WidgetTester tester, String clave) async {
    // Un campo con foco vuelve a desplazar la vista hacia sí mismo.
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.pumpAndSettle();
    final boton = find.byKey(Key(clave));
    if (boton.evaluate().isEmpty) {
      // Las ListView no construyen lo que queda fuera de pantalla.
      await tester.scrollUntilVisible(boton, 200, scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(boton);
    await tester.pumpAndSettle();
    await tester.tap(boton);
    await tester.pumpAndSettle();
  }

  /// Hace la foto de una cara con la cámara (falsa).
  Future<void> hacerFoto(WidgetTester tester, String cara) async {
    await pulsar(tester, 'fotos.$cara');
    await pulsar(tester, 'fotos.camara');
  }

  Iterable<String> escrituras() => backend.peticiones.where(
    (p) => p.startsWith('POST /coleccion') && p != 'POST /coleccion/comprobar',
  );

  String etiquetaDe(WidgetTester tester, String clave) {
    final campo = tester.widget<TextField>(
      find.descendant(of: find.byKey(Key(clave)), matching: find.byType(TextField)),
    );
    return campo.decoration!.labelText!;
  }

  String valorDe(WidgetTester tester, String clave) => tester
      .widget<TextField>(
        find.descendant(of: find.byKey(Key(clave)), matching: find.byType(TextField)),
      )
      .controller!
      .text;

  group('enseñar moneda nueva (RF-1, RF-3)', () {
    testWidgets('la IA propone, resalta los dudosos y solo se guarda al confirmar', (tester) async {
      backend.proximaLectura = {
        'pais': 'España',
        'valor_texto': '2 euros',
        'anio': 2008,
        'ceca': null,
        'variante': null,
        'campos_dudosos': ['anio'],
      };
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');
      expect(find.text('Te quedan 20 lecturas automáticas hoy.'), findsOneWidget);
      await hacerFoto(tester, 'reverso');
      expect(dispositivo.origenes, [OrigenFoto.camara, OrigenFoto.camara]);
      await pulsar(tester, 'captura.leer');

      // Propuesta en el formulario, aún sin escribir nada en la colección.
      expect(find.byKey(const Key('form.propuesta')), findsOneWidget);
      expect(find.textContaining('Revisa especialmente: año'), findsOneWidget);
      expect(etiquetaDe(tester, 'form.anio'), 'Año — revisar');
      expect(etiquetaDe(tester, 'form.pais'), 'País *');
      expect(valorDe(tester, 'form.pais'), 'España');
      expect(escrituras(), isEmpty);

      await tester.enterText(find.byKey(const Key('form.anio')), '2003');
      await pulsar(tester, 'form.guardar');

      final guardada = backend.monedas[_email]!.single;
      expect(guardada['anio'], 2003);
      expect(guardada['foto_anverso'], isNotNull);
      expect(guardada['foto_reverso'], isNotNull);
      expect(backend.peticiones, contains('PUT /coleccion/1/imagenes/anverso'));
      expect(find.text('2 euros · 2003'), findsOneWidget); // ficha
    });

    testWidgets('la foto de detalle nunca se envía a la IA (RF-8) pero sí se guarda', (
      tester,
    ) async {
      backend.proximaLectura = {'pais': 'Francia', 'valor_texto': '1 euro', 'anio': 2001};
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');
      await hacerFoto(tester, 'detalle');
      await pulsar(tester, 'captura.leer');

      expect(backend.lecturasRecibidas, [
        ['anverso'],
      ]);

      await pulsar(tester, 'form.guardar');
      expect(backend.peticiones, contains('PUT /coleccion/1/imagenes/detalle'));
    });

    testWidgets('sin foto del anverso no se puede leer con IA', (tester) async {
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');

      final leer = tester.widget<ButtonStyleButton>(find.byKey(const Key('captura.leer')));
      expect(leer.onPressed, isNull);
      expect(find.text('Añade al menos la foto del anverso para leerla con IA.'), findsOneWidget);
    });

    testWidgets('si la IA no puede leer, pasa al formulario manual con las fotos (RF-6)', (
      tester,
    ) async {
      await arrancar(tester); // por defecto la lectura falsa es fallida
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');
      await pulsar(tester, 'captura.leer');

      expect(find.textContaining('No se pudo leer la moneda'), findsOneWidget);
      expect(find.byKey(const Key('form.propuesta')), findsNothing);
      expect(valorDe(tester, 'form.pais'), isEmpty);
      expect(find.bySemanticsLabel('Anverso: cambiar foto'), findsOneWidget);
    });

    testWidgets('con la cuota agotada, el formulario manual explica por qué (RF-M3)', (
      tester,
    ) async {
      backend.errorLectura = (
        codigo: 429,
        detalle:
            'Has usado tus 20 lecturas automáticas de hoy. '
            'Puedes seguir rellenando los campos a mano.',
      );
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');
      await pulsar(tester, 'captura.leer');

      expect(find.textContaining('Has usado tus 20 lecturas'), findsOneWidget);
      expect(find.byKey(const Key('form.pais')), findsOneWidget);
    });

    testWidgets('si ya no quedan lecturas hoy, ni se ofrece leer con IA', (tester) async {
      backend.lecturasUsadas = 20;
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');

      final leer = tester.widget<ButtonStyleButton>(find.byKey(const Key('captura.leer')));
      expect(leer.onPressed, isNull);
      expect(find.textContaining('Has usado tus lecturas automáticas de hoy'), findsOneWidget);
    });

    testWidgets('sin red al leer, pasa al modo manual sin romperse', (tester) async {
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');
      backend.sinRed = true;
      await pulsar(tester, 'captura.leer');

      expect(find.textContaining('No se pudo conectar para leer la moneda'), findsOneWidget);
      expect(find.byKey(const Key('form.pais')), findsOneWidget);
    });

    testWidgets('cancelar la cámara no añade foto', (tester) async {
      dispositivo.cancelar = true;
      await arrancar(tester);
      await pulsar(tester, 'inicio.nueva');
      await hacerFoto(tester, 'anverso');

      expect(find.bySemanticsLabel('Anverso: añadir foto'), findsOneWidget);
    });
  });

  group('¿la tengo? (RF-2, RF-4, RF-5)', () {
    Future<void> comprobar(
      WidgetTester tester, {
      required String pais,
      required String valor,
      String? anio,
      String? ceca,
    }) async {
      await pulsar(tester, 'inicio.comprobar');
      await hacerFoto(tester, 'anverso');
      await pulsar(tester, 'captura.manual');
      await tester.enterText(find.byKey(const Key('form.pais')), pais);
      await tester.enterText(find.byKey(const Key('form.valor')), valor);
      if (anio != null) await tester.enterText(find.byKey(const Key('form.anio')), anio);
      if (ceca != null) await tester.enterText(find.byKey(const Key('form.ceca')), ceca);
      expect(find.text('Buscar en mi colección'), findsOneWidget);
      await pulsar(tester, 'form.guardar');
    }

    testWidgets('exacta: "Ya la tienes" con la tuya al lado de la encontrada', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '2 euros', anio: 2002, conFoto: true);
      await arrancar(tester);
      await comprobar(tester, pais: 'España', valor: '2 euros', anio: '2002');

      expect(find.byKey(const Key('resultado.exacta')), findsOneWidget);
      expect(find.text('Ya la tienes'), findsOneWidget);
      expect(find.text('La que has encontrado'), findsOneWidget);
      expect(find.text('La de tu colección'), findsOneWidget);
      expect(backend.peticiones, contains('GET /coleccion/1/imagenes/anverso'));
      expect(find.byKey(const Key('resultado.guardar')), findsNothing);
      expect(escrituras(), isEmpty);

      await pulsar(tester, 'resultado.verFicha');
      expect(find.text('Añadida'), findsOneWidget);
    });

    testWidgets('ninguna: "No la tienes" y "Guardar esta" reutiliza campos y fotos', (
      tester,
    ) async {
      await arrancar(tester);
      await comprobar(tester, pais: 'Italia', valor: '50 céntimos', anio: '2010');

      expect(find.text('No la tienes'), findsOneWidget);
      expect(escrituras(), isEmpty);

      await pulsar(tester, 'resultado.guardar');
      final guardada = backend.monedas[_email]!.single;
      expect(guardada['pais'], 'Italia');
      expect(guardada['anio'], 2010);
      expect(guardada['foto_anverso'], isNotNull);
      expect(find.text('50 céntimos · 2010'), findsOneWidget); // ficha
    });

    testWidgets('parcial: "Posible coincidencia" señala qué cambia y decide el humano', (
      tester,
    ) async {
      backend.anadirMoneda(_email, pais: 'Alemania', valor: '2 euros', anio: 2002, ceca: 'A');
      await arrancar(tester);
      await comprobar(tester, pais: 'Alemania', valor: '2 euros', anio: '2002', ceca: 'F');

      expect(find.text('Posible coincidencia'), findsOneWidget);
      expect(find.text('Distinto: ceca'), findsOneWidget);
      expect(escrituras(), isEmpty);

      await pulsar(tester, 'resultado.guardar');
      expect(backend.monedas[_email], hasLength(2));
    });

    testWidgets('año sin leer nunca da "ya la tienes", solo posible coincidencia', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro', anio: 2002);
      await arrancar(tester);
      await comprobar(tester, pais: 'España', valor: '1 euro');

      expect(find.text('Posible coincidencia'), findsOneWidget);
      expect(find.text('Ya la tienes'), findsNothing);
    });
  });

  group('fotos de una moneda guardada (RF-7, RF-8)', () {
    testWidgets('al editar se puede añadir una foto y quitar otra', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro', conFoto: true);
      await arrancar(tester);
      await pulsar(tester, 'inicio.coleccion');
      await tester.tap(find.text('1 euro'));
      await tester.pumpAndSettle();
      await pulsar(tester, 'ficha.editar');

      await hacerFoto(tester, 'reverso');
      await pulsar(tester, 'fotos.anverso');
      await pulsar(tester, 'fotos.quitar');
      await pulsar(tester, 'form.guardar');

      expect(backend.peticiones, contains('PUT /coleccion/1/imagenes/reverso'));
      expect(backend.peticiones, contains('DELETE /coleccion/1/imagenes/anverso'));
      final moneda = backend.monedas[_email]!.single;
      expect(moneda['foto_anverso'], isNull);
      expect(moneda['foto_reverso'], isNotNull);
      expect(find.text('Reverso'), findsOneWidget); // ficha con la foto nueva
      expect(find.text('Anverso'), findsNothing);
    });
  });

  group('exportación (RF-13)', () {
    testWidgets('exportar como CSV entrega el archivo a la hoja de compartir', (tester) async {
      await arrancar(tester);
      await pulsar(tester, 'inicio.coleccion');
      await pulsar(tester, 'listado.exportar');
      await pulsar(tester, 'listado.exportar.csv');

      expect(backend.peticiones, contains('GET /exportar'));
      final archivo = dispositivo.compartidos.single;
      expect(archivo.nombre, 'antcollect-2026-10-04.csv');
      expect(archivo.tipo, 'text/csv');
    });
  });
}
