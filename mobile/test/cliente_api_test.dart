import 'package:antcollect/api/cliente_api.dart';
import 'package:antcollect/api/modelos.dart';
import 'package:antcollect/auth/almacen_tokens.dart';
import 'package:antcollect/auth/sesion.dart';
import 'package:flutter_test/flutter_test.dart';

import 'backend_falso.dart';

void main() {
  late BackendFalso backend;
  late AlmacenTokensMemoria tokens;
  late ClienteApi api;

  const email = 'ana@example.com';

  setUp(() {
    backend = BackendFalso()..crearUsuario(email, 'contrasena-segura');
    final t = backend.emitirTokens(email);
    tokens = AlmacenTokensMemoria(ParDeTokens(accessToken: t.acceso, refreshToken: t.refresco));
    api = ClienteApi(urlBase: 'http://api.test', tokens: tokens, adaptador: backend);
  });

  group('token de acceso', () {
    test('se envía en cada petición', () async {
      expect((await api.yo()).email, email);
    });

    test('si caduca, se renueva con el de refresco y se repite la petición', () async {
      backend.caducarAccesos();
      final accesoViejo = tokens.tokens!.accessToken;

      expect((await api.yo()).email, email);
      expect(backend.refrescos, 1);
      expect(tokens.tokens!.accessToken, isNot(accesoViejo));
      expect(backend.peticiones, ['GET /auth/yo', 'POST /auth/refresco', 'GET /auth/yo']);
    });

    test('varias peticiones a la vez con el token caducado renuevan una sola vez', () async {
      backend.anadirMoneda(email, pais: 'España', valor: '1 euro');
      backend.caducarAccesos();

      await Future.wait([api.yo(), api.listar(), api.yo()]);
      expect(backend.refrescos, 1);
    });

    test('si el refresco también caduca, se borran los tokens y se avisa', () async {
      var avisado = false;
      api.alCaducarSesion = () => avisado = true;
      backend.caducarTodo();

      await expectLater(api.yo(), throwsA(isA<ErrorApi>().having((e) => e.codigo, 'codigo', 401)));
      expect(avisado, isTrue);
      expect(tokens.tokens, isNull);
    });
  });

  group('errores', () {
    test('sin red da un ErrorApi sin código y un mensaje para el usuario', () async {
      backend.sinRed = true;
      await expectLater(
        api.listar(),
        throwsA(
          isA<ErrorApi>()
              .having((e) => e.sinConexion, 'sinConexion', isTrue)
              .having((e) => e.mensaje, 'mensaje', contains('conexión')),
        ),
      );
    });

    test(
      'guardar un tipo que ya existe da TipoDuplicadoError con el id existente (RF-14)',
      () async {
        final existente = backend.anadirMoneda(email, pais: 'España', valor: '2 euros', anio: 2002);
        await expectLater(
          api.crear(const DatosMoneda(pais: 'españa ', valorTexto: '2 Euros', anio: 2002)),
          throwsA(
            isA<TipoDuplicadoError>().having((e) => e.existenteId, 'existenteId', existente['id']),
          ),
        );
      },
    );

    test('login con contraseña incorrecta muestra el mensaje del backend', () async {
      await expectLater(
        api.login(email, 'mala'),
        throwsA(
          isA<ErrorApi>().having((e) => e.mensaje, 'mensaje', 'Email o contraseña incorrectos'),
        ),
      );
    });
  });

  group('colección', () {
    test('listar pasa los filtros como parámetros (RF-9)', () async {
      backend.anadirMoneda(email, pais: 'España', valor: '1 euro', anio: 2002);
      backend.anadirMoneda(email, pais: 'Francia', valor: '1 euro', anio: 2002);
      backend.anadirMoneda(
        email,
        pais: 'España',
        valor: '2 euros',
        anio: 2010,
        estado: 'duplicada',
      );

      expect((await api.listar(const FiltrosColeccion(pais: 'espa'))).length, 2);
      expect((await api.listar(const FiltrosColeccion(anio: 2002))).length, 2);
      expect(
        (await api.listar(const FiltrosColeccion(estado: 'duplicada'))).single.valorTexto,
        '2 euros',
      );
      expect((await api.listar(const FiltrosColeccion(texto: 'franc'))).single.pais, 'Francia');
    });

    test('editar envía los campos vaciados como null', () async {
      final m = backend.anadirMoneda(email, pais: 'España', valor: '1 euro', ceca: 'M');
      final editada = await api.editar(
        m['id'] as int,
        const DatosMoneda(pais: 'España', valorTexto: '1 euro'),
      );
      expect(editada.ceca, isNull);
    });

    test('las fotos se exponen por cara y se descargan con el token', () async {
      final m = backend.anadirMoneda(email, pais: 'España', valor: '1 euro', conFoto: true);
      final moneda = await api.obtener(m['id'] as int);
      expect(moneda.fotos.keys, ['anverso']);
      expect(await api.descargarFoto(moneda.fotos['anverso']!), isNotEmpty);
    });
  });

  group('sesión', () {
    test('restaurar con tokens válidos entra directamente', () async {
      final sesion = Sesion(api: api, tokens: tokens);
      await sesion.restaurar();
      expect(sesion.estado, EstadoSesion.conSesion);
      expect(sesion.usuario!.email, email);
    });

    test('restaurar sin red no borra los tokens (se reintenta al volver a abrir)', () async {
      backend.sinRed = true;
      final sesion = Sesion(api: api, tokens: tokens);
      await sesion.restaurar();
      expect(sesion.estado, EstadoSesion.sinSesion);
      expect(tokens.tokens, isNotNull);
    });

    test('restaurar con la sesión caducada del todo borra los tokens', () async {
      backend.caducarTodo();
      final sesion = Sesion(api: api, tokens: tokens);
      await sesion.restaurar();
      expect(sesion.estado, EstadoSesion.sinSesion);
      expect(tokens.tokens, isNull);
    });

    test('cerrar sesión borra los tokens guardados', () async {
      final sesion = Sesion(api: api, tokens: tokens);
      await sesion.restaurar();
      await sesion.cerrarSesion();
      expect(sesion.estado, EstadoSesion.sinSesion);
      expect(tokens.tokens, isNull);
    });
  });
}
