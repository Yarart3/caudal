"""Guardar extractos sin duplicados (Fase 1b, parte 1.2)."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.importers.base import ImportFormatError, ParsedTransaction
from app.importers.fingerprint import fingerprint
from app.importers.service import import_statement
from app.models import Account, Transaction

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
IMAGIN_HEADERS = ["Concepto", "Fecha", "Importe", "Saldo"]


def _imagin_xlsx(rows: list[list[str]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(IMAGIN_HEADERS)
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _count(db: Session, account: Account) -> int:
    return db.scalar(select(func.count()).where(Transaction.account_id == account.id))


# ---------- Huella ----------


def test_fingerprint_rules() -> None:
    day, amount = date(2026, 9, 27), Decimal("-2.45")
    a = ParsedTransaction(2, day, "MERCADONA", amount, balance=Decimal("195.16"))
    b = ParsedTransaction(3, day, "MERCADONA", amount, balance=Decimal("197.61"))
    same_as_a = ParsedTransaction(9, day, "  mercadona ", amount, balance=Decimal("195.16"))

    assert len(fingerprint(1, a)) == 64
    assert fingerprint(1, a) != fingerprint(1, b)  # dos compras iguales: distinto saldo
    assert fingerprint(1, a) == fingerprint(1, same_as_a)  # concepto normalizado
    assert fingerprint(1, a) != fingerprint(2, a)  # otra cuenta
    # En Wise solo cuenta el ID
    wise = ParsedTransaction(2, day, "X", amount, external_id="CARD-1")
    wise_again = ParsedTransaction(5, day, "Y", Decimal("-1.00"), external_id="CARD-1")
    assert fingerprint(1, wise) == fingerprint(1, wise_again)


# ---------- Importar ----------


def test_import_imagin_twice_gives_zero_new(db: Session, make_account) -> None:
    account = make_account("imagin")

    first = import_statement(db, account, IMAGIN)
    assert (first.read, first.new, first.duplicates, first.review) == (8, 8, 0, 8)
    assert first.errors == [] and first.warnings == []

    second = import_statement(db, account, IMAGIN)
    assert (second.read, second.new, second.duplicates) == (8, 0, 8)
    assert _count(db, account) == 8


def test_imagin_identical_purchases_both_saved(db: Session, make_account) -> None:
    account = make_account("imagin")
    import_statement(db, account, IMAGIN)

    mercadona = db.scalars(
        select(Transaction).where(
            Transaction.account_id == account.id, Transaction.description == "MERCADONA"
        )
    ).all()
    assert [(t.date, t.amount) for t in mercadona] == [(date(2026, 9, 27), Decimal("-2.45"))] * 2
    assert len({t.fingerprint for t in mercadona}) == 2


def test_imported_values_and_reference_balance(db: Session, make_account) -> None:
    account = make_account("imagin")
    import_statement(db, account, IMAGIN)

    rows = db.scalars(select(Transaction).where(Transaction.account_id == account.id)).all()
    total = sum(t.amount for t in rows)
    assert total == Decimal("17.23")  # 67,23 (saldo final) - 50,00 (saldo antes del primero)
    assert all(t.category_status == "review" and not t.is_internal_transfer for t in rows)
    db.refresh(account)
    assert (account.reference_balance, account.reference_balance_date) == (
        Decimal("67.23"),
        date(2026, 9, 29),
    )


def test_import_wise(db: Session, make_account) -> None:
    account = make_account("wise", liquidity_type="money_market")
    summary = import_statement(db, account, WISE)
    assert (summary.read, summary.new, summary.duplicates) == (4, 4, 0)
    assert import_statement(db, account, WISE).new == 0
    db.refresh(account)
    assert account.reference_balance == Decimal("147.45")


def test_older_statement_does_not_rewind_reference_balance(db: Session, make_account) -> None:
    account = make_account(
        "imagin", reference_balance=Decimal("500.00"), reference_balance_date=date(2026, 10, 15)
    )
    import_statement(db, account, IMAGIN)  # acaba el 29/09: más antiguo
    db.refresh(account)
    assert (account.reference_balance, account.reference_balance_date) == (
        Decimal("500.00"),
        date(2026, 10, 15),
    )


def test_unreadable_row_is_reported_and_rest_saved(db: Session, make_account) -> None:
    account = make_account("imagin")
    data = _imagin_xlsx(
        [
            ["MERCADONA", "27/09/2026", "-2,45EUR", "37,71EUR"],
            ["BON AREA", "26/09/2026", "-1,9x4EUR", "40,16EUR"],
            ["BIZUM REBUT", "25/09/2026", "2,00EUR", "42,10EUR"],
        ]
    )
    summary = import_statement(db, account, data)

    assert (summary.read, summary.new) == (3, 2)
    assert [(e.row, e.field, e.value) for e in summary.errors] == [(3, "Importe", "-1,9x4EUR")]
    assert _count(db, account) == 2


def test_wrong_bank_saves_nothing(db: Session, make_account) -> None:
    account = make_account("imagin")
    with pytest.raises(ImportFormatError, match="parece de Wise"):
        import_statement(db, account, WISE)
    assert _count(db, account) == 0
    db.refresh(account)
    assert account.reference_balance is None


def test_manual_account_cannot_import(db: Session, make_account) -> None:
    account = make_account(None)
    with pytest.raises(ImportFormatError, match="no tiene banco asociado"):
        import_statement(db, account, IMAGIN)


def test_same_statement_in_two_accounts(db: Session, make_account) -> None:
    """La huella es por cuenta: el mismo extracto en dos cuentas (o usuarios) no choca."""
    mine = make_account("imagin")
    theirs = make_account("imagin", username="padres")
    assert import_statement(db, mine, IMAGIN).new == 8
    assert import_statement(db, theirs, IMAGIN).new == 8
