import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/modelos.dart';
import '../coleccion/foto_moneda.dart';
import '../coleccion/pantalla_ficha.dart';
import 'guardado.dart';

/// Resultado de "¿la tengo?" (RF-2) sobre los campos que el usuario revisó:
/// - exacta → "Ya la tienes", con la tuya al lado de la encontrada (RF-4).
/// - ninguna → "No la tienes" y "Guardar esta" con los mismos campos (RF-5).
/// - parcial → "Posible coincidencia": tipos parecidos, decide el humano.
///
/// Devuelve con `Navigator.pop` la [Moneda] si el usuario la guarda.
class PantallaResultado extends StatefulWidget {
  const PantallaResultado({
    super.key,
    required this.datos,
    required this.fotos,
    required this.resultado,
  });

  /// Campos confirmados con los que se buscó.
  final DatosMoneda datos;

  /// Fotos de la moneda encontrada (cara → bytes), para comparar y guardar.
  final Map<String, Uint8List> fotos;
  final ResultadoComprobacion resultado;

  @override
  State<PantallaResultado> createState() => _PantallaResultadoState();
}

class _PantallaResultadoState extends State<PantallaResultado> {
  bool _guardando = false;

  /// RF-5: guarda reutilizando los campos ya confirmados y las fotos.
  Future<void> _guardar() async {
    setState(() => _guardando = true);
    final guardada = await guardarMonedaNueva(context, widget.datos, widget.fotos);
    if (!mounted) return;
    setState(() => _guardando = false);
    if (guardada != null) Navigator.of(context).pop(guardada);
  }

  void _abrir(Moneda moneda) =>
      Navigator.of(context)
          .push(MaterialPageRoute<void>(builder: (_) => PantallaFicha(monedaId: moneda.id)));

