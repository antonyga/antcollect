import 'package:flutter/widgets.dart';

import '../api/cliente_api.dart';
import '../api/modelos.dart';
import 'almacen_tokens.dart';

enum EstadoSesion { comprobando, sinSesion, conSesion }

/// Estado de la sesión del usuario (RF-M1). La colección vive en el backend
/// (RF-M2): aquí solo se guarda quién ha iniciado sesión.
class Sesion extends ChangeNotifier {
  Sesion({required this.api, required this._tokens}) {
    api.alCaducarSesion = _alCaducar;
  }

  final ClienteApi api;
  final AlmacenTokens _tokens;

  EstadoSesion _estado = EstadoSesion.comprobando;
  EstadoSesion get estado => _estado;

  Usuario? _usuario;
  Usuario? get usuario => _usuario;

  /// Al arrancar: si hay tokens guardados, comprueba que siguen valiendo.
  Future<void> restaurar() async {
    if (await _tokens.leer() == null) {
      return _cambiar(EstadoSesion.sinSesion);
    }
    try {
      _usuario = await api.yo();
      _cambiar(EstadoSesion.conSesion);
    } on ErrorApi catch (e) {
      // Sin red no se cierra la sesión: los tokens siguen guardados y se
      // reintenta en el próximo arranque.
      if (!e.sinConexion) await _tokens.borrar();
      _cambiar(EstadoSesion.sinSesion);
    }
  }

  Future<void> iniciarSesion(String email, String contrasena) async {
    await _entrar(await api.login(email, contrasena));
  }

  Future<void> registrarse(String email, String contrasena) async {
    await _entrar(await api.registro(email, contrasena));
  }

  Future<void> cerrarSesion() async {
    await _tokens.borrar();
    _usuario = null;
    _cambiar(EstadoSesion.sinSesion);
  }

  Future<void> _entrar(ParDeTokens tokens) async {
    await _tokens.guardar(tokens);
    _usuario = await api.yo();
    _cambiar(EstadoSesion.conSesion);
  }

  void _alCaducar() {
    _usuario = null;
    _cambiar(EstadoSesion.sinSesion);
  }

  void _cambiar(EstadoSesion estado) {
    _estado = estado;
    notifyListeners();
  }
}

/// Da acceso a la [Sesion] (y a su [ClienteApi]) desde cualquier pantalla.
class AmbitoSesion extends InheritedNotifier<Sesion> {
  const AmbitoSesion({super.key, required Sesion sesion, required super.child})
    : super(notifier: sesion);

  static Sesion de(BuildContext context) {
    final ambito = context.dependOnInheritedWidgetOfExactType<AmbitoSesion>();
    assert(ambito != null, 'No hay AmbitoSesion por encima de este widget');
    return ambito!.notifier!;
  }

  /// Sin suscribirse a cambios (para callbacks como onPressed).
  static Sesion leer(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AmbitoSesion>()!.notifier!;

  static ClienteApi api(BuildContext context) => leer(context).api;
}
