import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// Backend en memoria que imita los endpoints usados por la app (mismas
/// rutas, códigos y formas de JSON que backend/app/rutas). Se enchufa como
/// adaptador HTTP de Dio, así los tests ejercitan el [ClienteApi] real
/// (cabeceras, refresco de token, traducción de errores).
class BackendFalso implements HttpClientAdapter {
  final _contrasenas = <String, String>{}; // email → contraseña
  final _usuarioIds = <String, int>{};
  final _accesos = <String, String>{}; // access token válido → email
  final _refrescos = <String, String>{}; // refresh token válido → email
  final monedas = <String, List<Map<String, dynamic>>>{}; // email → monedas
  final fotos = <String, Uint8List>{}; // ruta → bytes
  int _siguienteId = 1;
  int _siguienteToken = 1;

  /// Cuántas veces se llamó a /auth/refresco.
  int refrescos = 0;

  /// Simula estar sin red: toda petición falla sin respuesta.
  bool sinRed = false;

  /// Rutas pedidas, en orden (p. ej. "GET /coleccion").
  final peticiones = <String>[];

  // --- Preparación desde los tests ---

  void crearUsuario(String email, String contrasena) {
    _contrasenas[email] = contrasena;
    _usuarioIds[email] = _usuarioIds.length + 1;
    monedas[email] = [];
  }

  /// Da tokens válidos para [email] sin pasar por /auth/login.
  ({String acceso, String refresco}) emitirTokens(String email) {
    final acceso = 'acceso-${_siguienteToken++}';
    final refresco = 'refresco-${_siguienteToken++}';
    _accesos[acceso] = email;
    _refrescos[refresco] = email;
    return (acceso: acceso, refresco: refresco);
  }

  /// Simula que caducan todos los access tokens (el refresco sigue valiendo).
  void caducarAccesos() => _accesos.clear();

  /// Simula que caduca también el refresh token: la sesión no se puede renovar.
  void caducarTodo() {
    _accesos.clear();
    _refrescos.clear();
  }

  Map<String, dynamic> anadirMoneda(
    String email, {
    required String pais,
    required String valor,
    int? anio,
    String? ceca,
    String? variante,
    String? notas,
    String estado = 'en_coleccion',
    bool conFoto = false,
  }) {
    final id = _siguienteId++;
    final moneda = <String, dynamic>{
      'id': id,
      'pais': pais,
      'valor_texto': valor,
      'anio': anio,
      'ceca': ceca,
      'variante': variante,
      'notas': notas,
      'estado': estado,
      'foto_anverso': conFoto ? '/coleccion/$id/imagenes/anverso' : null,
      'foto_reverso': null,
      'foto_detalle': null,
      'fecha_agregada': '2026-10-03T12:00:00Z',
    };
    if (conFoto) fotos['/coleccion/$id/imagenes/anverso'] = _pngTransparente;
    monedas[email]!.add(moneda);
    return moneda;
  }

  // --- HttpClientAdapter ---

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    peticiones.add('${options.method} ${options.path}');
    if (sinRed) throw Exception('sin red');

    final ruta = options.path;
    final metodo = options.method;
    final datos = options.data is Map ? Map<String, dynamic>.from(options.data as Map) : null;

    switch ((metodo, ruta)) {
      case ('POST', '/auth/registro'):
        final email = datos!['email'] as String;
        if (_contrasenas.containsKey(email)) return _detalle(409, 'Ese email ya está registrado');
        crearUsuario(email, datos['contrasena'] as String);
        return _tokens(email, 201);
      case ('POST', '/auth/login'):
        final email = datos!['email'] as String;
        if (_contrasenas[email] != datos['contrasena']) {
          return _detalle(401, 'Email o contraseña incorrectos');
        }
        return _tokens(email);
      case ('POST', '/auth/refresco'):
        refrescos++;
        final email = _refrescos.remove(datos!['refresh_token']);
        if (email == null) return _detalle(401, 'Token de refresco inválido o expirado');
        return _tokens(email);
    }

    final cabecera = options.headers['Authorization'] as String?;
    final email = _accesos[cabecera?.replaceFirst('Bearer ', '')];
    if (email == null) return _detalle(401, 'No autenticado');
    final suyas = monedas[email]!;

