import 'package:flutter/material.dart';

import '../auth/sesion.dart';
import '../captura/flujo.dart';
import '../coleccion/pantalla_listado.dart';

/// Pantalla de inicio: los dos flujos de la v1 (comprobar y enseñar) y la
/// colección.
class PantallaInicio extends StatelessWidget {
  const PantallaInicio({super.key});

  Future<void> _confirmarCierre(BuildContext context) async {
    final sesion = AmbitoSesion.leer(context);
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Cerrar sesión?'),
        content: const Text('Tu colección sigue guardada en tu cuenta.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cerrar sesión'),
          ),
        ],
      ),
    );
    if (confirmado == true) await sesion.cerrarSesion();
  }

  @override
  Widget build(BuildContext context) {
    final sesion = AmbitoSesion.de(context);
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('AntCollect'),
        actions: [
          PopupMenuButton<void>(
            key: const Key('inicio.menu'),
            icon: const Icon(Icons.account_circle_outlined),
            tooltip: 'Cuenta',
            itemBuilder: (context) => [
              PopupMenuItem(enabled: false, child: Text(sesion.usuario?.email ?? '')),
              const PopupMenuDivider(),
              PopupMenuItem(
                key: const Key('inicio.cerrarSesion'),
                onTap: () => _confirmarCierre(context),
                child: const ListTile(
                  leading: Icon(Icons.logout),
                  title: Text('Cerrar sesión'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            // Desplazable: en pantallas bajas (o en horizontal) no caben
            // los tres botones.
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    '¿Qué quieres hacer?',
                    style: tema.textTheme.headlineSmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),
                  _BotonGrande(
                    key: const Key('inicio.comprobar'),
                    icono: Icons.manage_search,
                    titulo: '¿La tengo?',
                    detalle: 'Hazle una foto a una moneda y comprueba si ya está en tu colección',
                    onPressed: () => abrirFlujo(context, ModoFlujo.comprobar),
                  ),
                  const SizedBox(height: 16),
                  _BotonGrande(
                    key: const Key('inicio.nueva'),
                    icono: Icons.add_a_photo_outlined,
                    titulo: 'Enseñar moneda nueva',
                    detalle: 'Hazle una foto y añádela a tu colección',
                    onPressed: () => abrirFlujo(context, ModoFlujo.ensenar),
                  ),
                  const SizedBox(height: 16),
                  _BotonGrande(
                    key: const Key('inicio.coleccion'),
                    icono: Icons.collections_bookmark_outlined,
                    titulo: 'Mi colección',
                    detalle: 'Busca, revisa y edita tus monedas',
                    onPressed: () =>
                        Navigator.of(context)
                            .push(MaterialPageRoute<void>(builder: (_) => const PantallaListado())),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _BotonGrande extends StatelessWidget {
  const _BotonGrande({
    super.key,
    required this.icono,
    required this.titulo,
    required this.detalle,
    required this.onPressed,
  });

  final IconData icono;
  final String titulo;
  final String detalle;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onPressed,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icono, size: 40, color: tema.colorScheme.primary),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(titulo, style: tema.textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text(
                      detalle,
                      style: tema.textTheme.bodyMedium?.copyWith(
                        color: tema.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
