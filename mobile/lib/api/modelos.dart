// Modelos de la API (espejo de backend/app/esquemas.py). Dominio en español,
// igual que el backend y la v1 (CLAUDE.md §4).

/// Estados posibles de una moneda (RF-12). Clave = valor en la API.
const estadosMoneda = <String, String>{
  'en_coleccion': 'En colección',
  'duplicada': 'Duplicada',
  'para_intercambio': 'Para intercambio',
};

String etiquetaEstado(String estado) => estadosMoneda[estado] ?? estado;

/// Caras de una moneda con foto (RF-7/RF-8).
const carasMoneda = <String, String>{
  'anverso': 'Anverso',
  'reverso': 'Reverso',
  'detalle': 'Detalle',
};

class ParDeTokens {
  const ParDeTokens({required this.accessToken, required this.refreshToken});

  final String accessToken;
  final String refreshToken;

  factory ParDeTokens.fromJson(Map<String, dynamic> json) => ParDeTokens(
    accessToken: json['access_token'] as String,
    refreshToken: json['refresh_token'] as String,
  );
}

class Usuario {
  const Usuario({required this.id, required this.email, required this.creadoEn});

  final int id;
  final String email;
  final DateTime creadoEn;

  factory Usuario.fromJson(Map<String, dynamic> json) => Usuario(
    id: json['id'] as int,
    email: json['email'] as String,
    creadoEn: DateTime.parse(json['creado_en'] as String),
  );
}

class Moneda {
  const Moneda({
    required this.id,
    required this.pais,
    required this.valorTexto,
    required this.anio,
    required this.ceca,
    required this.variante,
    required this.notas,
    required this.estado,
    required this.fotos,
    required this.fechaAgregada,
  });

  final int id;
  final String pais;
  final String valorTexto;
  final int? anio;
  final String? ceca;
  final String? variante;
  final String? notas;
  final String estado;

  /// Cara → ruta autenticada de descarga (solo las caras que tienen foto).
  final Map<String, String> fotos;
  final DateTime fechaAgregada;

  /// Copia con otras fotos (p. ej. tras borrar una).
  Moneda conFotos(Map<String, String> fotos) => Moneda(
    id: id,
    pais: pais,
    valorTexto: valorTexto,
    anio: anio,
    ceca: ceca,
    variante: variante,
    notas: notas,
    estado: estado,
    fotos: fotos,
    fechaAgregada: fechaAgregada,
  );

  /// "2 euros · 2002" — título corto para listados.
  String get titulo => anio == null ? valorTexto : '$valorTexto · $anio';

  /// "España · ceca M · variante X" — línea secundaria para listados.
  String get subtitulo => [
    pais,
    if (ceca != null && ceca!.isNotEmpty) 'ceca $ceca',
    if (variante != null && variante!.isNotEmpty) variante!,
  ].join(' · ');

  factory Moneda.fromJson(Map<String, dynamic> json) => Moneda(
    id: json['id'] as int,
    pais: json['pais'] as String,
    valorTexto: json['valor_texto'] as String,
    anio: json['anio'] as int?,
    ceca: json['ceca'] as String?,
    variante: json['variante'] as String?,
    notas: json['notas'] as String?,
    estado: json['estado'] as String,
    fotos: {
      for (final cara in carasMoneda.keys)
        if (json['foto_$cara'] != null) cara: json['foto_$cara'] as String,
    },
    fechaAgregada: DateTime.parse(json['fecha_agregada'] as String),
  );
}

/// Campos que el usuario confirma antes de guardar (MonedaEntrada en el
/// backend). La app nunca crea ni edita sin que el humano pulse "Guardar"
/// sobre estos campos (principio rector, CLAUDE.md §2).
class DatosMoneda {
  const DatosMoneda({
    required this.pais,
    required this.valorTexto,
    this.anio,
    this.ceca,
    this.variante,
    this.notas,
    this.estado = 'en_coleccion',
  });

  final String pais;
  final String valorTexto;
  final int? anio;
  final String? ceca;
  final String? variante;
  final String? notas;
  final String estado;

  factory DatosMoneda.desde(Moneda m) => DatosMoneda(
    pais: m.pais,
    valorTexto: m.valorTexto,
    anio: m.anio,
    ceca: m.ceca,
    variante: m.variante,
    notas: m.notas,
    estado: m.estado,
  );

