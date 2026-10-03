import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import 'foto_moneda.dart';
import 'pantalla_formulario.dart';

/// Ficha de una moneda (RF-10): campos, fotos y notas, con editar y borrar.
class PantallaFicha extends StatefulWidget {
  const PantallaFicha({super.key, required this.monedaId});

  final int monedaId;

  @override
  State<PantallaFicha> createState() => _PantallaFichaState();
}

class _PantallaFichaState extends State<PantallaFicha> {
  Moneda? _moneda;
  String? _error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_moneda == null && _error == null) _cargar();
  }

  Future<void> _cargar() async {
    setState(() => _error = null);
    try {
      final moneda = await AmbitoSesion.api(context).obtener(widget.monedaId);
      if (mounted) setState(() => _moneda = moneda);
    } on ErrorApi catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    }
  }

  Future<void> _editar() async {
    final editada = await Navigator.of(context)
        .push<Moneda>(MaterialPageRoute(builder: (_) => PantallaFormulario(moneda: _moneda)));
    if (editada != null && mounted) {
      setState(() => _moneda = editada);
    }
  }

  /// RF-11: borrar siempre con confirmación.
  Future<void> _borrar() async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Borrar esta moneda?'),
        content: const Text(
          'Se borrará de tu colección junto con sus fotos. No se puede deshacer.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          FilledButton(
            key: const Key('ficha.confirmarBorrado'),
            style: FilledButton.styleFrom(backgroundColor: Theme.of(context).colorScheme.error),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Borrar'),
          ),
        ],
      ),
    );
    if (confirmado != true || !mounted) return;

    final navegador = Navigator.of(context);
    final mensajero = ScaffoldMessenger.of(context);
    try {
      await AmbitoSesion.api(context).borrar(widget.monedaId);
      mensajero.showSnackBar(const SnackBar(content: Text('Moneda borrada')));
      navegador.pop();
    } on ErrorApi catch (e) {
      mensajero.showSnackBar(SnackBar(content: Text(e.mensaje)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final moneda = _moneda;
    return Scaffold(
      appBar: AppBar(
        title: Text(moneda?.titulo ?? 'Moneda'),
        actions: [
          if (moneda != null) ...[
            IconButton(
              key: const Key('ficha.editar'),
              tooltip: 'Editar',
              icon: const Icon(Icons.edit_outlined),
              onPressed: _editar,
            ),
            IconButton(
              key: const Key('ficha.borrar'),
              tooltip: 'Borrar',
              icon: const Icon(Icons.delete_outline),
              onPressed: _borrar,
            ),
          ],
        ],
      ),
      body: SafeArea(child: _cuerpo(context, moneda)),
    );
  }

  Widget _cuerpo(BuildContext context, Moneda? moneda) {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              OutlinedButton(onPressed: _cargar, child: const Text('Reintentar')),
            ],
          ),
        ),
      );
    }
    if (moneda == null) return const Center(child: CircularProgressIndicator());

    final tema = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (moneda.fotos.isEmpty)
          const ClipRRect(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            child: SinFoto(tamano: 160),
          )
        else
          SizedBox(
            height: 200,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                for (final MapEntry(key: cara, value: ruta) in moneda.fotos.entries)
                  Padding(
                    padding: const EdgeInsets.only(right: 12),
                    child: Column(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: FotoMoneda(ruta: ruta, tamano: 170),
                        ),
                        const SizedBox(height: 4),
                        Text(carasMoneda[cara]!, style: tema.textTheme.labelMedium),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        const SizedBox(height: 16),
        _fila('País', moneda.pais),
        _fila('Valor', moneda.valorTexto),
        _fila('Año', moneda.anio?.toString()),
        _fila('Ceca', moneda.ceca),
        _fila('Variante', moneda.variante),
        _fila('Estado', etiquetaEstado(moneda.estado)),
        _fila(
          'Añadida',
          MaterialLocalizations.of(context).formatShortDate(moneda.fechaAgregada.toLocal()),
        ),
        if (moneda.notas != null && moneda.notas!.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text('Notas', style: tema.textTheme.titleSmall),
          const SizedBox(height: 4),
          Text(moneda.notas!),
        ],
      ],
    );
  }

  Widget _fila(String etiqueta, String? valor) {
    final tema = Theme.of(context);
    final vacio = valor == null || valor.isEmpty;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(
              etiqueta,
              style: tema.textTheme.bodyMedium?.copyWith(color: tema.colorScheme.onSurfaceVariant),
            ),
          ),
          Expanded(
            child: Text(
              vacio ? '—' : valor,
              style: tema.textTheme.bodyLarge?.copyWith(
                color: vacio ? tema.colorScheme.onSurfaceVariant : null,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
