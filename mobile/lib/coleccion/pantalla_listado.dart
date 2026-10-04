import 'dart:async';

import 'package:flutter/material.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import '../auth/sesion.dart';
import '../captura/dispositivo.dart';
import '../captura/flujo.dart';
import 'foto_moneda.dart';
import 'pantalla_ficha.dart';

/// Listado de la colección con búsqueda de texto y filtros por país, valor,
/// año y estado (RF-9). Siempre pide los datos al backend (RF-M2: la misma
/// colección desde cualquier dispositivo).
class PantallaListado extends StatefulWidget {
  const PantallaListado({super.key});

  @override
  State<PantallaListado> createState() => _PantallaListadoState();
}

class _PantallaListadoState extends State<PantallaListado> {
  final _busqueda = TextEditingController();
  Timer? _esperaBusqueda;
  FiltrosColeccion _filtros = const FiltrosColeccion();
  List<Moneda>? _monedas;
  String? _error;
  int _peticion = 0; // descarta respuestas de búsquedas ya superadas

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_monedas == null && _error == null) _cargar();
  }

  @override
  void dispose() {
    _esperaBusqueda?.cancel();
    _busqueda.dispose();
    super.dispose();
  }

  Future<void> _cargar() async {
    final peticion = ++_peticion;
    setState(() => _error = null);
    try {
      final monedas = await AmbitoSesion.api(context).listar(_filtros);
      if (mounted && peticion == _peticion) setState(() => _monedas = monedas);
    } on ErrorApi catch (e) {
      if (mounted && peticion == _peticion) setState(() => _error = e.mensaje);
    }
  }

  void _alEscribir(String texto) {
    _esperaBusqueda?.cancel();
    _esperaBusqueda = Timer(const Duration(milliseconds: 350), () {
      final limpio = texto.trim();
      _aplicar(
        FiltrosColeccion(
          texto: limpio.isEmpty ? null : limpio,
          pais: _filtros.pais,
          valor: _filtros.valor,
          anio: _filtros.anio,
          estado: _filtros.estado,
        ),
      );
    });
  }

  void _aplicar(FiltrosColeccion filtros) {
    setState(() => _filtros = filtros);
    _cargar();
  }

  Future<void> _abrirFiltros() async {
    final filtros = await showModalBottomSheet<FiltrosColeccion>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _HojaFiltros(filtros: _filtros),
    );
    if (filtros != null) _aplicar(filtros);
  }

  /// Al volver de la ficha se recarga siempre: la moneda puede haberse
  /// editado o borrado allí.
  Future<void> _abrir(Moneda moneda) async {
    await Navigator.of(context)
        .push<void>(MaterialPageRoute(builder: (_) => PantallaFicha(monedaId: moneda.id)));
    _cargar();
  }

  Future<void> _nueva() async {
    await abrirFlujo(context, ModoFlujo.ensenar);
    _cargar();
  }

  /// RF-13: toda la colección en CSV o JSON, entregada con la hoja de
  /// compartir del sistema (guardar en archivos, enviar por correo...).
  Future<void> _exportar(String formato) async {
    final api = AmbitoSesion.api(context);
    final dispositivo = AmbitoDispositivo.de(context);
    final mensajero = ScaffoldMessenger.of(context);
    try {
      final archivo = await api.exportar(formato);
      await dispositivo.compartirArchivo(archivo.bytes, nombre: archivo.nombre, tipo: archivo.tipo);
    } on ErrorApi catch (e) {
      mensajero.showSnackBar(SnackBar(content: Text(e.mensaje)));
    } on Exception {
      mensajero.showSnackBar(
        const SnackBar(content: Text('No se pudo compartir el archivo exportado.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi colección'),
        actions: [
          PopupMenuButton<String>(
            key: const Key('listado.exportar'),
            icon: const Icon(Icons.ios_share),
            tooltip: 'Exportar colección',
            onSelected: _exportar,
            itemBuilder: (context) => const [
              PopupMenuItem(
                key: Key('listado.exportar.csv'),
                value: 'csv',
                child: Text('Exportar como CSV (hoja de cálculo)'),
              ),
              PopupMenuItem(
                key: Key('listado.exportar.json'),
                value: 'json',
                child: Text('Exportar como JSON'),
              ),
            ],
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),
            child: Row(
              children: [
                Expanded(
                  child: SearchBar(
                    key: const Key('listado.busqueda'),
                    controller: _busqueda,
                    hintText: 'Buscar país, valor, ceca, notas…',
                    leading: const Icon(Icons.search),
                    elevation: const WidgetStatePropertyAll(0),
                    onChanged: _alEscribir,
                  ),
                ),
                IconButton(
                  key: const Key('listado.filtros'),
                  tooltip: 'Filtros',
                  onPressed: _abrirFiltros,
                  icon: Badge(
                    isLabelVisible: _filtros.hayFiltrosAvanzados,
                    child: const Icon(Icons.tune),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        key: const Key('listado.nueva'),
        tooltip: 'Añadir moneda',
        onPressed: _nueva,
        child: const Icon(Icons.add),
      ),
      body: SafeArea(child: _cuerpo(context)),
    );
  }

  Widget _cuerpo(BuildContext context) {
    final monedas = _monedas;
    if (_error != null && monedas == null) {
      return _Mensaje(
        icono: Icons.cloud_off_outlined,
        texto: _error!,
        accion: OutlinedButton(onPressed: _cargar, child: const Text('Reintentar')),
      );
    }
    if (monedas == null) return const Center(child: CircularProgressIndicator());

    final hayFiltros = _filtros.texto != null || _filtros.hayFiltrosAvanzados;
    return RefreshIndicator(
      onRefresh: _cargar,
      child: monedas.isEmpty
          ? ListView(
              children: [
                const SizedBox(height: 80),
                _Mensaje(
                  icono: hayFiltros ? Icons.search_off : Icons.collections_bookmark_outlined,
                  texto: hayFiltros
                      ? 'Ninguna moneda coincide con la búsqueda.'
                      : 'Tu colección está vacía.\nAñade tu primera moneda con el botón +.',
                ),
              ],
            )
          : ListView.separated(
              padding: const EdgeInsets.only(bottom: 88),
              itemCount: monedas.length + 1,
              separatorBuilder: (_, i) =>
                  i == 0 ? const SizedBox.shrink() : const Divider(height: 1, indent: 88),
              itemBuilder: (context, i) {
                if (i == 0) {
                  return Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                    child: Text(
                      monedas.length == 1 ? '1 moneda' : '${monedas.length} monedas',
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                  );
                }
                return _FilaMoneda(moneda: monedas[i - 1], onTap: () => _abrir(monedas[i - 1]));
              },
            ),
    );
  }
}

class _FilaMoneda extends StatelessWidget {
  const _FilaMoneda({required this.moneda, required this.onTap});

  final Moneda moneda;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final foto = moneda.fotos['anverso'] ?? moneda.fotos.values.firstOrNull;
    return ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: foto == null ? const SinFoto(tamano: 56) : FotoMoneda(ruta: foto, tamano: 56),
      ),
      title: Text(moneda.titulo),
      subtitle: Text(moneda.subtitulo, maxLines: 1, overflow: TextOverflow.ellipsis),
      trailing: moneda.estado == 'en_coleccion' ? null : _EtiquetaEstado(moneda.estado),
    );
  }
}

/// Etiqueta informativa (no interactiva: un Chip se anunciaría como casilla
/// en los lectores de pantalla).
class _EtiquetaEstado extends StatelessWidget {
  const _EtiquetaEstado(this.estado);

  final String estado;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: esquema.secondaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Text(
          etiquetaEstado(estado),
          style: Theme.of(context).textTheme.labelMedium
              ?.copyWith(color: esquema.onSecondaryContainer),
        ),
      ),
    );
  }
}