  /// Todos los campos, también los nulos: en un PATCH un `null` explícito
  /// vacía el campo (p. ej. quitar la ceca), que es lo que el usuario quiere
  /// al borrar el texto del formulario.
  Map<String, dynamic> toJson() => {
    'pais': pais,
    'valor_texto': valorTexto,
    'anio': anio,
    'ceca': ceca,
    'variante': variante,
    'notas': notas,
    'estado': estado,
  };
}

/// Filtros del listado (RF-9), mismos parámetros que `GET /coleccion`.
class FiltrosColeccion {
  const FiltrosColeccion({this.texto, this.pais, this.valor, this.anio, this.estado});

  final String? texto;
  final String? pais;
  final String? valor;
  final int? anio;
  final String? estado;

  bool get hayFiltrosAvanzados => pais != null || valor != null || anio != null || estado != null;

  Map<String, dynamic> toQuery() => {
    if (texto != null) 'texto': texto,
    if (pais != null) 'pais': pais,
    if (valor != null) 'valor': valor,
    if (anio != null) 'anio': anio,
    if (estado != null) 'estado': estado,
  };
}

/// Campos propuestos por la lectura IA (`POST /lecturas`). Solo es una
/// propuesta: rellena el formulario, y nada se guarda ni se consulta hasta
/// que el usuario la revisa (principio rector, RF-3).
class LecturaPropuesta {
  const LecturaPropuesta({
    this.pais,
    this.valorTexto,
    this.anio,
    this.ceca,
    this.variante,
    this.camposDudosos = const [],
    this.fallida = false,
    this.restantesHoy,
  });

  final String? pais;
  final String? valorTexto;
  final int? anio;
  final String? ceca;
  final String? variante;

  /// Campos (nombres de la API: `pais`, `valor_texto`, `anio`, `ceca`,
  /// `variante`) que la IA no leyó con seguridad: se resaltan para revisarlos.
  final List<String> camposDudosos;

  /// La IA no pudo leer la moneda: se pasa al modo manual (RF-6).
  final bool fallida;
  final int? restantesHoy;

  factory LecturaPropuesta.fromJson(Map<String, dynamic> json) => LecturaPropuesta(
    pais: json['pais'] as String?,
    valorTexto: json['valor_texto'] as String?,
    anio: json['anio'] as int?,
    ceca: json['ceca'] as String?,
    variante: json['variante'] as String?,
    camposDudosos: [for (final c in json['campos_dudosos'] as List<dynamic>) c as String],
    fallida: json['fallida'] as bool,
    restantesHoy: json['lecturas_restantes_hoy'] as int?,
  );
}

/// Lecturas IA que le quedan hoy al usuario (RF-M3).
class CuotaLecturas {
  const CuotaLecturas({
    required this.limiteDiario,
    required this.usadasHoy,
    required this.restantesHoy,
  });

  final int limiteDiario;
  final int usadasHoy;
  final int restantesHoy;

  factory CuotaLecturas.fromJson(Map<String, dynamic> json) => CuotaLecturas(
    limiteDiario: json['limite_diario'] as int,
    usadasHoy: json['usadas_hoy'] as int,
    restantesHoy: json['restantes_hoy'] as int,
  );
}

enum CategoriaComprobacion { exacta, parcial, ninguna }

/// Respuesta de "¿la tengo?" (RF-2), `POST /coleccion/comprobar`.
class ResultadoComprobacion {
  const ResultadoComprobacion({required this.categoria, this.exacta, this.posibles = const []});

  final CategoriaComprobacion categoria;

  /// La moneda que coincide en los 5 campos (solo si la categoría es exacta).
  final Moneda? exacta;

  /// Tipos parecidos (mismo país y valor, y año si lo hay): decide el humano.
  final List<Moneda> posibles;

  factory ResultadoComprobacion.fromJson(Map<String, dynamic> json) => ResultadoComprobacion(
    categoria: CategoriaComprobacion.values.byName(json['categoria'] as String),
    exacta: json['exacta'] == null ? null : Moneda.fromJson(json['exacta'] as Map<String, dynamic>),
    posibles: [
      for (final m in json['posibles'] as List<dynamic>) Moneda.fromJson(m as Map<String, dynamic>),
    ],
  );
}

/// Archivo descargado de `GET /exportar` (RF-13).
class ArchivoExportado {
  const ArchivoExportado({required this.bytes, required this.nombre, required this.tipo});

  final List<int> bytes;
  final String nombre;
  final String tipo;
}