    if (metodo == 'GET' && ruta == '/auth/yo') {
      return _json({'id': _usuarioIds[email], 'email': email, 'creado_en': '2026-10-01T10:00:00Z'});
    }
    if (ruta == '/coleccion') {
      if (metodo == 'GET') return _json(_filtrar(suyas, options.queryParameters));
      if (metodo == 'POST') {
        final choque = _duplicada(suyas, datos!);
        if (choque != null) return _duplicado(choque);
        return _json(
          anadirMoneda(
            email,
            pais: datos['pais'] as String,
            valor: datos['valor_texto'] as String,
            anio: datos['anio'] as int?,
            ceca: datos['ceca'] as String?,
            variante: datos['variante'] as String?,
            notas: datos['notas'] as String?,
            estado: datos['estado'] as String,
          ),
          201,
        );
      }
    }
    final foto = RegExp(r'^/coleccion/\d+/imagenes/\w+$').hasMatch(ruta) ? fotos[ruta] : null;
    if (foto != null && metodo == 'GET') {
      return ResponseBody.fromBytes(
        foto,
        200,
        headers: {
          Headers.contentTypeHeader: ['image/png'],
        },
      );
    }
    final id = int.tryParse(RegExp(r'^/coleccion/(\d+)$').firstMatch(ruta)?.group(1) ?? '');
    final moneda = suyas.where((m) => m['id'] == id).firstOrNull;
    if (id != null) {
      if (metodo == 'DELETE') {
        suyas.remove(moneda);
        return ResponseBody.fromString('', 204);
      }
      if (moneda == null) return _detalle(404, 'No existe esa moneda');
      if (metodo == 'GET') return _json(moneda);
      if (metodo == 'PATCH') {
        final editada = {...moneda, ...datos!};
        final choque = _duplicada(suyas.where((m) => m['id'] != id), editada);
        if (choque != null) return _duplicado(choque);
        moneda.addAll(datos);
        return _json(moneda);
      }
    }
    return _detalle(404, 'Not Found');
  }

  @override
  void close({bool force = false}) {}

  // --- Ayudas ---

  static String _norm(Object? v) => (v as String? ?? '').trim().toLowerCase();

  static String _tipo(Map<String, dynamic> m) => [
    _norm(m['pais']),
    _norm(m['valor_texto']),
    m['anio'],
    _norm(m['ceca']),
    _norm(m['variante']),
  ].join('|');

  Map<String, dynamic>? _duplicada(
    Iterable<Map<String, dynamic>> monedas,
    Map<String, dynamic> m,
  ) => monedas.where((otra) => _tipo(otra) == _tipo(m)).firstOrNull;

  List<Map<String, dynamic>> _filtrar(List<Map<String, dynamic>> monedas, Map<String, dynamic> q) {
    bool contiene(Object? campo, Object? buscado) =>
        buscado == null || _norm(campo).contains(_norm(buscado));
    return monedas.where((m) {
      final texto = q['texto'];
      final coincideTexto =
          texto == null ||
          ['pais', 'valor_texto', 'ceca', 'variante', 'notas'].any((c) => contiene(m[c], texto));
      return coincideTexto &&
          contiene(m['pais'], q['pais']) &&
          contiene(m['valor_texto'], q['valor']) &&
          (q['anio'] == null || m['anio'] == q['anio']) &&
          (q['estado'] == null || m['estado'] == q['estado']);
    }).toList();
  }

  ResponseBody _tokens(String email, [int codigo = 200]) {
    final t = emitirTokens(email);
    return _json({
      'access_token': t.acceso,
      'refresh_token': t.refresco,
      'token_type': 'bearer',
    }, codigo);
  }

  ResponseBody _duplicado(Map<String, dynamic> existente) => _json({
    'detail': {
      'mensaje': 'Ya existe un tipo igual en tu colección',
      'existente_id': existente['id'],
    },
  }, 409);

  ResponseBody _detalle(int codigo, String detalle) => _json({'detail': detalle}, codigo);

  ResponseBody _json(Object cuerpo, [int codigo = 200]) => ResponseBody.fromString(
    jsonEncode(cuerpo),
    codigo,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

// PNG de 1×1 transparente, para las fotos de prueba.
final _pngTransparente = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
);
