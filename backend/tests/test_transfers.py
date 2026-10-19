"""Transferencias internas (Fase 1b, parte 1.3)."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.service import import_statement
from app.models import Account, Transaction
from app.transfers.matcher import looks_like_transfer

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
WISE_HEADERS = [
    "Documento de identidad",
    "Fecha",
    "Cantidad",
    "Divisa",
    "Descripción",
    "Referencia del pago",
    "Cambiar desde",
    "Cambiar a",
    "Comercio",
    "Nombre del pagador",
    "Tipo de transacción",
    "Tipo de detalles de transacción",
]


def _wise_xlsx(rows: list[dict[str, object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "All transactions"
    ws.append(WISE_HEADERS)
    for row in rows:
        ws.append([row.get(h, "") for h in WISE_HEADERS])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _deposit_from_imagin(tx_id: str, day: datetime, amount: float) -> dict[str, object]:
    return {
        "Documento de identidad": tx_id,
        "Fecha": day,
        "Cantidad": amount,
        "Divisa": "EUR",
        "Descripción": "Has recibido dinero",
        "Referencia del pago": "enviament de diners - imaginBank",
        "Nombre del pagador": "Nombre Ejemplo",
        "Tipo de transacción": "CREDIT",
        "Tipo de detalles de transacción": "DEPOSIT",
    }


def _internal(db: Session, account: Account) -> list[tuple[str, Decimal]]:
    rows = db.scalars(
        select(Transaction)
        .where(Transaction.account_id == account.id, Transaction.is_internal_transfer.is_(True))
        .order_by(Transaction.id)
    )
    return [(t.description, t.amount) for t in rows]


def _add(db: Session, account: Account, day: date, description: str, amount: str, **fields):
    tx = Transaction(
        account_id=account.id, date=day, description=description, amount=Decimal(amount), **fields
    )
    db.add(tx)
    db.commit()
    return tx


def test_looks_like_transfer() -> None:
    assert looks_like_transfer("enviament de dine")
    assert looks_like_transfer("TRANSFER IMMEDIATA")
    assert looks_like_transfer("Traspaso a cuenta")
    assert not looks_like_transfer("BIZUM ENVIAT")
    assert not looks_like_transfer("MERCADONA")


def test_imagin_then_wise(db: Session, make_account) -> None:
    imagin = make_account("imagin")
    wise = make_account("wise")

    assert import_statement(db, imagin, IMAGIN).internal == 0  # todavía no hay Wise
    summary = import_statement(db, wise, WISE)

    assert (summary.new, summary.internal, summary.review) == (4, 1, 3)
    assert _internal(db, imagin) == [("enviament de dine", Decimal("-50.00"))]
    assert _internal(db, wise) == [("Nombre Ejemplo", Decimal("50.00"))]
    pair = db.scalars(select(Transaction).where(Transaction.is_internal_transfer.is_(True)))
    assert {t.category_status for t in pair} == {"auto"}  # no hay que categorizarlas


def test_wise_then_imagin(db: Session, make_account) -> None:
    imagin = make_account("imagin")
    wise = make_account("wise")

    assert import_statement(db, wise, WISE).internal == 0
    summary = import_statement(db, imagin, IMAGIN)

    assert (summary.new, summary.internal, summary.review) == (8, 1, 7)
    assert _internal(db, imagin) == [("enviament de dine", Decimal("-50.00"))]
    assert _internal(db, wise) == [("Nombre Ejemplo", Decimal("50.00"))]


def test_reimport_does_not_change_pairs(db: Session, make_account) -> None:
    imagin = make_account("imagin")
    wise = make_account("wise")
    import_statement(db, imagin, IMAGIN)
    import_statement(db, wise, WISE)

    again = import_statement(db, wise, WISE)
    assert (again.new, again.internal) == (0, 0)
    assert len(_internal(db, imagin)) == len(_internal(db, wise)) == 1


def test_never_between_users(db: Session, make_account) -> None:
    """La salida de imagin de los padres no es pareja del ingreso en el Wise de Gerard."""
    parents_imagin = make_account("imagin", username="padres")
    wise = make_account("wise")
    import_statement(db, parents_imagin, IMAGIN)

    assert import_statement(db, wise, WISE).internal == 0
    assert _internal(db, parents_imagin) == []


def test_more_than_three_days_apart(db: Session, make_account) -> None:
    manual = make_account(None)
    wise = make_account("wise")
    _add(db, manual, date(2026, 9, 23), "Traspaso a Wise", "-50.00")  # 4 días antes del 27/09

    assert import_statement(db, wise, WISE).internal == 0


def test_three_days_apart_is_paired(db: Session, make_account) -> None:
    manual = make_account(None)
    wise = make_account("wise")
    _add(db, manual, date(2026, 9, 24), "Traspaso a Wise", "-50.00")  # 3 días antes

    assert import_statement(db, wise, WISE).internal == 1


def test_same_amount_without_transfer_signal_is_not_paired(db: Session, make_account) -> None:
    """Un pago con tarjeta de -12,40 y una devolución de +12,40 en otra cuenta NO son
    una transferencia: ninguna de las dos lo parece y no hay pista del extracto."""
    manual = make_account(None)
    wise = make_account("wise")
    _add(db, manual, date(2026, 9, 26), "Devolución tienda", "12.40")

    assert import_statement(db, wise, WISE).internal == 0


def test_hint_prefers_imagin_account(db: Session, make_account) -> None:
    """El ingreso de Wise viene de imaginBank: si hay dos salidas de -50,00, gana la de imagin."""
    imagin = make_account("imagin")
    manual = make_account(None, name="Trade Republic")
    wise = make_account("wise")
    _add(db, manual, date(2026, 9, 27), "Traspaso a Wise", "-50.00")
    import_statement(db, imagin, IMAGIN)

    import_statement(db, wise, WISE)
    assert _internal(db, imagin) == [("enviament de dine", Decimal("-50.00"))]
    assert _internal(db, manual) == []


def test_each_movement_is_paired_once(db: Session, make_account) -> None:
    imagin = make_account("imagin")
    wise = make_account("wise")
    import_statement(db, imagin, IMAGIN)  # una sola salida de -50,00 el 27/09
    day = datetime(2026, 9, 27)  # noqa: DTZ001
    data = _wise_xlsx(
        [_deposit_from_imagin("TRANSFER-1", day, 50), _deposit_from_imagin("TRANSFER-2", day, 50)]
    )

    summary = import_statement(db, wise, data)
    assert summary.internal == 1
    assert len(_internal(db, wise)) == 1


def test_wise_conversion_is_internal(db: Session, make_account) -> None:
    wise = make_account("wise")
    data = _wise_xlsx(
        [
            {
                "Documento de identidad": "BALANCE-1",
                "Fecha": datetime(2026, 10, 1),  # noqa: DTZ001
                "Cantidad": -20,
                "Divisa": "EUR",
                "Descripción": "Conversión de EUR a USD",
                "Cambiar desde": "EUR",
                "Cambiar a": "USD",
                "Tipo de transacción": "DEBIT",
            }
        ]
    )
    summary = import_statement(db, wise, data)
    assert (summary.new, summary.internal, summary.review) == (1, 1, 0)


def test_manual_category_is_kept(db: Session, make_account) -> None:
    """Si la otra pata ya tenía categoría puesta a mano, se respeta."""
    manual = make_account(None)
    wise = make_account("wise")
    old = _add(db, manual, date(2026, 9, 27), "Traspaso a Wise", "-50.00", category_status="manual")

    import_statement(db, wise, WISE)
    db.refresh(old)
    assert (old.is_internal_transfer, old.category_status) == (True, "manual")
