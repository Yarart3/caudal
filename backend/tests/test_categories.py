"""Fase 1c, parte 1.1: categorías y reglas iniciales, motor de reglas y su aplicación."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.categories import apply_rules, find_rule, seed_user_defaults
from app.categories.rules import compile_rules, load_rules, pattern_regex
from app.categories.seed import DEFAULT_CATEGORIES, DEFAULT_RULES
from app.db import engine
from app.importers.service import import_statement
from app.main import app
from app.models import Account, Category, Rule, Transaction, User

TEST_PASSWORD = "contrasena-de-prueba"
SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()


def _matches(pattern: str, description: str) -> bool:
    rules = compile_rules([Rule(id=1, pattern=pattern, category_id=1, priority=100)])
    return find_rule(description, rules) is not None


def _category(db: Session, user: User, name: str) -> Category:
    return db.scalar(select(Category).where(Category.user_id == user.id, Category.name == name))


def _tx(db: Session, account: Account, description: str, amount: str = "-1.00", **fields):
    tx = Transaction(
        account_id=account.id,
        date=fields.pop("date", date(2026, 9, 26)),
        description=description,
        amount=Decimal(amount),
        **fields,
    )
    db.add(tx)
    db.commit()
    return tx


# ---------- palabras enteras ----------


@pytest.mark.parametrize(
    ("pattern", "description"),
    [
        ("BAR", "BAR PEPE"),
        ("BAR", "CAFE-BAR LA PLAZA"),
        ("BAR", "bar"),
        ("BON AREA", "bon   àrea lleida"),  # minúsculas, acentos y espacios de más
        ("cafetería", "CAFETERIA CENTRAL"),  # acentos en la regla
        ("WWW.AMAZ", "WWW.AMAZ*12AB"),
        ("AMAZON", "WWW.AMAZON"),  # el punto es borde
        ("AMAZON", "WWW.AMAZON.ES"),
        ("*AMZ", "PAGO*AMZ 123"),  # el asterisco del principio no necesita borde
    ],
)
def test_pattern_matches_whole_words(pattern: str, description: str) -> None:
    assert _matches(pattern, description)


@pytest.mark.parametrize(
    ("pattern", "description"),
    [
        ("BAR", "BARCELONA"),
        ("BAR", "EMBARQUE"),
        ("BAR", "BAR2"),  # un número pegado tampoco es borde
        ("WWW.AMAZ", "WWW.AMAZON"),
        ("MERCADON", "MERCADONA"),
        ("CONSUM", "CONSUMO ELECTRICO"),
    ],
)
def test_pattern_does_not_match_inside_words(pattern: str, description: str) -> None:
    assert not _matches(pattern, description)


def test_empty_pattern_is_ignored() -> None:
    assert pattern_regex("   ") is None


def test_order_priority_then_longest() -> None:
    rules = compile_rules(
        [
            Rule(id=1, pattern="BAR", category_id=1, priority=100),
            Rule(id=2, pattern="BAR PEPE", category_id=2, priority=100),
            Rule(id=3, pattern="BIZUM ENVIAT", category_id=None, priority=10),
        ]
    )
    assert find_rule("BAR PEPE LLEIDA", rules).id == 2  # misma prioridad: la más larga
    assert find_rule("BAR LA PLAZA", rules).id == 1
    # La de revisar tiene prioridad 10 y corta: no acaba en Comida fuera
    assert find_rule("BIZUM ENVIAT BAR PEPE", rules).category_id is None
    assert find_rule("SUPERMERCADO", rules) is None


# ---------- semilla ----------


def test_seed_creates_defaults_once(db: Session, make_user) -> None:
    user = make_user("gerard")
    seed_user_defaults(db, user.id)
    seed_user_defaults(db, user.id)  # la segunda vez no duplica
    db.commit()

    names = set(db.scalars(select(Category.name).where(Category.user_id == user.id)))
    assert names == {name for name, _, _ in DEFAULT_CATEGORIES}
    rules = db.scalars(select(Rule).where(Rule.user_id == user.id)).all()
    assert len(rules) == len(DEFAULT_RULES)
    assert all(r.created_by == "system" for r in rules)
    bizum = {r.pattern: r.category_id for r in rules if r.pattern.startswith("BIZUM")}
    assert bizum == {"BIZUM ENVIAT": None, "BIZUM REBUT": None}
    bar = next(r for r in rules if r.pattern == "BAR")
    assert bar.category_id == _category(db, user, "Comida fuera").id


def test_setup_seeds_both_users_separately(client: TestClient, db: Session) -> None:
    passwords = {"gerard_password": "clave-gerard-123", "padres_password": "clave-padres-123"}
    assert client.post("/api/setup", json=passwords).status_code == 201
    for user in db.scalars(select(User)):
        categories = db.scalars(select(Category).where(Category.user_id == user.id)).all()
        assert len(categories) == len(DEFAULT_CATEGORIES)
        own_ids = {c.id for c in categories}
        rules = db.scalars(select(Rule).where(Rule.user_id == user.id)).all()
        # Las reglas de cada uno apuntan a SUS categorías, nunca a las del otro
        assert {r.category_id for r in rules if r.category_id} <= own_ids


def test_migration_0002_seeds_existing_users() -> None:
    """Los usuarios creados antes de la 1c (esquema 0001) reciben la semilla al migrar."""
    config = Config("alembic.ini")
    command.downgrade(config, "0001")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, display_name, color, password_hash) "
                    "VALUES ('antiguo', 'Antiguo', '#0E6B58', 'x')"
                )
            )
    finally:
        command.upgrade(config, "head")
    with engine.connect() as conn:
        categories = conn.scalar(text("SELECT count(*) FROM categories"))
        review_rules = conn.scalar(text("SELECT count(*) FROM rules WHERE category_id IS NULL"))
    assert categories == len(DEFAULT_CATEGORIES)
    assert review_rules == 2


# ---------- aplicar las reglas ----------


def test_apply_rules_only_touches_pending(db: Session, make_account) -> None:
    account = make_account("imagin")
    user = db.get(User, account.user_id)
    seed_user_defaults(db, user.id)
    db.commit()
    supermarket = _category(db, user, "Supermercado")
    clothes = _category(db, user, "Ropa")

    pending = _tx(db, account, "MERCADONA")
    bizum = _tx(db, account, "BIZUM ENVIAT")
    unknown = _tx(db, account, "TIENDA DESCONOCIDA")
    manual = _tx(db, account, "MERCADONA", category_status="manual", category_id=clothes.id)
    internal = _tx(db, account, "MERCADONA", is_internal_transfer=True, category_status="auto")

    assert apply_rules(db, user.id) == 1
    db.commit()
    for tx in (pending, bizum, unknown, manual, internal):
        db.refresh(tx)
    assert (pending.category_id, pending.category_status) == (supermarket.id, "auto")
    assert (bizum.category_id, bizum.category_status) == (None, "review")
    assert unknown.category_status == "review"
    assert (manual.category_id, manual.category_status) == (clothes.id, "manual")
    assert (internal.category_id, internal.category_status) == (None, "auto")


def test_apply_rules_respects_users(db: Session, make_account) -> None:
    """Las reglas de padres no tocan los movimientos de gerard."""
    gerard_account = make_account("imagin")
    padres_account = make_account("imagin", username="padres")
    padres = db.get(User, padres_account.user_id)
    seed_user_defaults(db, padres.id)  # gerard no tiene reglas
    db.commit()
    gerard_tx = _tx(db, gerard_account, "MERCADONA")
    padres_tx = _tx(db, padres_account, "MERCADONA")

    assert apply_rules(db, padres.id, [gerard_tx.id, padres_tx.id]) == 1
    db.commit()
    db.refresh(gerard_tx)
    db.refresh(padres_tx)
    assert gerard_tx.category_status == "review"
    assert padres_tx.category_id == _category(db, padres, "Supermercado").id


def test_apply_rules_limited_to_ids(db: Session, make_account) -> None:
    account = make_account("imagin")
    seed_user_defaults(db, account.user_id)
    db.commit()
    first = _tx(db, account, "MERCADONA")
    second = _tx(db, account, "MERCADONA")
    assert apply_rules(db, account.user_id, [second.id]) == 1
    assert apply_rules(db, account.user_id, []) == 0
    db.commit()
    db.refresh(first)
    assert first.category_status == "review"


def test_load_rules_skips_other_users(db: Session, make_user) -> None:
    gerard = make_user("gerard")
    padres = make_user("padres")
    seed_user_defaults(db, padres.id)
    db.commit()
    assert load_rules(db, gerard.id) == []


# ---------- al importar y al apuntar a mano ----------


def test_import_categorizes_with_rules(db: Session, make_account) -> None:
    imagin = make_account("imagin")
    seed_user_defaults(db, imagin.user_id)
    db.commit()

    summary = import_statement(db, imagin, IMAGIN)
    # WWW.AMAZON, 2 × MERCADONA y BON AREA. Por revisar: los dos Bizum, la transferencia
    # recibida y «enviament de dine» (sin Wise importado no tiene pareja)
    assert (summary.new, summary.categorized, summary.review, summary.internal) == (8, 4, 4, 0)

    by_text = {
        tx.description: tx
        for tx in db.scalars(select(Transaction).where(Transaction.account_id == imagin.id))
    }
    user = db.get(User, imagin.user_id)
    assert by_text["WWW.AMAZON"].category_id == _category(db, user, "Compras online").id
    assert by_text["BIZUM REBUT"].category_status == "review"


def test_internal_transfer_is_not_categorized(db: Session, make_account) -> None:
    """La pareja imagin → Wise queda interna y sin categoría, aunque haya una regla que
    encaje con el concepto."""
    imagin = make_account("imagin")
    wise = make_account("wise", name="Wise")
    user = db.get(User, imagin.user_id)
    seed_user_defaults(db, user.id)
    db.add(
        Rule(
            user_id=user.id,
            pattern="ENVIAMENT DE DINE",
            category_id=_category(db, user, "Otros").id,
            priority=50,
        )
    )
    db.commit()

    import_statement(db, wise, WISE)
    summary = import_statement(db, imagin, IMAGIN)
    assert summary.internal == 1
    assert summary.categorized == 4
    sent = db.scalar(
        select(Transaction).where(
            Transaction.account_id == imagin.id, Transaction.description == "enviament de dine"
        )
    )
    assert (sent.is_internal_transfer, sent.category_id) == (True, None)


def test_manual_transaction_uses_rules(make_user, db: Session) -> None:
    user = make_user("gerard")
    seed_user_defaults(db, user.id)
    db.commit()
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "gerard", "password": TEST_PASSWORD})
    account = client.post(
        "/api/accounts", json={"name": "Efectivo", "kind": "spending", "import_format": None}
    ).json()["id"]

    body = {
        "account_id": account,
        "date": "2026-09-26",
        "description": "Bar Pepe",
        "amount": "-3.50",
    }
    created = client.post("/api/transactions", json=body).json()
    assert created["category_status"] == "auto"
    assert created["category_id"] == _category(db, user, "Comida fuera").id

    body["description"] = "Barcelona parking"
    created = client.post("/api/transactions", json=body).json()
    assert created["category_status"] == "review"
    total = db.scalar(select(func.count()).select_from(Transaction))
    assert total == 2