class _Mensaje extends StatelessWidget {
  const _Mensaje({required this.icono, required this.texto, this.accion});

  final IconData icono;
  final String texto;
  final Widget? accion;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icono, size: 48, color: tema.colorScheme.onSurfaceVariant),
            const SizedBox(height: 12),
            Text(texto, textAlign: TextAlign.center, style: tema.textTheme.bodyLarge),
            if (accion != null) ...[const SizedBox(height: 16), accion!],
          ],
        ),
      ),
    );
  }
}

/// Filtros avanzados del listado (RF-9). El texto de búsqueda se mantiene.
class _HojaFiltros extends StatefulWidget {
  const _HojaFiltros({required this.filtros});

  final FiltrosColeccion filtros;

  @override
  State<_HojaFiltros> createState() => _HojaFiltrosState();
}

class _HojaFiltrosState extends State<_HojaFiltros> {
  late final _pais = TextEditingController(text: widget.filtros.pais);
  late final _valor = TextEditingController(text: widget.filtros.valor);
  late final _anio = TextEditingController(text: widget.filtros.anio?.toString());
  late String? _estado = widget.filtros.estado;

  @override
  void dispose() {
    _pais.dispose();
    _valor.dispose();
    _anio.dispose();
    super.dispose();
  }

  static String? _texto(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  void _aplicar() => Navigator.pop(
    context,
    FiltrosColeccion(
      texto: widget.filtros.texto,
      pais: _texto(_pais),
      valor: _texto(_valor),
      anio: int.tryParse(_anio.text.trim()),
      estado: _estado,
    ),
  );

  void _limpiar() => Navigator.pop(context, FiltrosColeccion(texto: widget.filtros.texto));

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Filtros', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          TextField(
            key: const Key('filtros.pais'),
            controller: _pais,
            decoration: const InputDecoration(labelText: 'País', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('filtros.valor'),
            controller: _valor,
            decoration: const InputDecoration(labelText: 'Valor', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('filtros.anio'),
            controller: _anio,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Año', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String?>(
            initialValue: _estado,
            decoration: const InputDecoration(labelText: 'Estado', border: OutlineInputBorder()),
            items: [
              const DropdownMenuItem(value: null, child: Text('Todos')),
              for (final e in estadosMoneda.entries)
                DropdownMenuItem(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) => setState(() => _estado = v),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(onPressed: _limpiar, child: const Text('Quitar filtros')),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  key: const Key('filtros.aplicar'),
                  onPressed: _aplicar,
                  child: const Text('Aplicar'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
