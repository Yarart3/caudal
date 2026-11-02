"""Fase 2, parte 2.3: pagos recurrentes (GET /api/recurring) con movimientos inventados."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from app.recurring import group_key
from app.recurring.service import _same_day


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


@pytest.fixture
def account(gerard: TestClient, make_account) -> Account:
    return make_account("imagin", username="gerard")


def _add(
    db: Session, account: Account, day: str, description: str, amount: str, **fields
) -> Transaction:
    tx = Transaction(
        account_id=account.id,
        date=date.fromisoformat(day),
        description=description,
        amount=Decimal(amount),
        category_status=fields.pop("category_status", "review"),
        **fields,
    )
    db.add(tx)
    db.commit()
    return tx


def _get(client: TestClient, month: str = "2026-09") -> dict:
    res = client.get(f"/api/recurring?month={month}")
    assert res.status_code == 200
    return res.json()


def _keys(body: dict) -> list[str]:
    return [item["key"] for item in body["items"]]


# ---------- funciones sueltas ----------


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Spotify P2B4C6", "SPOTIFY"),
        ("COMPRA TARJ. 1234 netflix.com 05/09", "COMPRA TARJ. NETFLIX.COM"),
        ("Gimnàs   Municipal", "GIMNAS MUNICIPAL"),
        ("12345 67890", "12345 67890"),
    ],
)
def test_group_key(description: str, expected: str) -> None:
    assert group_key(description) == expected


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        ("2026-01-31", 1, "2026-02-28"),
        ("2026-08-25", 1, "2026-09-25"),
        ("2026-12-15", 1, "2027-01-15"),
        ("2028-02-29", 12, "2029-02-28"),
    ],
)
def test_same_day_next_period(day: str, months: int, expected: str) -> None:
    assert _same_day(date.fromisoformat(day), months) == date.fromisoformat(expected)


# ---------- detección ----------


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/recurring").status_code == 401


def test_monthly_payment_is_detected(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2026-06-25", "SPOTIFY P1A2B3", "-9.99")
    _add(db, account, "2026-07-25", "SPOTIFY P4C5D6", "-10.99")
    _add(db, account, "2026-08-26", "SPOTIFY P7E8F9", "-10.99")
    _add(db, account, "2026-09-25", "SPOTIFY P0G1H2", "-10.99", category_status="auto")
    body = _get(gerard)
    assert body["month"] == "2026-09"
    assert body["monthly_total"] == "10.99"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item | {"category_id": None} == {
        "key": "SPOTIFY",
        "description": "SPOTIFY P0G1H2",
        "frequency": "monthly",
        "amount": "10.99",
        "monthly_amount": "10.99",
        "occurrences": 4,
        "first_date": "2026-06-25",
        "last_date": "2026-09-25",
        "next_date": "2026-10-25",
        "detected_on": "2026-08-26",
        "is_new": False,
        "category_id": None,
        "category_name": "Sin categoría",
        "category_color": "#8A9099",
        "account_name": "imagin",
    }


def test_category_of_last_payment_is_shown(
    gerard: TestClient, db: Session, account: Account
) -> None:
    category = next(c for c in gerard.get("/api/categories").json() if c["name"] == "Suscripciones")
    for day in ("2026-07-12", "2026-08-12"):
        _add(db, account, day, "NETFLIX.COM", "-13.99")
    _add(db, account, "2026-09-12", "NETFLIX.COM", "-13.99", category_id=category["id"])
    item = _get(gerard)["items"][0]
    assert (item["category_name"], item["category_color"]) == ("Suscripciones", category["color"])


def test_two_monthly_payments_are_not_enough(
    gerard: TestClient, db: Session, account: Account
) -> None:
    _add(db, account, "2026-08-01", "GIMNASIO", "-34.90")
    _add(db, account, "2026-09-01", "GIMNASIO", "-34.90")
    assert _get(gerard)["items"] == []


def test_new_recurring_in_selected_month(gerard: TestClient, db: Session, account: Account) -> None:
    for day in ("2026-07-01", "2026-08-01", "2026-09-01"):
        _add(db, account, day, "GIMNASIO", "-34.90")
    assert _get(gerard, "2026-09")["items"][0]["is_new"] is True
    # Octubre todavía sin importar: sigue activo, pero ya no es nuevo
    assert _get(gerard, "2026-10")["items"][0]["is_new"] is False
    assert _get(gerard, "2026-08")["items"] == []  # en agosto solo había dos pagos


def test_amount_within_ten_percent(gerard: TestClient, db: Session, account: Account) -> None:
    # 45,00 · 49,00 · 41,00: a ±10 % de la mediana (45,00) → recurrente (la luz)
    _add(db, account, "2026-07-05", "ENDESA ENERGIA", "-45.00")
    _add(db, account, "2026-08-05", "ENDESA ENERGIA", "-49.00")
    _add(db, account, "2026-09-05", "ENDESA ENERGIA", "-41.00")
    # 20 · 30 · 20: 30 queda fuera y la cadena se corta
    _add(db, account, "2026-07-10", "VODAFONE", "-20.00")
    _add(db, account, "2026-08-10", "VODAFONE", "-30.00")
    _add(db, account, "2026-09-10", "VODAFONE", "-20.00")
    assert _keys(_get(gerard)) == ["ENDESA ENERGIA"]


def test_other_amount_in_same_shop_does_not_break_it(
    gerard: TestClient, db: Session, account: Account
) -> None:
    for day in ("2026-07-03", "2026-08-03", "2026-09-03"):
        _add(db, account, day, "AMAZON PRIME", "-4.99")
    _add(db, account, "2026-08-15", "AMAZON PRIME", "-36.00")  # otra cosa, otro importe
    item = _get(gerard)["items"][0]
    assert (item["key"], item["amount"], item["occurrences"]) == ("AMAZON PRIME", "4.99", 3)


def test_weekly_purchases_are_not_recurring(
    gerard: TestClient, db: Session, account: Account
) -> None:
    # La misma barra de pan cada semana: hay pagos a 28 días, pero con otros en medio
    for day in range(1, 31, 7):
        _add(db, account, f"2026-07-{day:02d}", "FORN DE PA", "-3.00")
        _add(db, account, f"2026-08-{day:02d}", "FORN DE PA", "-3.00")
        _add(db, account, f"2026-09-{day:02d}", "FORN DE PA", "-3.00")
    assert _get(gerard)["items"] == []


def test_irregular_gaps_are_not_monthly(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2026-05-10", "PELUQUERIA", "-15.00")
    _add(db, account, "2026-07-10", "PELUQUERIA", "-15.00")
    _add(db, account, "2026-09-10", "PELUQUERIA", "-15.00")
    assert _get(gerard)["items"] == []


def test_same_day_duplicate_counts_once(gerard: TestClient, db: Session, account: Account) -> None:
    for day in ("2026-07-20", "2026-08-20", "2026-09-20"):
        _add(db, account, day, "SEGURO MOVIL", "-6.00")
    _add(db, account, "2026-09-20", "SEGURO MOVIL", "-6.00")
    item = _get(gerard)["items"][0]
    assert (item["occurrences"], item["monthly_amount"]) == (3, "6.00")


def test_annual_payment(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2025-09-15", "SEGURO HOGAR", "-340.00")
    _add(db, account, "2026-09-14", "SEGURO HOGAR", "-342.00")
    body = _get(gerard)
    item = body["items"][0]
    assert (item["frequency"], item["amount"], item["monthly_amount"]) == (
        "annual",
        "342.00",
        "28.50",
    )
    assert (item["next_date"], item["detected_on"], item["is_new"]) == (
        "2027-09-14",
        "2026-09-14",
        True,
    )
    assert body["monthly_total"] == "28.50"


def test_monthly_total_adds_monthly_and_annual(
    gerard: TestClient, db: Session, account: Account
) -> None:
    for day in ("2026-07-25", "2026-08-25", "2026-09-25"):
        _add(db, account, day, "SPOTIFY", "-10.99")
    _add(db, account, "2025-09-01", "DOMINIO WEB", "-12.00")
    _add(db, account, "2026-09-01", "DOMINIO WEB", "-12.00")
    body = _get(gerard)
    assert _keys(body) == ["SPOTIFY", "DOMINIO WEB"]  # del más caro al mes al más barato
    assert body["monthly_total"] == "11.99"  # 10,99 + 12,00 / 12


def test_stopped_payment_is_not_shown(gerard: TestClient, db: Session, account: Account) -> None:
    for day in ("2026-04-08", "2026-05-08", "2026-06-08"):
        _add(db, account, day, "HBO MAX", "-9.99")
    assert _get(gerard, "2026-07")["items"][0]["key"] == "HBO MAX"  # 53 días: sigue activo
    assert _get(gerard, "2026-09")["items"] == []  # 114 días sin pagar: dado de baja


def test_later_payments_do_not_count(gerard: TestClient, db: Session, account: Account) -> None:
    for day in ("2026-08-02", "2026-09-02", "2026-10-02"):
        _add(db, account, day, "GIMNASIO", "-34.90")
    assert _get(gerard, "2026-09")["items"] == []


def test_income_internal_and_bizum_are_ignored(
    gerard: TestClient, db: Session, account: Account
) -> None:
    for day in ("2026-07-28", "2026-08-28", "2026-09-28"):
        _add(db, account, day, "NOMINA EMPRESA", "1200.00")
        _add(db, account, day, "TRASPASO A WISE", "-50.00", is_internal_transfer=True)
        _add(db, account, day, "BIZUM ENVIAT", "-10.00")
        _add(db, account, day, "bizum enviat Pis", "-300.00")
    assert _get(gerard)["items"] == []


def test_grouped_without_words_with_numbers(
    gerard: TestClient, db: Session, account: Account
) -> None:
    _add(db, account, "2026-07-06", "COMPRA TARJ 4512 YOUTUBE 06/07", "-13.99")
    _add(db, account, "2026-08-06", "COMPRA TARJ 4512 YOUTUBE 06/08", "-13.99")
    _add(db, account, "2026-09-06", "COMPRA TARJ 4512 YOUTUBE 06/09", "-13.99")
    assert _keys(_get(gerard)) == ["COMPRA TARJ YOUTUBE"]


def test_without_month_uses_last_transaction_month(
    gerard: TestClient, db: Session, account: Account
) -> None:
    _add(db, account, "2026-07-14", "MERCADONA", "-5.00")
    assert gerard.get("/api/recurring").json()["month"] == "2026-07"


def test_invalid_month_is_rejected(gerard: TestClient) -> None:
    res = gerard.get("/api/recurring?month=2026-9")
    assert res.status_code == 422
    assert res.json()["detail"] == "El mes tiene que ser AAAA-MM"


def test_users_are_isolated(
    gerard: TestClient, padres: TestClient, db: Session, account: Account, make_account
) -> None:
    padres_account = make_account("caixabank", username="padres")
    for day in ("2026-07-05", "2026-08-05", "2026-09-05"):
        _add(db, account, day, "SPOTIFY", "-10.99")
        _add(db, padres_account, day, "FIBRA MOVIL", "-62.00")
    assert _keys(_get(gerard)) == ["SPOTIFY"]
    assert _keys(_get(padres)) == ["FIBRA MOVIL"]
