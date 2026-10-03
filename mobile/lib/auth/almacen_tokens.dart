import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/modelos.dart';

/// Dónde se guardan los tokens de sesión entre arranques de la app.
abstract class AlmacenTokens {
  Future<ParDeTokens?> leer();
  Future<void> guardar(ParDeTokens tokens);
  Future<void> borrar();
}

/// Producción: Keychain (iOS) / Keystore cifrado (Android). Los tokens nunca
/// van a SharedPreferences ni a disco en claro.
class AlmacenTokensSeguro implements AlmacenTokens {
  AlmacenTokensSeguro([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _claveAcceso = 'antcollect.access_token';
  static const _claveRefresco = 'antcollect.refresh_token';

  @override
  Future<ParDeTokens?> leer() async {
    final acceso = await _storage.read(key: _claveAcceso);
    final refresco = await _storage.read(key: _claveRefresco);
    if (acceso == null || refresco == null) return null;
    return ParDeTokens(accessToken: acceso, refreshToken: refresco);
  }

  @override
  Future<void> guardar(ParDeTokens tokens) async {
    await _storage.write(key: _claveAcceso, value: tokens.accessToken);
    await _storage.write(key: _claveRefresco, value: tokens.refreshToken);
  }

  @override
  Future<void> borrar() async {
    await _storage.delete(key: _claveAcceso);
    await _storage.delete(key: _claveRefresco);
  }
}

/// Tests: en memoria.
class AlmacenTokensMemoria implements AlmacenTokens {
  AlmacenTokensMemoria([this.tokens]);

  ParDeTokens? tokens;

  @override
  Future<ParDeTokens?> leer() async => tokens;

  @override
  Future<void> guardar(ParDeTokens tokens) async => this.tokens = tokens;

  @override
  Future<void> borrar() async => tokens = null;
}
