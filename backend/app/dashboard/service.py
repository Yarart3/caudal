"""Totales de los paneles. Todo con Decimal y siempre filtrando por el usuario.

Reglas (DISENO 9.1):
- Negativo = gasto, positivo = ingreso. Las transferencias internas no cuentan ni como
  ingreso ni como gasto (sí mueven el saldo de cada cuenta).
- Una devolución (+) cuenta como ingreso, aunque tenga una categoría de gasto: así el gasto
  por categoría suma exactamente el gasto del mes.

Saldo de una cuenta a una fecha D (DISENO 8.2: el saldo se calcula, no se guarda):
- con saldo de referencia (último saldo del extracto) a fecha R:
      saldo(D) = referencia + S(D) − S(R)
  donde S(x) es la suma de sus movimientos con fecha ≤ x. Si D > R suma lo que vino después;
  si D < R, resta lo que pasó entre D y R.
- sin saldo de referencia (cuentas a mano): saldo(D) = S(D).
"""

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import accumulate

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.dashboard.months import last_months, month_end, month_key, parse_month
from app.models import Account, Category, Transaction

ZERO = Decimal("0.00")
HISTORY_MONTHS = 12


def default_month(db: Session, user_id: int) -> date:
    """El mes del último movimiento del usuario (si importa septiembre en octubre, el panel
    enseña septiembre). Sin movimientos, el mes actual."""
    last = db.scalar(
        select(func.max(Transaction.date))
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.user_id == user_id)
    )
    day = last or datetime.now(UTC).date()
    return day.replace(day=1)


def resolve_month(db: Session, user_id: int, month: str | None) -> date:
    """Primer día del mes pedido («AAAA-MM») o del mes por defecto. ValueError si no vale."""
    return parse_month(month) if month else default_month(db, user_id)


# ---------- saldos ----------


@dataclass
class _Series:
    """Suma acumulada de los movimientos de una cuenta, por fecha."""

    dates: list[date] = field(default_factory=list)
    cumulative: list[Decimal] = field(default_factory=list)

    def upto(self, day: date) -> Decimal:
        """S(day): suma de los movimientos con fecha ≤ day."""
        position = bisect_right(self.dates, day)
        return self.cumulative[position - 1] if position else ZERO


def _series(db: Session, user_id: int) -> dict[int, _Series]:
    rows = db.execute(
        select(Transaction.account_id, Transaction.date, func.sum(Transaction.amount))
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.user_id == user_id)
        .group_by(Transaction.account_id, Transaction.date)
        .order_by(Transaction.account_id, Transaction.date)
    ).all()
    by_account: dict[int, tuple[list[date], list[Decimal]]] = {}
    for account_id, day, total in rows:
        dates, totals = by_account.setdefault(account_id, ([], []))
        dates.append(day)
        totals.append(total)
    return {
        account_id: _Series(dates, list(accumulate(totals)))
        for account_id, (dates, totals) in by_account.items()
    }


def _balance(account: Account, series: _Series, day: date) -> Decimal:
    if account.reference_balance is not None and account.reference_balance_date is not None:
        return (
            account.reference_balance
            + series.upto(day)
            - series.upto(account.reference_balance_date)
        )
    return series.upto(day)


def _accounts(db: Session, user_id: int) -> list[Account]:
    return list(db.scalars(select(Account).where(Account.user_id == user_id).order_by(Account.id)))


# ---------- ingresos y gastos ----------


def _income_expense_by_month(
    db: Session, user_id: int, first: date, last: date
) -> dict[str, tuple[Decimal, Decimal]]:
    """{«AAAA-MM»: (ingresos, gastos)} entre dos meses, sin internas. Gastos en positivo."""
    month = func.to_char(Transaction.date, "YYYY-MM")
    rows = db.execute(
        select(
            month,
            func.coalesce(func.sum(case((Transaction.amount > 0, Transaction.amount))), 0),
            func.coalesce(func.sum(case((Transaction.amount < 0, -Transaction.amount))), 0),
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.is_internal_transfer.is_(False),
            Transaction.date >= first,
            Transaction.date <= month_end(last),
        )
        .group_by(month)
    ).all()
    return {key: (Decimal(income), Decimal(expense)) for key, income, expense in rows}


