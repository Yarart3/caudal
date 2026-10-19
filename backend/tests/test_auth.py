"""Parte 2.3: tarjetas de usuarios, login, logout, /me y bloqueo tras intentos fallidos."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import User, UserSession

TEST_PASSWORD = "contrasena-de-prueba"  # la que pone make_user por defecto


def _login(client, username="gerard", password=TEST_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_users_returns_only_card_data(client, make_user):
    make_user("gerard", is_admin=True)
    make_user("padres", color="#3555A0")
    res = client.get("/api/auth/users")
    assert res.status_code == 200
    assert res.json() == [
        {"username": "gerard", "display_name": "Gerard", "initial": "G", "color": "#0E6B58"},
        {"username": "padres", "display_name": "Padres", "initial": "P", "color": "#3555A0"},
    ]


def test_login_logout_and_me(client, make_user):
    make_user("gerard", is_admin=True)
    assert client.get("/api/auth/me").status_code == 401

    res = _login(client)
    assert res.status_code == 200
    assert res.json() == {
        "username": "gerard",
        "display_name": "Gerard",
        "initial": "G",
        "color": "#0E6B58",
        "is_admin": True,
    }
    assert "caudal_session=" in res.headers["set-cookie"]

    # El TestClient guarda la cookie, como haría el navegador
    assert client.get("/api/auth/me").json()["username"] == "gerard"

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_logout_deletes_the_session_in_db(client, db, make_user):
    make_user("gerard")
    _login(client)
    assert db.scalars(select(UserSession)).first() is not None
    client.post("/api/auth/logout")
    assert db.scalars(select(UserSession)).first() is None


def test_wrong_password_and_unknown_user_give_the_same_error(client, make_user):
    make_user("gerard")
    for res in (_login(client, password="incorrecta"), _login(client, username="nadie")):
        assert res.status_code == 401
        assert res.json() == {"detail": "Usuario o contraseña incorrectos"}


def test_lock_after_5_failed_attempts(client, db, make_user):
    user = make_user("gerard")
    for _ in range(4):
        assert _login(client, password="incorrecta").status_code == 401

    res = _login(client, password="incorrecta")  # 5.º intento fallido
    assert res.status_code == 429
    assert res.json() == {"detail": "Demasiados intentos fallidos. Vuelve a probar en 5 minutos"}

    # Bloqueado: tampoco entra con la contraseña correcta
    assert _login(client).status_code == 429

    # Pasado el bloqueo, entra y el contador vuelve a cero
    db.refresh(user)
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert _login(client).status_code == 200
    db.refresh(user)
    assert user.failed_attempts == 0
    assert user.locked_until is None


def test_successful_login_resets_failed_attempts(client, db, make_user):
    user = make_user("gerard")
    for _ in range(3):
        _login(client, password="incorrecta")
    assert _login(client).status_code == 200
    db.refresh(user)
    assert user.failed_attempts == 0


def test_lock_is_per_user(client, make_user):
    make_user("gerard")
    make_user("padres")
    for _ in range(5):
        _login(client, username="padres", password="incorrecta")
    assert _login(client, username="padres").status_code == 429
    assert _login(client, username="gerard").status_code == 200


def test_me_reflects_db_user(client, db, make_user):
    make_user("gerard")
    _login(client)
    user = db.scalar(select(User).where(User.username == "gerard"))
    user.display_name = "Gerard G."
    db.commit()
    assert client.get("/api/auth/me").json()["display_name"] == "Gerard G."
