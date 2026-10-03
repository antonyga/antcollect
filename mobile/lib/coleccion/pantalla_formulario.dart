import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import 'pantalla_ficha.dart';

/// Alta manual (RF-6) y edición (RF-10/RF-12) de una moneda. Nada se guarda
/// hasta que el usuario pulsa "Guardar" sobre los campos (principio rector).
///
/// Devuelve la [Moneda] guardada con `Navigator.pop`, o nada si se cancela.
class PantallaFormulario extends StatefulWidget {
  const PantallaFormulario({super.key, this.moneda});

  /// `null` = alta nueva; si no, edición de esta moneda.
  final Moneda? moneda;

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
  bool _guardando = false;

  bool get _esEdicion => widget.moneda != null;

  @override
  void initState() {
    super.initState();
    final m = widget.moneda;
    _pais = TextEditingController(text: m?.pais);
    _valor = TextEditingController(text: m?.valorTexto);
    _anio = TextEditingController(text: m?.anio?.toString());
    _ceca = TextEditingController(text: m?.ceca);
    _variante = TextEditingController(text: m?.variante);
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

  Future<void> _guardar() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _guardando = true);
    final api = AmbitoSesion.api(context);
    final navegador = Navigator.of(context);
    TipoDuplicadoError? duplicado;
    try {
      final guardada = _esEdicion
          ? await api.editar(widget.moneda!.id, _datos())
          : await api.crear(_datos());
      navegador.pop(guardada);
    } on TipoDuplicadoError catch (e) {
      duplicado = e;
    } on ErrorApi catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
      }
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
    if (duplicado != null && mounted) await _avisarDuplicado(duplicado);
  }

  /// RF-14: el tipo ya existe. Se ofrece ver la que ya tienes, sin guardar.
  Future<void> _avisarDuplicado(TipoDuplicadoError e) async {
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
    if (verla == true && mounted) {
      await Navigator.of(context)
          .push(MaterialPageRoute<void>(builder: (_) => PantallaFicha(monedaId: e.existenteId)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_esEdicion ? 'Editar moneda' : 'Nueva moneda')),
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
                _campo(_pais, 'País', clave: 'pais', obligatorio: true),
                _campo(
                  _valor,
                  'Valor',
                  clave: 'valor',
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
                  onPressed: _guardando ? null : _guardar,
                  icon: _guardando
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check),
                  label: Text(_esEdicion ? 'Guardar cambios' : 'Guardar en mi colección'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _campo(
    TextEditingController controlador,
    String etiqueta, {
    required String clave,
    bool obligatorio = false,
    String? ayuda,
    TextInputType? teclado,
    int lineas = 1,
    FormFieldValidator<String>? validador,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        key: Key('form.$clave'),
        controller: controlador,
        decoration: InputDecoration(
          labelText: obligatorio ? '$etiqueta *' : etiqueta,
          helperText: ayuda,
          border: const OutlineInputBorder(),
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
