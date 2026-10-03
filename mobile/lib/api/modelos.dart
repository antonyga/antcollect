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
