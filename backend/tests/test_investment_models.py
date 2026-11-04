"""Fase 3, parte 3.1: restricciones de productos, operaciones, precios y valores a mano."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, InvestmentOperation, ManualValuation, Price, Product, User


def _product(db: Session, user: User, **fields) -> Product:
    fields.setdefault("name", "iShares Core MSCI World")
    fields.setdefault("isin", "IE00B4L5Y983")
    fields.setdefault("kind", "etf")
    fields.setdefault("price_source", "yahoo")
    product = Product(user_id=user.id, **fields)
    db.add(product)
    db.commit()
    return product


def _account(db: Session, user: User, name: str = "Scalable", kind: str = "investment") -> Account:
    account = Account(user_id=user.id, name=name, kind=kind)
    db.add(account)
    db.commit()
    return account


def _operation(db: Session, account: Account, product: Product, **fields) -> InvestmentOperation:
    fields.setdefault("date", date(2026, 10, 1))
    fields.setdefault("kind", "buy")
    fields.setdefault("shares", Decimal("1.5"))
    fields.setdefault("amount_eur", Decimal("100.00"))
    operation = InvestmentOperation(account_id=account.id, product_id=product.id, **fields)
    db.add(operation)
    db.commit()
    return operation


def test_product_defaults(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"))
    db.refresh(product)
    assert product.currency == "EUR"
    assert product.long_term is True
    assert product.ter is None


def test_ter_keeps_four_decimals_exactly(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"), ter=Decimal("0.00070"))
    db.refresh(product)
    assert product.ter == Decimal("0.00070")


@pytest.mark.parametrize("fields", [{"kind": "bono"}, {"price_source": "google"}, {"ter": "1"}])
def test_invalid_product_is_rejected(db: Session, make_user, fields: dict) -> None:
    user = make_user("gerard")
    with pytest.raises(IntegrityError):
        _product(db, user, **fields)
    db.rollback()


def test_commodity_product_is_allowed(db: Session, make_user) -> None:
    product = _product(
        db, make_user("gerard"), name="Oro de ejemplo", isin="IE0000000001", kind="commodity"
    )
    assert product.kind == "commodity"


def test_same_isin_twice_for_one_user_is_rejected(db: Session, make_user) -> None:
    user = make_user("gerard")
    _product(db, user)
    with pytest.raises(IntegrityError):
        _product(db, user, name="Otro nombre")
    db.rollback()


def test_same_isin_for_two_users_is_allowed(db: Session, make_user) -> None:
    _product(db, make_user("gerard"))
    _product(db, make_user("padres"))
    assert len(db.scalars(select(Product)).all()) == 2


def test_products_without_isin_do_not_clash(db: Session, make_user) -> None:
    user = make_user("gerard")
    _product(db, user, name="Bitcoin", isin=None, kind="crypto", price_source="coingecko")
    _product(db, user, name="Ether", isin=None, kind="crypto", price_source="coingecko")
    assert len(db.scalars(select(Product)).all()) == 2


def test_operation_keeps_eight_decimals_of_shares(db: Session, make_user) -> None:
    user = make_user("gerard")
    operation = _operation(db, _account(db, user), _product(db, user), shares=Decimal("0.12345678"))
    db.refresh(operation)
    assert operation.shares == Decimal("0.12345678")
    assert operation.fee_eur is None


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "split"},
        {"kind": "buy", "shares": Decimal(0)},
        {"kind": "sell", "shares": Decimal(0)},
        {"shares": Decimal("-1")},
        {"amount_eur": Decimal(0)},
        {"amount_eur": Decimal("-10.00")},
        {"fee_eur": Decimal("-0.01")},
    ],
)
def test_invalid_operation_is_rejected(db: Session, make_user, fields: dict) -> None:
    user = make_user("gerard")
    account, product = _account(db, user), _product(db, user)
    with pytest.raises(IntegrityError):
        _operation(db, account, product, **fields)
    db.rollback()


def test_dividend_and_fee_may_have_no_shares(db: Session, make_user) -> None:
    user = make_user("gerard")
    account, product = _account(db, user), _product(db, user)
    _operation(db, account, product, kind="dividend", shares=Decimal(0), amount_eur=Decimal("3.20"))
    _operation(db, account, product, kind="fee", shares=Decimal(0), amount_eur=Decimal("1.00"))
    assert len(db.scalars(select(InvestmentOperation)).all()) == 2


def test_same_fingerprint_in_one_account_is_rejected(db: Session, make_user) -> None:
    user = make_user("gerard")
    account, product = _account(db, user), _product(db, user)
    _operation(db, account, product, fingerprint="a" * 64)
    with pytest.raises(IntegrityError):
        _operation(db, account, product, fingerprint="a" * 64)
    db.rollback()


def test_manual_operations_without_fingerprint_do_not_clash(db: Session, make_user) -> None:
    user = make_user("gerard")
    account, product = _account(db, user), _product(db, user)
    _operation(db, account, product)
    _operation(db, account, product)
    assert len(db.scalars(select(InvestmentOperation)).all()) == 2


def test_product_with_operations_cannot_be_deleted(db: Session, make_user) -> None:
    user = make_user("gerard")
    product = _product(db, user)
    _operation(db, _account(db, user), product)
    with pytest.raises(IntegrityError):
        db.execute(delete(Product).where(Product.id == product.id))
        db.commit()
    db.rollback()


def test_deleting_an_account_deletes_its_operations(db: Session, make_user) -> None:
    user = make_user("gerard")
    account, product = _account(db, user), _product(db, user)
    _operation(db, account, product)
    db.execute(delete(Account).where(Account.id == account.id))
    db.commit()
    assert db.scalars(select(InvestmentOperation)).all() == []
    assert db.get(Product, product.id) is not None


def test_mixed_account_is_allowed(db: Session, make_user) -> None:
    assert _account(db, make_user("gerard"), "Trade Republic", "mixed").kind == "mixed"


def test_price_is_unique_per_product_and_day(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"))
    db.add(
        Price(
            product_id=product.id,
            date=date(2026, 11, 3),
            price=Decimal("112.34"),
            currency="EUR",
            source="yahoo",
        )
    )
    db.commit()
    db.add(
        Price(
            product_id=product.id,
            date=date(2026, 11, 3),
            price=Decimal("113.00"),
            currency="EUR",
            source="yahoo",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_price_keeps_six_decimals_and_must_be_positive(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"))
    price = Price(
        product_id=product.id,
        date=date(2026, 11, 3),
        price=Decimal("0.123456"),
        currency="EUR",
        source="yahoo",
    )
    db.add(price)
    db.commit()
    db.refresh(price)
    assert price.price == Decimal("0.123456")
    assert price.fetched_at is not None
    db.add(
        Price(
            product_id=product.id,
            date=date(2026, 11, 4),
            price=Decimal(0),
            currency="EUR",
            source="yahoo",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_deleting_a_product_deletes_prices_and_valuations(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"), kind="pension", price_source="manual")
    db.add(
        Price(
            product_id=product.id,
            date=date(2026, 11, 3),
            price=Decimal("1"),
            currency="EUR",
            source="manual",
        )
    )
    db.add(
        ManualValuation(product_id=product.id, date=date(2026, 11, 1), value_eur=Decimal("1500.00"))
    )
    db.commit()
    db.execute(delete(Product).where(Product.id == product.id))
    db.commit()
    assert db.scalars(select(Price)).all() == []
    assert db.scalars(select(ManualValuation)).all() == []


@pytest.mark.parametrize(
    "fields", [{"value_eur": Decimal("-1")}, {"contributed_eur": Decimal("-1")}]
)
def test_invalid_manual_valuation_is_rejected(db: Session, make_user, fields: dict) -> None:
    product = _product(db, make_user("gerard"), kind="pension", price_source="manual")
    values = {"product_id": product.id, "date": date(2026, 11, 1), "value_eur": Decimal("10.00")}
    db.add(ManualValuation(**{**values, **fields}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_one_manual_valuation_per_product_and_day(db: Session, make_user) -> None:
    product = _product(db, make_user("gerard"), kind="pension", price_source="manual")
    for _ in range(2):
        db.add(
            ManualValuation(
                product_id=product.id, date=date(2026, 11, 1), value_eur=Decimal("10.00")
            )
        )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
