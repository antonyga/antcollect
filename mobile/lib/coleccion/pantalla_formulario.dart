import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import '../captura/flujo.dart';
import '../captura/guardado.dart';
import '../captura/pantalla_resultado.dart';
import '../captura/selector_fotos.dart';

/// Paso "confirmar" del pipeline capturar → leer → confirmar (RF-3), y
/// también la edición de una moneda guardada (RF-10/RF-12).
///
/// Los campos pueden venir propuestos por la IA ([propuesta]); los dudosos se
/// resaltan. Nada se guarda ni se consulta hasta que el usuario pulsa el botón
/// final sobre los campos ya revisados (principio rector):
/// - [ModoFlujo.ensenar]: "Guardar en mi colección" (RF-1).
/// - [ModoFlujo.comprobar]: "Buscar en mi colección" → resultado (RF-2).
///
/// Devuelve la [Moneda] guardada con `Navigator.pop`, o nada si no se guarda.
class PantallaFormulario extends StatefulWidget {
  const PantallaFormulario({
    super.key,
    this.moneda,
    this.modo = ModoFlujo.ensenar,
    this.propuesta,
    this.aviso,
    this.fotos = const {},
  });

  /// `null` = moneda nueva; si no, edición de esta moneda.
  final Moneda? moneda;
  final ModoFlujo modo;

  /// Campos propuestos por la IA, si se leyó la moneda.
  final LecturaPropuesta? propuesta;

  /// Por qué se rellena a mano (cuota agotada, IA no disponible, sin red...).
  final String? aviso;

  /// Fotos hechas en el paso de captura (cara → bytes).
  final Map<String, Uint8List> fotos;

  @override
  State<PantallaFormulario> createState() => _PantallaFormularioState();
}