  @override
  Widget build(BuildContext context) {
    final r = widget.resultado;
    return Scaffold(
      appBar: AppBar(title: const Text('¿La tengo?')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: switch (r.categoria) {
                CategoriaComprobacion.exacta => _exacta(r.exacta!),
                CategoriaComprobacion.ninguna => _ninguna(),
                CategoriaComprobacion.parcial => _parcial(r.posibles),
              },
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _exacta(Moneda tuya) => [
    const _Cabecera(
      clave: 'resultado.exacta',
      icono: Icons.check_circle_outline,
      titulo: 'Ya la tienes',
      texto: 'Coincide en país, valor, año, ceca y variante con una moneda de tu colección.',
    ),
    const SizedBox(height: 16),
    _Comparacion(encontrada: widget.fotos['anverso'], tuya: tuya.fotos['anverso']),
    if (widget.fotos.containsKey('reverso') || tuya.fotos.containsKey('reverso')) ...[
      const SizedBox(height: 12),
      _Comparacion(encontrada: widget.fotos['reverso'], tuya: tuya.fotos['reverso']),
    ],
    const SizedBox(height: 16),
    _TarjetaMoneda(moneda: tuya, alPulsar: () => _abrir(tuya)),
    const SizedBox(height: 16),
    FilledButton.icon(
      key: const Key('resultado.verFicha'),
      onPressed: () => _abrir(tuya),
      icon: const Icon(Icons.open_in_new),
      label: const Text('Ver la que ya tengo'),
    ),
  ];

  List<Widget> _ninguna() => [
    const _Cabecera(
      clave: 'resultado.ninguna',
      icono: Icons.fiber_new_outlined,
      titulo: 'No la tienes',
      texto: 'No hay ningún tipo igual en tu colección. Puedes guardarla como nueva.',
    ),
    const SizedBox(height: 16),
    _Buscada(datos: widget.datos, foto: widget.fotos['anverso']),
    const SizedBox(height: 16),
    _botonGuardar('Guardar esta'),
  ];

  List<Widget> _parcial(List<Moneda> posibles) => [
    const _Cabecera(
      clave: 'resultado.parcial',
      icono: Icons.help_outline,
      titulo: 'Posible coincidencia',
      texto:
          'Tienes tipos parecidos, pero no coinciden con seguridad en los cinco campos. '
          'Fíjate en el año, la ceca y la variante, y decide tú si es la misma moneda.',
    ),
    const SizedBox(height: 16),
    _Buscada(datos: widget.datos, foto: widget.fotos['anverso']),
    const SizedBox(height: 16),
    Text('Parecidas en tu colección', style: Theme.of(context).textTheme.titleSmall),
    const SizedBox(height: 8),
    for (final m in posibles)
      Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: _TarjetaMoneda(
          moneda: m,
          diferencias: _diferencias(widget.datos, m),
          alPulsar: () => _abrir(m),
        ),
      ),
    const SizedBox(height: 8),
    _botonGuardar('No es ninguna: guardar como nueva'),
  ];

  Widget _botonGuardar(String texto) => FilledButton.icon(
    key: const Key('resultado.guardar'),
    onPressed: _guardando ? null : _guardar,
    icon: _guardando
        ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
        : const Icon(Icons.add),
    label: Text(texto),
  );

  /// Qué campos del tipo no coinciden (comparación aproximada, solo para
  /// orientar al usuario; la decisión exacta la tomó el backend).
  static List<String> _diferencias(DatosMoneda buscada, Moneda m) {
    String n(Object? v) => (v?.toString() ?? '').trim().toLowerCase();
    return [
      if (n(buscada.anio) != n(m.anio)) 'año',
      if (n(buscada.ceca) != n(m.ceca)) 'ceca',
      if (n(buscada.variante) != n(m.variante)) 'variante',
    ];
  }
}

class _Cabecera extends StatelessWidget {
  const _Cabecera({
    required this.clave,
    required this.icono,
    required this.titulo,
    required this.texto,
  });

  final String clave;
  final IconData icono;
  final String titulo;
  final String texto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final esquema = tema.colorScheme;
    return Card(
      key: Key(clave),
      margin: EdgeInsets.zero,
      color: esquema.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icono, size: 36, color: esquema.onPrimaryContainer),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    style: tema.textTheme.titleLarge?.copyWith(color: esquema.onPrimaryContainer),
                  ),
                  const SizedBox(height: 4),
                  Text(texto, style: TextStyle(color: esquema.onPrimaryContainer)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// La moneda encontrada al lado de la de la colección (RF-4).
class _Comparacion extends StatelessWidget {
  const _Comparacion({required this.encontrada, required this.tuya});

  final Uint8List? encontrada;
  final String? tuya;

  @override
  Widget build(BuildContext context) {
    final encontradaFoto = encontrada;
    final tuyaFoto = tuya;
    return Row(
      children: [
        Expanded(
          child: _FotoConPie(
            pie: 'La que has encontrado',
            foto: encontradaFoto != null
                ? Image.memory(encontradaFoto, fit: BoxFit.cover)
                : const SinFoto(),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _FotoConPie(
            pie: 'La de tu colección',
            foto: tuyaFoto != null ? FotoMoneda(ruta: tuyaFoto) : const SinFoto(),
          ),
        ),
      ],
    );
  }
}

class _FotoConPie extends StatelessWidget {
  const _FotoConPie({required this.pie, required this.foto});

  final String pie;
  final Widget foto;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      AspectRatio(
        aspectRatio: 1,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox.expand(child: foto),
        ),
      ),
      const SizedBox(height: 4),
      Text(pie, style: Theme.of(context).textTheme.labelMedium, textAlign: TextAlign.center),
    ],
  );
}

/// Resumen de lo que se buscó.
class _Buscada extends StatelessWidget {
  const _Buscada({required this.datos, required this.foto});

  final DatosMoneda datos;
  final Uint8List? foto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final f = foto;
    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        contentPadding: const EdgeInsets.all(8),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: f != null
              ? Image.memory(f, width: 56, height: 56, fit: BoxFit.cover)
              : const SinFoto(tamano: 56),
        ),
        title: Text('La que has encontrado', style: tema.textTheme.labelMedium),
        subtitle: Text(_descripcion(datos), style: tema.textTheme.bodyLarge),
      ),
    );
  }

  static String _descripcion(DatosMoneda d) => [
    d.valorTexto,
    if (d.anio != null) '${d.anio}' else 'año sin leer',
    d.pais,
    if (d.ceca != null) 'ceca ${d.ceca}',
    if (d.variante != null) d.variante!,
  ].join(' · ');
}

class _TarjetaMoneda extends StatelessWidget {
  const _TarjetaMoneda({required this.moneda, required this.alPulsar, this.diferencias = const []});

  final Moneda moneda;
  final VoidCallback alPulsar;
  final List<String> diferencias;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final ruta = moneda.fotos['anverso'];
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        contentPadding: const EdgeInsets.all(8),
        onTap: alPulsar,
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: ruta != null ? FotoMoneda(ruta: ruta, tamano: 56) : const SinFoto(tamano: 56),
        ),
        title: Text(moneda.titulo),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(moneda.subtitulo),
            if (diferencias.isNotEmpty)
              Text(
                'Distinto: ${diferencias.join(', ')}',
                style: tema.textTheme.bodySmall?.copyWith(
                  color: tema.colorScheme.tertiary,
                  fontWeight: FontWeight.w600,
                ),
              ),
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