def _percent(part: Decimal, whole: Decimal) -> int | None:
    """part / whole en %, redondeado al entero (como en la maqueta). None si whole es 0."""
    if whole == 0:
        return None
    return int((part / whole * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


@dataclass
class AccountBalance:
    id: int
    name: str
    kind: str
    liquidity_type: str
    balance: Decimal


@dataclass
class NetWorthMonth:
    month: str
    liquidity: Decimal
    investments: Decimal


@dataclass
class NetWorth:
    month: str
    net_worth: Decimal
    liquidity: Decimal
    investments: Decimal  # Fase 3: de momento siempre 0
    savings: Decimal  # ingresos − gastos del mes
    accounts: list[AccountBalance]
    by_type: dict[str, Decimal]  # «cash» (efectivo) y «money_market» (fondo monetario)
    history: list[NetWorthMonth]


def net_worth(db: Session, user_id: int, first_day: date) -> NetWorth:
    accounts = _accounts(db, user_id)
    series = _series(db, user_id)
    empty = _Series()
    end = month_end(first_day)

    balances = [
        AccountBalance(
            id=a.id,
            name=a.name,
            kind=a.kind,
            liquidity_type=a.liquidity_type,
            balance=_money(_balance(a, series.get(a.id, empty), end)),
        )
        for a in accounts
    ]
    liquidity = sum((b.balance for b in balances), ZERO)
    by_type = {"cash": ZERO, "money_market": ZERO}
    for b in balances:
        by_type[b.liquidity_type] += b.balance

    history = []
    for month in last_months(first_day, HISTORY_MONTHS):
        month_last = month_end(month)
        total = sum((_balance(a, series.get(a.id, empty), month_last) for a in accounts), ZERO)
        history.append(NetWorthMonth(month_key(month), _money(total), ZERO))

    flows = _income_expense_by_month(db, user_id, first_day, first_day)
    income, expense = flows.get(month_key(first_day), (ZERO, ZERO))
    return NetWorth(
        month=month_key(first_day),
        net_worth=_money(liquidity),
        liquidity=_money(liquidity),
        investments=ZERO,
        savings=_money(income - expense),
        accounts=balances,
        by_type={k: _money(v) for k, v in by_type.items()},
        history=history,
    )


@dataclass
class CashflowMonth:
    month: str
    income: Decimal
    expense: Decimal


@dataclass
class CategorySpend:
    category_id: int | None  # None = sin categoría (por revisar)
    name: str
    color: str
    amount: Decimal


@dataclass
class Cashflow:
    month: str
    cash_total: Decimal  # dinero en cuentas a final de mes
    income: Decimal
    expense: Decimal  # en positivo
    savings: Decimal
    savings_rate: int | None  # % de los ingresos que se ahorra; None sin ingresos
    previous_expense: Decimal
    expense_change: int | None  # % respecto al mes anterior; None si el anterior es 0
    history: list[CashflowMonth]
    by_category: list[CategorySpend]


UNCATEGORIZED = ("Sin categoría", "#8A9099")


def cashflow(db: Session, user_id: int, first_day: date) -> Cashflow:
    months = last_months(first_day, HISTORY_MONTHS)
    flows = _income_expense_by_month(db, user_id, months[0], first_day)
    history = [
        CashflowMonth(month_key(m), *map(_money, flows.get(month_key(m), (ZERO, ZERO))))
        for m in months
    ]
    current, previous = history[-1], history[-2]

    rows = db.execute(
        select(Category.id, Category.name, Category.color, func.sum(-Transaction.amount))
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Account.user_id == user_id,
            Transaction.is_internal_transfer.is_(False),
            Transaction.amount < 0,
            Transaction.date >= first_day,
            Transaction.date <= month_end(first_day),
        )
        .group_by(Category.id, Category.name, Category.color)
    ).all()
    by_category = sorted(
        (
            CategorySpend(
                category_id=cat_id,
                name=name if cat_id is not None else UNCATEGORIZED[0],
                color=(color or UNCATEGORIZED[1]) if cat_id is not None else UNCATEGORIZED[1],
                amount=_money(total),
            )
            for cat_id, name, color, total in rows
        ),
        key=lambda c: (-c.amount, c.name),
    )

    accounts = _accounts(db, user_id)
    series = _series(db, user_id)
    end = month_end(first_day)
    cash_total = sum((_balance(a, series.get(a.id, _Series()), end) for a in accounts), ZERO)
    savings = current.income - current.expense
    return Cashflow(
        month=current.month,
        cash_total=_money(cash_total),
        income=current.income,
        expense=current.expense,
        savings=_money(savings),
        savings_rate=_percent(savings, current.income),
        previous_expense=previous.expense,
        expense_change=_percent(current.expense - previous.expense, previous.expense),
        history=history,
        by_category=by_category,
    )
