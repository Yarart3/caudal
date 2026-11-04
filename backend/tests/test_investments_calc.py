"""Fase 3, parte 3.4a: FIFO, TIR, rentabilidad por año, peor caída y aportaciones.

Casos calculados a mano (los cálculos van en cada test) y el ejemplo de la ayuda de `XIRR` de
Excel. No usan base de datos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.investments.calc import (
    DayValue,
    Op,
    OversoldError,
    annual_ter_cost,
    cash_flows,
    contribution_streak,
    fifo,
    max_drawdown,
    monthly_contributions,
    xirr,
    year_returns,
)

D = Decimal


def buy(day: date, shares: str, amount: str, id: int = 0) -> Op:
    return Op(day, "buy", D(shares), D(amount), id)


def sell(day: date, shares: str, amount: str, id: int = 0) -> Op:
    return Op(day, "sell", D(shares), D(amount), id)


# ---------------------------------------------------------------- FIFO


def test_fifo_partial_sale_takes_the_oldest_lot_first():
    # 10 a 100 € (1.000 €) y 10 a 150 € (1.500 €); se venden 15 por 2.100 €.
    # Coste FIFO: el primer lote entero (1.000) + 5/10 del segundo (750) = 1.750 → gana 350.
    result = fifo(
        [
            buy(date(2024, 1, 10), "10", "1000.00"),
            buy(date(2024, 3, 1), "10", "1500.00"),
            sell(date(2024, 6, 1), "15", "2100.00"),
        ]
    )
    assert [(s.shares, s.cost, s.proceeds, s.gain) for s in result.sales] == [
        (D("15"), D("1750.00"), D("2100.00"), D("350.00"))
    ]
    assert result.shares == D("5")
    assert result.cost == D("750.00")
    assert result.average_price == D("150")
    assert result.realized == D("350.00")
    assert result.lots[0].date == date(2024, 3, 1)


def test_fifo_two_sales_and_a_new_buy():
    # Lote A: 4 por 400. Venta 1 de 3 → coste 300. Lote B: 2 por 260. Venta 2 de 2:
    # 1 de A (100) + 1 de B (130) = 230. Queda 1 de B con coste 130.
    result = fifo(
        [
            buy(date(2024, 1, 1), "4", "400.00"),
            sell(date(2024, 2, 1), "3", "330.00"),
            buy(date(2024, 3, 1), "2", "260.00"),
            sell(date(2024, 4, 1), "2", "250.00"),
        ]
    )
    assert [(s.cost, s.gain) for s in result.sales] == [
        (D("300.00"), D("30.00")),
        (D("230.00"), D("20.00")),
    ]
    assert (result.shares, result.cost) == (D("1"), D("130.00"))


def test_fifo_rounding_always_adds_up_to_what_was_paid():
    # 3 participaciones por 100 €, vendidas de una en una: 33,33 + 33,34 + 33,33 = 100,00.
    # (2.ª venta: quedan 66,67 € por 2 → la mitad es 33,335 → 33,34.)
    ops = [buy(date(2024, 1, 1), "3", "100.00")] + [
        sell(date(2024, 2, day), "1", "40.00", id=day) for day in (1, 2, 3)
    ]
    result = fifo(ops)
    assert [s.cost for s in result.sales] == [D("33.33"), D("33.34"), D("33.33")]
    assert sum(s.cost for s in result.sales) == D("100.00")
    assert result.lots == []
    assert result.average_price is None


def test_fifo_fractional_shares():
    # 0,5 por 50 € y 0,25 por 30 €; se venden 0,6 → 50 + 30 × 0,1/0,25 (12) = 62.
    result = fifo(
        [
            buy(date(2024, 1, 1), "0.5", "50.00"),
            buy(date(2024, 1, 2), "0.25", "30.00"),
            sell(date(2024, 1, 3), "0.6", "70.00"),
        ]
    )
    assert result.sales[0].cost == D("62.00")
    assert (result.shares, result.cost) == (D("0.15"), D("18.00"))


def test_fifo_same_day_buys_count_before_sells():
    # La venta se dio de alta antes (id menor), pero el mismo día la compra va primero.
    result = fifo(
        [
            sell(date(2024, 5, 5), "1", "110.00", id=1),
            buy(date(2024, 5, 5), "1", "100.00", id=2),
        ]
    )
    assert result.realized == D("10.00")


def test_fifo_selling_more_than_held_raises():
    with pytest.raises(OversoldError):
        fifo([buy(date(2024, 1, 1), "1", "100.00"), sell(date(2024, 1, 2), "2", "300.00")])


def test_fifo_dividends_and_fees_do_not_touch_the_lots():
    result = fifo(
        [
            buy(date(2024, 1, 1), "2", "200.00"),
            Op(date(2024, 6, 1), "dividend", D(0), D("3.40")),
            Op(date(2024, 7, 1), "dividend", D(0), D("2.10")),
            Op(date(2024, 8, 1), "fee", D(0), D("1.00")),
        ]
    )
    assert (result.shares, result.cost) == (D("2"), D("200.00"))
    assert result.dividends == D("5.50")
    assert result.fees == D("1.00")
    assert result.realized == 0


# ---------------------------------------------------------------- TIR


def test_xirr_one_year_ten_percent():
    # 1.000 € el 1-1-2023 y 1.100 € 365 días después → 10 % exacto.
    assert xirr([(date(2023, 1, 1), D("-1000")), (date(2024, 1, 1), D("1100"))]) == D("0.1")


def test_xirr_leap_year_uses_365_days_like_excel():
    # 2020 es bisiesto: 366 días → 1,1 ^ (365/366) − 1 = 0,09971...
    rate = xirr([(date(2020, 1, 1), D("-1000")), (date(2021, 1, 1), D("1100"))])
    assert rate == D(repr(round(1.1 ** (365 / 366) - 1, 8)))


def test_xirr_matches_the_excel_help_example():
    # Ejemplo de la ayuda de XIRR (Microsoft): resultado 0,373362535 (37,34 %).
    flows = [
        (date(2008, 1, 1), D("-10000")),
        (date(2008, 3, 1), D("2750")),
        (date(2008, 10, 30), D("4250")),
        (date(2009, 2, 15), D("3250")),
        (date(2009, 4, 1), D("2750")),
    ]
    assert abs(xirr(flows) - D("0.373362535")) < D("0.0000001")


def test_xirr_loss_and_big_loss():
    # −50 % en un año. −99 % cae fuera de lo que encuentra Newton desde el 10 %: bisección.
    assert xirr([(date(2023, 1, 1), D("-1000")), (date(2024, 1, 1), D("500"))]) == D("-0.5")
    rate = xirr([(date(2023, 1, 1), D("-1000")), (date(2024, 1, 1), D("10"))])
    assert abs(rate - D("-0.99")) < D("0.000001")


def test_xirr_monthly_contributions_hand_case():
    # 100 € el 1 de enero y 100 € 181 días después; valor 210 € a los 365 días.
    # Se comprueba que la tasa devuelta anula el valor actual neto y que está entre el 6 y el 7 %.
    flows = [
        (date(2023, 1, 1), D("-100")),
        (date(2023, 7, 1), D("-100")),
        (date(2024, 1, 1), D("210")),
    ]
    rate = float(xirr(flows))
    npv = -100 - 100 / (1 + rate) ** (181 / 365) + 210 / (1 + rate) ** (365 / 365)
    assert abs(npv) < 1e-6
    assert 0.06 < rate < 0.07


def test_xirr_without_a_positive_and_a_negative_flow_is_none():
    assert xirr([(date(2024, 1, 1), D("-100")), (date(2024, 2, 1), D("-50"))]) is None
    assert xirr([(date(2024, 1, 1), D("0")), (date(2024, 2, 1), D("50"))]) is None
    assert xirr([]) is None


def test_cash_flows_signs():
    ops = [
        buy(date(2024, 1, 1), "1", "100.00"),
        sell(date(2024, 2, 1), "1", "120.00"),
        Op(date(2024, 3, 1), "dividend", D(0), D("2.00")),
        Op(date(2024, 4, 1), "fee", D(0), D("1.00")),
    ]
    assert [v for _, v in cash_flows(ops)] == [D("-100.00"), D("120.00"), D("2.00"), D("-1.00")]


# ---------------------------------------------------------------- rentabilidad por año


def test_year_returns_modified_dietz():
    # 2024: compra de 1.000 € el 2 de enero, vale 1.100 € el 31-12 → 10 %.
    # 2025: parte de 1.100; el 2 de julio entran 1.000 (dentro 183 de 365 días); vale 2.310.
    #   R = (2.310 − 1.100 − 1.000) / (1.100 + 1.000 · 183/365)
    series = [
        DayValue(date(2024, 1, 2), D("1000"), D("1000")),
        DayValue(date(2024, 12, 31), D("1100")),
        DayValue(date(2025, 7, 2), D("2200"), D("1000")),
        DayValue(date(2025, 12, 31), D("2310")),
    ]
    result = year_returns(series)
    assert result[2024] == D("0.1")
    assert result[2025] == D("210") / (D("1100") + D("1000") * D(183) / D(365))


def test_year_returns_a_big_late_contribution_is_not_a_gain():
    # Parte de 1.000 el 1-1; el 31-12 entran 10.000 y vale 11.000 → solo ha ganado 0 €.
    series = [
        DayValue(date(2024, 1, 1), D("1000"), D("1000")),
        DayValue(date(2024, 12, 31), D("11000"), D("10000")),
    ]
    assert year_returns(series)[2024] == 0


def test_year_returns_empty():
    assert year_returns([]) == {}


# ---------------------------------------------------------------- peor caída


def test_max_drawdown_ignores_contributions():
    # Valores 100 → 120 → 90 (−25 % desde 120) → 200 (entran 100: la rentabilidad del día es
    # 100/90) → 180. El índice va 1 → 1,2 → 0,9 → 1,0 → 0,9: peor caída −25 %.
    series = [
        DayValue(date(2024, 1, 1), D("100"), D("100")),
        DayValue(date(2024, 1, 2), D("120")),
        DayValue(date(2024, 1, 3), D("90")),
        DayValue(date(2024, 1, 4), D("200"), D("100")),
        DayValue(date(2024, 1, 5), D("180")),
    ]
    assert abs(max_drawdown(series) - D("-0.25")) < D("0.0000001")


def test_max_drawdown_only_up_and_too_short():
    up = [DayValue(date(2024, 1, 1), D("100"), D("100")), DayValue(date(2024, 1, 2), D("110"))]
    assert max_drawdown(up) == 0
    assert max_drawdown(up[:1]) is None
    assert max_drawdown([]) is None


# ---------------------------------------------------------------- aportaciones y TER


def test_monthly_contributions_and_streak():
    ops = [
        buy(date(2026, 8, 3), "1", "100.00"),
        buy(date(2026, 9, 1), "1", "100.00"),
        buy(date(2026, 10, 1), "1", "150.00"),
        sell(date(2026, 10, 20), "1", "50.00"),
        Op(date(2026, 10, 25), "dividend", D(0), D("5.00")),
        buy(date(2026, 6, 1), "1", "80.00"),  # julio sin aportar: corta la racha
    ]
    months = monthly_contributions(ops)
    assert months == {
        (2026, 6): D("80.00"),
        (2026, 8): D("100.00"),
        (2026, 9): D("100.00"),
        (2026, 10): D("100.00"),
    }
    # Noviembre aún sin aportar: cuenta desde octubre → oct, sep y ago.
    assert contribution_streak(months, date(2026, 11, 5)) == 3
    months[(2026, 11)] = D("50.00")
    assert contribution_streak(months, date(2026, 11, 5)) == 4


def test_streak_breaks_with_a_net_sale_month_and_crosses_years():
    months = {(2025, 12): D("10"), (2026, 1): D("10"), (2026, 2): D("-30")}
    # En febrero se vendió más de lo aportado: en marzo la racha es 0. A mitad de febrero
    # aún no se rompe (cuenta desde enero), y cruza de año: dic + ene = 2.
    assert contribution_streak(months, date(2026, 3, 15)) == 0
    assert contribution_streak(months, date(2026, 2, 15)) == 2
    assert contribution_streak(months, date(2026, 1, 31)) == 2
    assert contribution_streak({}, date(2026, 1, 1)) == 0


def test_annual_ter_cost():
    # 10.000 × 0,07 % = 7,00 · sin TER no cuenta · 2.345,67 × 0,2 % = 4,69134 → 11,69
    positions = [(D("10000"), D("0.0007")), (D("500"), None), (D("2345.67"), D("0.002"))]
    assert annual_ter_cost(positions) == D("11.69")
    assert annual_ter_cost([]) == D("0.00")
