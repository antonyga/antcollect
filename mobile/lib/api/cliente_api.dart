import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../auth/almacen_tokens.dart';
import 'modelos.dart';

/// Error de la API ya traducido a un mensaje para mostrar al usuario.
class ErrorApi implements Exception {
  const ErrorApi(this.mensaje, {this.codigo, this.detalle});

  final String mensaje;

  /// Código HTTP, o `null` si no hubo respuesta (sin red, timeout...).
  final int? codigo;

  /// `detail` de FastAPI cuando es un objeto (p. ej. el 409 de duplicado
  /// trae `existente_id`).
  final Map<String, dynamic>? detalle;

  bool get sinConexion => codigo == null;

  @override
  String toString() => 'ErrorApi($codigo): $mensaje';
}

/// La moneda que se intenta guardar ya existe en la colección (RF-14).
class TipoDuplicadoError extends ErrorApi {
  const TipoDuplicadoError(super.mensaje, {required this.existenteId}) : super(codigo: 409);

  final int existenteId;
}

/// Cliente HTTP de la API de AntCollect. Añade el token de acceso a cada
/// petición y, si caduca (401), lo renueva una vez con el token de refresco
/// y repite la petición. Si el refresco también falla, borra los tokens y
/// avisa con [alCaducarSesion] para volver a la pantalla de acceso.
class ClienteApi {
  ClienteApi({required this.urlBase, required this._tokens, HttpClientAdapter? adaptador}) {
    final opciones = BaseOptions(
      baseUrl: urlBase,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
    );
    _dio = Dio(opciones);
    _dioRefresco = Dio(opciones);
    if (adaptador != null) {
      _dio.httpClientAdapter = adaptador;
      _dioRefresco.httpClientAdapter = adaptador;
    }
    _dio.interceptors.add(
      QueuedInterceptorsWrapper(onRequest: _ponerToken, onError: _renovarSiCaduco),
    );
  }

  final String urlBase;
  final AlmacenTokens _tokens;
  late final Dio _dio;
  late final Dio _dioRefresco; // sin interceptores: evita bucles de refresco

  /// Se llama cuando la sesión ya no se puede renovar.
  void Function()? alCaducarSesion;

  static const _rutasSinToken = {'/auth/login', '/auth/registro', '/auth/refresco'};

  Future<void> _ponerToken(RequestOptions opciones, RequestInterceptorHandler handler) async {
    if (!_rutasSinToken.contains(opciones.path)) {
      final tokens = await _tokens.leer();
      if (tokens != null) {
        opciones.headers['Authorization'] = 'Bearer ${tokens.accessToken}';
      }
    }
    handler.next(opciones);
  }

  Future<void> _renovarSiCaduco(DioException error, ErrorInterceptorHandler handler) async {
    final opciones = error.requestOptions;
    if (error.response?.statusCode != 401 ||
        _rutasSinToken.contains(opciones.path) ||
        opciones.extra['reintentada'] == true) {
      return handler.next(error);
    }

    final tokens = await _tokens.leer();
    if (tokens == null) return handler.next(error);

    // Si otra petición en cola ya renovó el token mientras esta esperaba,
    // basta con repetirla con el nuevo.
    var acceso = tokens.accessToken;
    if (opciones.headers['Authorization'] == 'Bearer $acceso') {
      try {
        final respuesta = await _dioRefresco.post<Map<String, dynamic>>(
          '/auth/refresco',
          data: {'refresh_token': tokens.refreshToken},
        );
        final nuevos = ParDeTokens.fromJson(respuesta.data!);
        await _tokens.guardar(nuevos);
        acceso = nuevos.accessToken;
      } on DioException catch (e) {
        if (e.response?.statusCode == 401) {
          await _tokens.borrar();
          alCaducarSesion?.call();
        }
        return handler.next(error);
      }
    }

    opciones.headers['Authorization'] = 'Bearer $acceso';
    opciones.extra['reintentada'] = true;
    try {
      handler.resolve(await _dioRefresco.fetch(opciones));
    } on DioException catch (e) {
      handler.next(e);
    }
  }

  /// Ejecuta la petición traduciendo cualquier fallo a [ErrorApi].
  Future<T> _llamar<T>(Future<T> Function() peticion) async {
    try {
      return await peticion();
    } on DioException catch (e) {
      throw _traducir(e);
    }
  }

  static ErrorApi _traducir(DioException e) {
    final respuesta = e.response;
    if (respuesta == null) {
      return const ErrorApi(
        'No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.',
      );
    }
    final codigo = respuesta.statusCode;
    final datos = respuesta.data;
    final detalle = datos is Map ? datos['detail'] : null;

    if (codigo == 409 && detalle is Map && detalle['existente_id'] is int) {
      return TipoDuplicadoError(
        detalle['mensaje'] as String? ?? 'Ya existe un tipo igual en tu colección',
        existenteId: detalle['existente_id'] as int,
      );
    }
    if (detalle is String) {
      return ErrorApi(detalle, codigo: codigo);
    }
    if (codigo == 422) {
      return ErrorApi('Revisa los datos del formulario.', codigo: codigo);
    }
    if (codigo != null && codigo >= 500) {
      return ErrorApi('El servidor tuvo un problema. Inténtalo de nuevo.', codigo: codigo);
    }
    return ErrorApi(
      'Error inesperado ($codigo).',
      codigo: codigo,
      detalle: detalle is Map<String, dynamic> ? detalle : null,
    );
  }

  // --- Auth (RF-M1) ---