class _PantallaFormularioState extends State<PantallaFormulario> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _pais;
  late final TextEditingController _valor;
  late final TextEditingController _anio;
  late final TextEditingController _ceca;
  late final TextEditingController _variante;
  late final TextEditingController _notas;
  late String _estado;
  late final Map<String, Uint8List> _fotosNuevas = {...widget.fotos};
  final _fotosQuitadas = <String>{};
  bool _enviando = false;

  bool get _esEdicion => widget.moneda != null;
  bool get _comprobar => !_esEdicion && widget.modo == ModoFlujo.comprobar;
  List<String> get _dudosos => widget.propuesta?.camposDudosos ?? const [];

  @override
  void initState() {
    super.initState();
    final m = widget.moneda;
    final p = widget.propuesta;
    _pais = TextEditingController(text: m?.pais ?? p?.pais);
    _valor = TextEditingController(text: m?.valorTexto ?? p?.valorTexto);
    _anio = TextEditingController(text: (m?.anio ?? p?.anio)?.toString());
    _ceca = TextEditingController(text: m?.ceca ?? p?.ceca);
    _variante = TextEditingController(text: m?.variante ?? p?.variante);
    _notas = TextEditingController(text: m?.notas);
    _estado = m?.estado ?? 'en_coleccion';
  }

  @override
  void dispose() {
    for (final c in [_pais, _valor, _anio, _ceca, _variante, _notas]) {
      c.dispose();
    }
    super.dispose();
  }

  static String? _opcional(TextEditingController c) {
    final texto = c.text.trim();
    return texto.isEmpty ? null : texto;
  }

  DatosMoneda _datos() => DatosMoneda(
    pais: _pais.text.trim(),
    valorTexto: _valor.text.trim(),
    anio: int.tryParse(_anio.text.trim()),
    ceca: _opcional(_ceca),
    variante: _opcional(_variante),
    notas: _opcional(_notas),
    estado: _estado,
  );

  /// Fotos guardadas que se siguen mostrando (al editar).
  Map<String, String> get _fotosGuardadas => {
    for (final MapEntry(key: cara, value: ruta) in (widget.moneda?.fotos ?? const {}).entries)
      if (!_fotosQuitadas.contains(cara)) cara: ruta,
  };

  Future<void> _enviar() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _enviando = true);
    try {
      if (_comprobar) {
        await _buscar();
      } else if (_esEdicion) {
        await _guardarEdicion();
      } else {
        final guardada = await guardarMonedaNueva(context, _datos(), _fotosNuevas);
        if (guardada != null && mounted) Navigator.of(context).pop(guardada);
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _guardarEdicion() async {
    final navegador = Navigator.of(context);
    Moneda editada;
    try {
      editada = await AmbitoSesion.api(context).editar(widget.moneda!.id, _datos());
    } on TipoDuplicadoError catch (e) {
      if (mounted) unawaited(avisarDuplicado(context, e));
      return;
    } on ErrorApi catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
      }
      return;
    }
    if (!mounted) return;
    editada = await actualizarFotos(context, editada, _fotosNuevas, _fotosQuitadas);
    navegador.pop(editada);
  }

  /// "¿La tengo?" con los campos ya revisados por el usuario (RF-2).
  Future<void> _buscar() async {
    final datos = _datos();
    final navegador = Navigator.of(context);
    ResultadoComprobacion resultado;
    try {
      resultado = await AmbitoSesion.api(context).comprobar(datos);
    } on ErrorApi catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
      }
      return;
    }
    final guardada = await navegador.push<Moneda>(
      MaterialPageRoute(
        builder: (_) =>
            PantallaResultado(datos: datos, fotos: {..._fotosNuevas}, resultado: resultado),
      ),
    );
    if (guardada != null) navegador.pop(guardada);
  }

  String get _titulo => _esEdicion
      ? 'Editar moneda'
      : _comprobar
      ? '¿La tengo?'
      : 'Nueva moneda';

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(_titulo)),
      body: SafeArea(
        child: Form(
          key: _form,
          // Column, no ListView: un ListView no construye los campos fuera de
          // pantalla y Form.validate() se saltaría sus validaciones.
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.aviso != null)
                  _Aviso(
                    key: const Key('form.aviso'),
                    icono: Icons.edit_note,
                    texto: widget.aviso!,
                  ),
                if (widget.propuesta != null) _avisoPropuesta(),
                Text('Fotos', style: tema.textTheme.titleSmall),
                const SizedBox(height: 8),
                SelectorFotos(
                  nuevas: _fotosNuevas,
                  guardadas: _fotosGuardadas,
                  alElegir: (cara, bytes) => setState(() => _fotosNuevas[cara] = bytes),
                  alQuitar: (cara) => setState(() {
                    _fotosNuevas.remove(cara);
                    _fotosQuitadas.add(cara);
                  }),
                ),
                const SizedBox(height: 24),
                _campo(_pais, 'País', clave: 'pais', obligatorio: true),
                _campo(
                  _valor,
                  'Valor',
                  clave: 'valor',
                  campoApi: 'valor_texto',
                  obligatorio: true,
                  ayuda: 'Por ejemplo: 2 euros, 50 céntimos',
                ),
                _campo(
                  _anio,
                  'Año',
                  clave: 'anio',
                  teclado: TextInputType.number,
                  ayuda: 'Déjalo vacío si no se lee',
                  validador: (v) {
                    final texto = v?.trim() ?? '';
                    if (texto.isEmpty) return null;
                    final anio = int.tryParse(texto);
                    if (anio == null || anio < 1 || anio > DateTime.now().year) {
                      return 'Escribe un año válido (p. ej. 2002)';
                    }
                    return null;
                  },
                ),
                _campo(
                  _ceca,
                  'Ceca',
                  clave: 'ceca',
                  ayuda: 'Marca de la casa de moneda, si la tiene',
                ),
                _campo(_variante, 'Variante', clave: 'variante'),
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: DropdownButtonFormField<String>(
                    key: const Key('form.estado'),
                    initialValue: _estado,
                    decoration: const InputDecoration(
                      labelText: 'Estado',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      for (final e in estadosMoneda.entries)
                        DropdownMenuItem(value: e.key, child: Text(e.value)),
                    ],
                    onChanged: (v) => setState(() => _estado = v!),
                  ),
                ),
                _campo(_notas, 'Notas', clave: 'notas', lineas: 4),
                const SizedBox(height: 8),
                FilledButton.icon(
                  key: const Key('form.guardar'),
                  onPressed: _enviando ? null : _enviar,
                  icon: _enviando
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(_comprobar ? Icons.search : Icons.check),
                  label: Text(
                    _esEdicion
                        ? 'Guardar cambios'
                        : _comprobar
                        ? 'Buscar en mi colección'
                        : 'Guardar en mi colección',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Lenguaje de propuesta, nunca de resultado (CLAUDE.md §2).
  Widget _avisoPropuesta() {
    final accion = _comprobar ? 'buscar' : 'guardar';
    final nombres = [for (final c in _dudosos) _nombresCampos[c] ?? c].join(', ');
    return _Aviso(
      key: const Key('form.propuesta'),
      icono: Icons.auto_awesome_outlined,
      texto: _dudosos.isEmpty
          ? 'Campos propuestos por la IA. Revísalos antes de $accion.'
          : 'Campos propuestos por la IA. Revisa especialmente: $nombres.',
    );
  }

  static const _nombresCampos = {
    'pais': 'país',
    'valor_texto': 'valor',
    'anio': 'año',
    'ceca': 'ceca',
    'variante': 'variante',
  };

  Widget _campo(
    TextEditingController controlador,
    String etiqueta, {
    required String clave,
    String? campoApi,
    bool obligatorio = false,
    String? ayuda,
    TextInputType? teclado,
    int lineas = 1,
    FormFieldValidator<String>? validador,
  }) {
    final dudoso = _dudosos.contains(campoApi ?? clave);
    final tema = Theme.of(context);
    final aviso = tema.brightness == Brightness.dark
        ? Colors.orange.shade300
        : Colors.orange.shade900;
    final base = obligatorio ? '$etiqueta *' : etiqueta;
    final bordeAviso = OutlineInputBorder(borderSide: BorderSide(color: aviso, width: 2));
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        key: Key('form.$clave'),
        controller: controlador,
        decoration: InputDecoration(
          labelText: dudoso ? '$base — revisar' : base,
          helperText: dudoso ? 'La IA no lo leyó con seguridad: compruébalo en la moneda' : ayuda,
          helperMaxLines: 2,
          prefixIcon: dudoso ? Icon(Icons.warning_amber_rounded, color: aviso) : null,
          labelStyle: dudoso ? TextStyle(color: aviso) : null,
          helperStyle: dudoso ? TextStyle(color: aviso) : null,
          border: const OutlineInputBorder(),
          enabledBorder: dudoso ? bordeAviso : null,
          focusedBorder: dudoso ? bordeAviso : null,
        ),
        keyboardType: lineas > 1 ? TextInputType.multiline : teclado,
        minLines: lineas > 1 ? 2 : 1,
        maxLines: lineas,
        textCapitalization: TextCapitalization.sentences,
        validator:
            validador ??
            (obligatorio
                ? (v) => (v == null || v.trim().isEmpty) ? 'Este campo es obligatorio' : null
                : null),
      ),
    );
  }
}

class _Aviso extends StatelessWidget {
  const _Aviso({super.key, required this.icono, required this.texto});

  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Card(
        margin: EdgeInsets.zero,
        color: esquema.secondaryContainer,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(icono, color: esquema.onSecondaryContainer),
              const SizedBox(width: 12),
              Expanded(
                child: Text(texto, style: TextStyle(color: esquema.onSecondaryContainer)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
