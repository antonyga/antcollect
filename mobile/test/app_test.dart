import 'package:antcollect/api/cliente_api.dart';
import 'package:antcollect/api/modelos.dart';
import 'package:antcollect/auth/almacen_tokens.dart';
import 'package:antcollect/auth/sesion.dart';
import 'package:antcollect/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'backend_falso.dart';

const _email = 'ana@example.com';
const _contrasena = 'contrasena-segura';

void main() {
  late BackendFalso backend;

  setUp(() => backend = BackendFalso()..crearUsuario(_email, _contrasena));

  /// Arranca la app contra el backend falso; con [conSesion] ya entra logueada.
  Future<void> arrancar(WidgetTester tester, {bool conSesion = true}) async {
    final tokens = AlmacenTokensMemoria();
    if (conSesion) {
      final t = backend.emitirTokens(_email);
      tokens.tokens = ParDeTokens(accessToken: t.acceso, refreshToken: t.refresco);
    }
    final api = ClienteApi(urlBase: 'http://api.test', tokens: tokens, adaptador: backend);
    final sesion = Sesion(api: api, tokens: tokens);
    await tester.pumpWidget(AntCollectApp(sesion: sesion));
    await tester.runAsync(sesion.restaurar);
    await tester.pumpAndSettle();
  }

  Future<void> pulsarGuardar(WidgetTester tester) async {
    await tester.ensureVisible(find.byKey(const Key('form.guardar')));
    await tester.tap(find.byKey(const Key('form.guardar')));
    await tester.pumpAndSettle();
  }

  Future<void> irAColeccion(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('inicio.coleccion')));
    await tester.pumpAndSettle();
  }

  group('acceso (RF-M1)', () {
    testWidgets('sin sesión muestra el acceso; al entrar va al inicio', (tester) async {
      await arrancar(tester, conSesion: false);
      expect(find.text('Inicia sesión para ver tu colección'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('acceso.email')), _email);
      await tester.enterText(find.byKey(const Key('acceso.contrasena')), _contrasena);
      await tester.tap(find.byKey(const Key('acceso.enviar')));
      await tester.pumpAndSettle();

      expect(find.text('¿Qué quieres hacer?'), findsOneWidget);
    });

    testWidgets('credenciales incorrectas muestran el error sin salir del acceso', (tester) async {
      await arrancar(tester, conSesion: false);
      await tester.enterText(find.byKey(const Key('acceso.email')), _email);
      await tester.enterText(find.byKey(const Key('acceso.contrasena')), 'equivocada');
      await tester.tap(find.byKey(const Key('acceso.enviar')));
      await tester.pumpAndSettle();

      expect(find.text('Email o contraseña incorrectos'), findsOneWidget);
    });

    testWidgets('el registro valida la longitud de la contraseña y crea la cuenta', (tester) async {
      await arrancar(tester, conSesion: false);
      await tester.tap(find.text('¿No tienes cuenta? Regístrate'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('acceso.email')), 'nuevo@example.com');
      await tester.enterText(find.byKey(const Key('acceso.contrasena')), 'corta');
      await tester.tap(find.byKey(const Key('acceso.enviar')));
      await tester.pumpAndSettle();
      expect(find.text('Mínimo 8 caracteres'), findsOneWidget);
      expect(backend.peticiones, isEmpty);

      await tester.enterText(find.byKey(const Key('acceso.contrasena')), 'suficientemente-larga');
      await tester.tap(find.byKey(const Key('acceso.enviar')));
      await tester.pumpAndSettle();
      expect(find.text('¿Qué quieres hacer?'), findsOneWidget);
      expect(backend.monedas.containsKey('nuevo@example.com'), isTrue);
    });

    testWidgets('cerrar sesión pide confirmación y vuelve al acceso', (tester) async {
      await arrancar(tester);
      await tester.tap(find.byKey(const Key('inicio.menu')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cerrar sesión'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Cerrar sesión'));
      await tester.pumpAndSettle();

      expect(find.text('Inicia sesión para ver tu colección'), findsOneWidget);
    });

    testWidgets('si la sesión caduca del todo, se vuelve al acceso desde cualquier pantalla', (
      tester,
    ) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro');
      await arrancar(tester);
      await irAColeccion(tester);
      expect(find.text('1 euro'), findsOneWidget);

      backend.caducarTodo();
      await tester.drag(find.text('1 euro'), const Offset(0, 300)); // tirar para recargar
      await tester.pumpAndSettle();

      expect(find.text('Inicia sesión para ver tu colección'), findsOneWidget);
    });
  });

  group('colección', () {
    testWidgets('listado vacío invita a añadir la primera moneda', (tester) async {
      await arrancar(tester);
      await irAColeccion(tester);
      expect(find.textContaining('Tu colección está vacía'), findsOneWidget);
    });

    testWidgets('alta manual: valida obligatorios, guarda y abre la ficha', (tester) async {
      await arrancar(tester);
      await tester.tap(find.byKey(const Key('inicio.nueva')));
      await tester.pumpAndSettle();

      await pulsarGuardar(tester);
      expect(find.text('Este campo es obligatorio'), findsNWidgets(2));
      expect(backend.peticiones.where((p) => p.startsWith('POST')), isEmpty);

      await tester.enterText(find.byKey(const Key('form.pais')), 'España');
      await tester.enterText(find.byKey(const Key('form.valor')), '2 euros');
      await tester.enterText(find.byKey(const Key('form.anio')), '2002');
      await tester.enterText(find.byKey(const Key('form.ceca')), 'M');
      await pulsarGuardar(tester);

      expect(backend.monedas[_email]!.single['pais'], 'España');
      expect(find.text('2 euros · 2002'), findsOneWidget); // título de la ficha
      expect(find.text('M'), findsOneWidget);
    });

    testWidgets('un año imposible no se envía', (tester) async {
      await arrancar(tester);
      await tester.tap(find.byKey(const Key('inicio.nueva')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('form.pais')), 'España');
      await tester.enterText(find.byKey(const Key('form.valor')), '1 euro');
      await tester.enterText(find.byKey(const Key('form.anio')), '20022');
      await pulsarGuardar(tester);

      expect(find.textContaining('año válido'), findsOneWidget);
      expect(backend.monedas[_email], isEmpty);
    });

    testWidgets('guardar un tipo que ya tienes avisa y permite abrir el existente (RF-14)', (
      tester,
    ) async {
      backend.anadirMoneda(
        _email,
        pais: 'España',
        valor: '2 euros',
        anio: 2002,
        notas: 'la original',
      );
      await arrancar(tester);
      await tester.tap(find.byKey(const Key('inicio.nueva')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('form.pais')), 'españa');
      await tester.enterText(find.byKey(const Key('form.valor')), '2 euros');
      await tester.enterText(find.byKey(const Key('form.anio')), '2002');
      await pulsarGuardar(tester);

      expect(find.text('Ya tienes este tipo'), findsOneWidget);
      await tester.tap(find.text('Ver la que ya tengo'));
      await tester.pumpAndSettle();
      expect(find.text('la original'), findsOneWidget);
      expect(backend.monedas[_email]!.length, 1);
    });

    testWidgets('buscar filtra el listado (RF-9)', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro', anio: 2002);
      backend.anadirMoneda(_email, pais: 'Francia', valor: '2 euros', anio: 2001);
      await arrancar(tester);
      await irAColeccion(tester);
      expect(find.text('2 monedas'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('listado.busqueda')), 'franc');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(find.text('1 moneda'), findsOneWidget);
      expect(find.text('2 euros · 2001'), findsOneWidget);
      expect(find.text('1 euro · 2002'), findsNothing);
    });

    testWidgets('filtrar por estado desde la hoja de filtros (RF-9, RF-12)', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro');
      backend.anadirMoneda(_email, pais: 'Italia', valor: '1 euro', estado: 'para_intercambio');
      await arrancar(tester);
      await irAColeccion(tester);

      await tester.tap(find.byKey(const Key('listado.filtros')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Todos'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Para intercambio').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('filtros.aplicar')));
      await tester.pumpAndSettle();

      expect(find.text('1 moneda'), findsOneWidget);
      expect(find.text('Italia'), findsOneWidget);
    });

    testWidgets('editar desde la ficha actualiza la ficha y el listado (RF-10)', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro', anio: 2002);
      await arrancar(tester);
      await irAColeccion(tester);
      await tester.tap(find.text('1 euro · 2002'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('ficha.editar')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('form.anio')), '2003');
      await tester.enterText(find.byKey(const Key('form.notas')), 'brillo original');
      await pulsarGuardar(tester);

      expect(find.text('1 euro · 2003'), findsOneWidget);
      expect(find.text('brillo original'), findsOneWidget);

      await tester.binding.handlePopRoute(); // botón "atrás" del sistema
      await tester.pumpAndSettle();
      expect(find.text('1 euro · 2003'), findsOneWidget);
    });

    testWidgets('borrar pide confirmación; cancelar no borra (RF-11)', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro');
      await arrancar(tester);
      await irAColeccion(tester);
      await tester.tap(find.text('1 euro'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('ficha.borrar')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancelar'));
      await tester.pumpAndSettle();
      expect(backend.monedas[_email], hasLength(1));

      await tester.tap(find.byKey(const Key('ficha.borrar')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ficha.confirmarBorrado')));
      await tester.pumpAndSettle();

      expect(backend.monedas[_email], isEmpty);
      expect(find.textContaining('Tu colección está vacía'), findsOneWidget);
    });

    testWidgets('sin red el listado lo dice y permite reintentar', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro');
      await arrancar(tester);
      backend.sinRed = true;
      await irAColeccion(tester);
      expect(find.textContaining('No se pudo conectar'), findsOneWidget);

      backend.sinRed = false;
      await tester.tap(find.text('Reintentar'));
      await tester.pumpAndSettle();
      expect(find.text('1 euro'), findsOneWidget);
    });

    testWidgets('la ficha muestra la foto descargada con el token', (tester) async {
      backend.anadirMoneda(_email, pais: 'España', valor: '1 euro', conFoto: true);
      await arrancar(tester);
      await irAColeccion(tester);
      await tester.tap(find.text('1 euro'));
      await tester.pumpAndSettle();

      expect(find.text('Anverso'), findsOneWidget);
      expect(find.byType(Image), findsWidgets);
      expect(backend.peticiones, contains('GET /coleccion/1/imagenes/anverso'));
    });
  });
}