  Future<ParDeTokens> login(String email, String contrasena) => _llamar(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {'email': email, 'contrasena': contrasena},
    );
    return ParDeTokens.fromJson(r.data!);
  });

  Future<ParDeTokens> registro(String email, String contrasena) => _llamar(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/auth/registro',
      data: {'email': email, 'contrasena': contrasena},
    );
    return ParDeTokens.fromJson(r.data!);
  });

  Future<Usuario> yo() => _llamar(() async {
    final r = await _dio.get<Map<String, dynamic>>('/auth/yo');
    return Usuario.fromJson(r.data!);
  });

  /// Borra la cuenta, su colección y sus fotos. Pide la contraseña: si no
  /// coincide, el backend responde 403 ("Contraseña incorrecta").
  Future<void> borrarCuenta(String contrasena) =>
      _llamar(() => _dio.post<void>('/auth/cuenta/borrar', data: {'contrasena': contrasena}));

  /// Política de privacidad (`privacidad`) o términos (`terminos`), servidos
  /// por el propio backend (páginas públicas, sin token).
  Uri enlaceLegal(String pagina) => Uri.parse(urlBase).resolve('/$pagina');

  // --- Colección (RF-9, RF-10, RF-11, RF-12) ---

  Future<List<Moneda>> listar([FiltrosColeccion filtros = const FiltrosColeccion()]) =>
      _llamar(() async {
        final r = await _dio.get<List<dynamic>>('/coleccion', queryParameters: filtros.toQuery());
        return [for (final m in r.data!) Moneda.fromJson(m as Map<String, dynamic>)];
      });

  Future<Moneda> obtener(int id) => _llamar(() async {
    final r = await _dio.get<Map<String, dynamic>>('/coleccion/$id');
    return Moneda.fromJson(r.data!);
  });

  /// Lanza [TipoDuplicadoError] si ese tipo ya está en la colección.
  Future<Moneda> crear(DatosMoneda datos) => _llamar(() async {
    final r = await _dio.post<Map<String, dynamic>>('/coleccion', data: datos.toJson());
    return Moneda.fromJson(r.data!);
  });

  /// Lanza [TipoDuplicadoError] si la edición choca con otro tipo existente.
  Future<Moneda> editar(int id, DatosMoneda datos) => _llamar(() async {
    final r = await _dio.patch<Map<String, dynamic>>('/coleccion/$id', data: datos.toJson());
    return Moneda.fromJson(r.data!);
  });

  Future<void> borrar(int id) => _llamar(() => _dio.delete<void>('/coleccion/$id'));

  /// Descarga una foto por su ruta autenticada (`Moneda.fotos`).
  Future<Uint8List> descargarFoto(String ruta) => _llamar(() async {
    final r = await _dio.get<List<int>>(ruta, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  });

  /// Sube (o reemplaza) la foto de una cara (RF-7/RF-8). El backend la
  /// endereza, la reduce y le quita los metadatos.
  Future<Moneda> subirFoto(int id, String cara, Uint8List bytes) => _llamar(() async {
    final r = await _dio.put<Map<String, dynamic>>(
      '/coleccion/$id/imagenes/$cara',
      data: FormData.fromMap({'archivo': MultipartFile.fromBytes(bytes, filename: '$cara.jpg')}),
    );
    return Moneda.fromJson(r.data!);
  });

  Future<void> borrarFoto(int id, String cara) =>
      _llamar(() => _dio.delete<void>('/coleccion/$id/imagenes/$cara'));

  // --- Lectura IA y "¿la tengo?" (RF-1, RF-2, RF-M3) ---

  /// Pide a la IA que proponga los campos. La foto de detalle nunca se envía
  /// (RF-8). Lanza [ErrorApi] con código 429 (cuota agotada) o 503 (IA no
  /// disponible); en ambos casos, y sin red, la app pasa al modo manual.
  Future<LecturaPropuesta> leer(Uint8List anverso, {Uint8List? reverso}) => _llamar(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/lecturas',
      data: FormData.fromMap({
        'anverso': MultipartFile.fromBytes(anverso, filename: 'anverso.jpg'),
        if (reverso != null) 'reverso': MultipartFile.fromBytes(reverso, filename: 'reverso.jpg'),
      }),
      // La lectura puede encadenar varios proveedores de IA (respaldo).
      options: Options(receiveTimeout: const Duration(seconds: 120)),
    );
    return LecturaPropuesta.fromJson(r.data!);
  });

  Future<CuotaLecturas> cuota() => _llamar(() async {
    final r = await _dio.get<Map<String, dynamic>>('/lecturas/cuota');
    return CuotaLecturas.fromJson(r.data!);
  });

  /// "¿La tengo?" sobre los campos ya confirmados por el usuario.
  Future<ResultadoComprobacion> comprobar(DatosMoneda datos) => _llamar(() async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/coleccion/comprobar',
      data: {
        'pais': datos.pais,
        'valor_texto': datos.valorTexto,
        'anio': datos.anio,
        'ceca': datos.ceca,
        'variante': datos.variante,
      },
    );
    return ResultadoComprobacion.fromJson(r.data!);
  });

  // --- Exportación (RF-13) ---

  /// Descarga toda la colección como `csv` o `json`.
  Future<ArchivoExportado> exportar(String formato) => _llamar(() async {
    final r = await _dio.get<List<int>>(
      '/exportar',
      queryParameters: {'formato': formato},
      options: Options(responseType: ResponseType.bytes),
    );
    final disposicion = r.headers.value('content-disposition') ?? '';
    final nombre = RegExp(r'filename="([^"]+)"').firstMatch(disposicion)?.group(1);
    return ArchivoExportado(
      bytes: r.data!,
      nombre: nombre ?? 'antcollect.$formato',
      tipo: formato == 'csv' ? 'text/csv' : 'application/json',
    );
  });
}
