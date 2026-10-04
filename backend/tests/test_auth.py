"""Tests de autenticación (RF-M1) y, sobre todo, de aislamiento entre
usuarios (RNF-M1) — la propiedad nueva más crítica de la v2 respecto a la v1
de un solo usuario: ningún usuario debe poder ver ni modificar la colección
de otro.
"""

from __future__ import annotations


async def _registrar(cliente, email: str, contrasena: str = "contrasena123") -> dict:
    r = await cliente.post("/auth/registro", json={"email": email, "contrasena": contrasena})
    assert r.status_code == 201, r.text
    return r.json()


def _cabecera(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_registro_devuelve_tokens(cliente):
    tokens = await _registrar(cliente, "ana@example.com")
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"


async def test_registro_con_email_repetido_falla(cliente):
    await _registrar(cliente, "ana@example.com")

    r = await cliente.post(
        "/auth/registro", json={"email": "ana@example.com", "contrasena": "otra12345"}
    )
    assert r.status_code == 409


async def test_login_correcto(cliente):
    await _registrar(cliente, "ana@example.com", "contrasena123")

    r = await cliente.post(
        "/auth/login", json={"email": "ana@example.com", "contrasena": "contrasena123"}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_login_con_contrasena_incorrecta_falla(cliente):
    await _registrar(cliente, "ana@example.com", "contrasena123")

    r = await cliente.post("/auth/login", json={"email": "ana@example.com", "contrasena": "mala"})
    assert r.status_code == 401


async def test_login_con_email_inexistente_falla(cliente):
    r = await cliente.post(
        "/auth/login", json={"email": "nadie@example.com", "contrasena": "x12345678"}
    )
    assert r.status_code == 401


async def test_endpoint_protegido_sin_token_devuelve_401(cliente):
    r = await cliente.get("/auth/yo")
    assert r.status_code == 401


async def test_endpoint_protegido_con_token_invalido_devuelve_401(cliente):
    r = await cliente.get("/auth/yo", headers={"Authorization": "Bearer esto-no-es-un-jwt"})
    assert r.status_code == 401


async def test_refresco_emite_un_nuevo_access_token(cliente):
    tokens = await _registrar(cliente, "ana@example.com")

    r = await cliente.post("/auth/refresco", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_refresco_con_un_access_token_en_vez_de_refresh_falla(cliente):
    tokens = await _registrar(cliente, "ana@example.com")

    r = await cliente.post("/auth/refresco", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


async def test_borrar_cuenta_invalida_el_token(cliente):
    tokens = await _registrar(cliente, "ana@example.com")
    headers = _cabecera(tokens)

    r = await cliente.post(
        "/auth/cuenta/borrar", json={"contrasena": "contrasena123"}, headers=headers
    )
    assert r.status_code == 204

    r = await cliente.get("/auth/yo", headers=headers)
    assert r.status_code == 401


async def test_borrar_cuenta_exige_la_contrasena(cliente):
    """Con un token válido pero sin la contraseña correcta no se borra nada.
    403 y no 401: el cliente no debe confundirlo con una sesión caducada."""
    tokens = await _registrar(cliente, "ana@example.com")
    headers = _cabecera(tokens)

    r = await cliente.post(
        "/auth/cuenta/borrar", json={"contrasena": "no-es-la-mia"}, headers=headers
    )
    assert r.status_code == 403

    r = await cliente.get("/auth/yo", headers=headers)
    assert r.status_code == 200


async def test_borrar_cuenta_borra_tambien_su_coleccion(cliente):
    tokens = await _registrar(cliente, "ana@example.com")
    headers = _cabecera(tokens)
    await cliente.post(
        "/coleccion", json={"pais": "España", "valor_texto": "2 euros"}, headers=headers
    )

    r = await cliente.post(
        "/auth/cuenta/borrar", json={"contrasena": "contrasena123"}, headers=headers
    )
    assert r.status_code == 204

    # Re-registrar el mismo email tras borrar la cuenta debe ser posible
    # (confirma que no quedó ningún rastro de la cuenta anterior).
    tokens2 = await _registrar(cliente, "ana@example.com")
    r = await cliente.get("/coleccion", headers=_cabecera(tokens2))
    assert r.json() == []


async def test_dos_usuarios_pueden_tener_el_mismo_tipo_sin_chocar(cliente):
    """RNF-M1: la unicidad de "tipo" (RF-14) es por usuario, no global."""
    tokens_a = await _registrar(cliente, "alicia@example.com")
    tokens_b = await _registrar(cliente, "benito@example.com")
    datos = {"pais": "España", "valor_texto": "2 euros", "anio": 2002}

    r1 = await cliente.post("/coleccion", json=datos, headers=_cabecera(tokens_a))
    r2 = await cliente.post("/coleccion", json=datos, headers=_cabecera(tokens_b))

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


async def test_un_usuario_no_puede_ver_la_moneda_de_otro(cliente):
    tokens_a = await _registrar(cliente, "alicia@example.com")
    tokens_b = await _registrar(cliente, "benito@example.com")
    r = await cliente.post(
        "/coleccion",
        json={"pais": "España", "valor_texto": "2 euros", "anio": 2002},
        headers=_cabecera(tokens_a),
    )
    moneda_id = r.json()["id"]

    r = await cliente.get(f"/coleccion/{moneda_id}", headers=_cabecera(tokens_b))
    assert r.status_code == 404


async def test_un_usuario_no_puede_borrar_la_moneda_de_otro(cliente):
    tokens_a = await _registrar(cliente, "alicia@example.com")
    tokens_b = await _registrar(cliente, "benito@example.com")
    r = await cliente.post(
        "/coleccion",
        json={"pais": "España", "valor_texto": "2 euros", "anio": 2002},
        headers=_cabecera(tokens_a),
    )
    moneda_id = r.json()["id"]

    await cliente.delete(f"/coleccion/{moneda_id}", headers=_cabecera(tokens_b))

    # Sigue existiendo para su dueña real.
    r = await cliente.get(f"/coleccion/{moneda_id}", headers=_cabecera(tokens_a))
    assert r.status_code == 200


async def test_listado_de_cada_usuario_no_incluye_monedas_de_otro(cliente):
    tokens_a = await _registrar(cliente, "alicia@example.com")
    tokens_b = await _registrar(cliente, "benito@example.com")
    await cliente.post(
        "/coleccion", json={"pais": "España", "valor_texto": "2 euros"}, headers=_cabecera(tokens_a)
    )
    await cliente.post(
        "/coleccion", json={"pais": "Francia", "valor_texto": "1 euro"}, headers=_cabecera(tokens_b)
    )

    r_a = await cliente.get("/coleccion", headers=_cabecera(tokens_a))
    r_b = await cliente.get("/coleccion", headers=_cabecera(tokens_b))

    assert [m["pais"] for m in r_a.json()] == ["España"]
    assert [m["pais"] for m in r_b.json()] == ["Francia"]
