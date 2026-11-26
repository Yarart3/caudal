"""Fase 4, paso 4.1: Ajustes → Usuarios (/api/admin/users)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.auth.security import verify_password
from app.models import Category, Rule, User, UserSession
from tests.conftest import TEST_PASSWORD

NEW = {
    "username": "Abuela",
    "display_name": "Abuela",
    "color": "#A05A35",
    "password": "clave-abuela",
}


def _id(db, username: str) -> int:
    return db.scalar(select(User.id).where(User.username == username))


def _url(db, username: str, suffix: str = "") -> str:
    return f"/api/admin/users/{_id(db, username)}{suffix}"


# ---------- Solo el administrador ----------


def test_sin_sesion_401(client):
    assert client.get("/api/admin/users").status_code == 401
    assert client.post("/api/admin/users", json=NEW).status_code == 401


def test_un_usuario_normal_recibe_403_en_todo(db, login):
    login("gerard", is_admin=True)
    padres = login("padres")
    assert padres.get("/api/admin/users").status_code == 403
    assert padres.post("/api/admin/users", json=NEW).status_code == 403
    assert padres.patch(_url(db, "gerard"), json={"is_active": False}).status_code == 403
    res = padres.post(_url(db, "gerard", "/reset-password"), json={"password": "x" * 10})
    assert res.status_code == 403
    assert res.json() == {"detail": "Solo para el administrador"}
    # Y no ha cambiado nada
    gerard = db.get(User, _id(db, "gerard"))
    assert gerard.is_active
    assert verify_password(gerard.password_hash, TEST_PASSWORD)
    assert db.scalar(select(func.count()).select_from(User)) == 2


# ---------- Listar ----------


def test_lista_todos_los_usuarios_sin_el_hash(db, login):
    admin = login("gerard", is_admin=True)
    login("padres")
    db.get(User, _id(db, "padres")).locked_until = datetime.now(UTC) + timedelta(minutes=5)
    db.commit()
    res = admin.get("/api/admin/users")
    assert res.status_code == 200
    users = res.json()
    assert [u["username"] for u in users] == ["gerard", "padres"]
    assert users[0]["is_admin"] and not users[1]["is_admin"]
    assert users[1]["locked"] and not users[0]["locked"]
    assert users[1]["initial"] == "P"
    assert all("password_hash" not in u for u in users)


# ---------- Crear ----------


def test_crea_un_usuario_con_su_semilla_y_puede_entrar(client, db, login):
    admin = login("gerard", is_admin=True)
    res = admin.post("/api/admin/users", json=NEW)
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "abuela"  # en minúsculas
    assert body["display_name"] == "Abuela"
    assert body["is_active"] and not body["is_admin"]
    # Con sus categorías y reglas iniciales, como en el asistente
    assert db.scalar(select(func.count()).where(Category.user_id == body["id"])) > 0
    assert db.scalar(select(func.count()).where(Rule.user_id == body["id"])) > 0
    # Sale en «¿Quién entra?» y puede entrar
    assert "abuela" in [u["username"] for u in client.get("/api/auth/users").json()]
    res = client.post("/api/auth/login", json={"username": "abuela", "password": "clave-abuela"})
    assert res.status_code == 200


def test_crear_usuario_repetido_409(login):
    admin = login("gerard", is_admin=True)
    login("padres")
    res = admin.post("/api/admin/users", json={**NEW, "username": "Padres"})
    assert res.status_code == 409
    assert res.json() == {"detail": "Ya existe el usuario «padres»"}


def test_crear_con_contrasena_corta_422(login):
    admin = login("gerard", is_admin=True)
    res = admin.post("/api/admin/users", json={**NEW, "password": "corta"})
    assert res.status_code == 422
    assert "al menos 8" in res.json()["detail"]


def test_crear_con_usuario_no_valido_422(login):
    admin = login("gerard", is_admin=True)
    for bad in ("a", "con espacio", "àvia", "-guion", "x" * 41):
        res = admin.post("/api/admin/users", json={**NEW, "username": bad})
        assert res.status_code == 422, bad
        assert "de 2 a 40" in res.json()["detail"]


def test_crear_con_color_o_nombre_no_valido_422(login):
    admin = login("gerard", is_admin=True)
    assert admin.post("/api/admin/users", json={**NEW, "color": "rojo"}).status_code == 422
    assert admin.post("/api/admin/users", json={**NEW, "display_name": "  "}).status_code == 422


# ---------- Editar y desactivar ----------


def test_edita_nombre_color_y_admin(db, login):
    admin = login("gerard", is_admin=True)
    login("padres")
    res = admin.patch(
        _url(db, "padres"),
        json={"display_name": "Mamá y papá", "color": "#112233", "is_admin": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert (body["display_name"], body["color"], body["is_admin"]) == (
        "Mamá y papá",
        "#112233",
        True,
    )
    assert body["initial"] == "M"


def test_desactivar_cierra_sesiones_y_no_deja_entrar(client, db, login):
    admin = login("gerard", is_admin=True)
    padres = login("padres")
    padres_id = _id(db, "padres")
    res = admin.patch(_url(db, "padres"), json={"is_active": False})
    assert res.status_code == 200
    assert res.json()["is_active"] is False
    assert db.scalar(select(func.count()).where(UserSession.user_id == padres_id)) == 0
    assert padres.get("/api/auth/me").status_code == 401
    # No sale en «¿Quién entra?» y entrar da el mismo error que un usuario que no existe
    assert [u["username"] for u in client.get("/api/auth/users").json()] == ["gerard"]
    res = client.post("/api/auth/login", json={"username": "padres", "password": TEST_PASSWORD})
    assert res.status_code == 401
    assert res.json() == {"detail": "Usuario o contraseña incorrectos"}
    # Sus datos siguen ahí
    assert db.scalar(select(func.count()).where(Category.user_id == padres_id)) > 0

    # Reactivado, vuelve a entrar
    assert admin.patch(_url(db, "padres"), json={"is_active": True}).status_code == 200
    res = client.post("/api/auth/login", json={"username": "padres", "password": TEST_PASSWORD})
    assert res.status_code == 200


def test_una_sesion_de_un_usuario_desactivado_no_vale(db, login):
    """Aunque se desactive directamente en la BD (sin pasar por la API)."""
    padres = login("padres")
    db.get(User, _id(db, "padres")).is_active = False
    db.commit()
    assert padres.get("/api/auth/me").status_code == 401


def test_el_admin_no_puede_desactivarse_ni_quitarse_el_admin(db, login):
    admin = login("gerard", is_admin=True)
    for change in ({"is_active": False}, {"is_admin": False}):
        res = admin.patch(_url(db, "gerard"), json=change)
        assert res.status_code == 409
        assert "a ti mismo" in res.json()["detail"]
    gerard = db.get(User, _id(db, "gerard"))
    db.refresh(gerard)
    assert gerard.is_active and gerard.is_admin
    # Su nombre sí lo puede cambiar
    res = admin.patch(_url(db, "gerard"), json={"display_name": "Gerard G."})
    assert res.status_code == 200


def test_usuario_que_no_existe_404(login):
    admin = login("gerard", is_admin=True)
    assert admin.patch("/api/admin/users/999", json={"is_active": False}).status_code == 404
    res = admin.post("/api/admin/users/999/reset-password", json={"password": "x" * 10})
    assert res.status_code == 404


# ---------- Restablecer contraseña ----------


def test_restablecer_contrasena_desbloquea_y_cierra_sesiones(client, db, login):
    admin = login("gerard", is_admin=True)
    padres = login("padres")
    user = db.get(User, _id(db, "padres"))
    user.failed_attempts = 3
    user.locked_until = datetime.now(UTC) + timedelta(minutes=5)
    db.commit()

    res = admin.post(_url(db, "padres", "/reset-password"), json={"password": "nueva-clave-123"})
    assert res.status_code == 200
    assert res.json()["locked"] is False
    assert padres.get("/api/auth/me").status_code == 401
    res = client.post("/api/auth/login", json={"username": "padres", "password": "nueva-clave-123"})
    assert res.status_code == 200
    # La sesión del administrador sigue abierta
    assert admin.get("/api/auth/me").status_code == 200


def test_restablecer_con_contrasena_corta_422(db, login):
    admin = login("gerard", is_admin=True)
    login("padres")
    res = admin.post(_url(db, "padres", "/reset-password"), json={"password": "a"})
    assert res.status_code == 422
    assert "al menos 8" in res.json()["detail"]
