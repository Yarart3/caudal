"""Fase 1c, parte 1.3: /api/dashboard. Los totales se comparan con sumas hechas a mano sobre
los ejemplos de samples/ (septiembre de 2026):

imagin (8): WWW.AMAZON −69,73 · BIZUM ENVIAT −8,20 · enviament de dine −50,00 (interna) ·
            MERCADONA −2,45 ×2 · BIZUM REBUT +2,00 · BON AREA −1,94 · TRANSFER IMMEDIATA +150,00
            Saldo final del extracto: 67,23 (29/09). Saldo antes del primer movimiento: 50,00.
Wise (4):   Tienda −7,00 · ingreso desde imagin +50,00 (interna) · Restaurante −12,40 ·
            Supermercado −3,15. Saldo final: 147,45 (30/09). Antes: 120,00.

Sin internas: ingresos 2,00 + 150,00 = 152,00
              gastos 69,73 + 8,20 + 2,45 + 2,45 + 1,94 + 7,00 + 12,40 + 3,15 = 107,32
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dashboard.months import add_months, last_months, month_end, parse_month

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _account(client: TestClient, name: str, import_format: str | None, liquidity="cash") -> int:
    body = {
        "name": name,
        "kind": "spending",
        "import_format": import_format,
        "liquidity_type": liquidity,
    }
    res = client.post("/api/accounts", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def _upload(client: TestClient, account: int, data: bytes) -> None:
    files = {"file": ("x.xlsx", data, XLSX)}
    res = client.post("/api/imports", data={"account_id": str(account)}, files=files)
    assert res.status_code == 200


def _tx(client: TestClient, account: int, day: str, description: str, amount: str) -> dict:
    body = {"account_id": account, "date": day, "description": description, "amount": amount}
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def samples(gerard: TestClient) -> dict[str, int]:
    accounts = {
        "imagin": _account(gerard, "imagin", "imagin"),
        "wise": _account(gerard, "Wise", "wise", liquidity="money_market"),
    }
    _upload(gerard, accounts["wise"], WISE)
    _upload(gerard, accounts["imagin"], IMAGIN)
    return accounts


def _net_worth(client: TestClient, **params) -> dict:
    res = client.get("/api/dashboard/net-worth", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _cashflow(client: TestClient, **params) -> dict:
    res = client.get("/api/dashboard/cashflow", params=params)
    assert res.status_code == 200, res.text
    return res.json()


# ---------- meses ----------


def test_month_helpers() -> None:
    september = parse_month("2026-09")
    assert month_end(september).day == 30
    assert month_end(parse_month("2028-02")).day == 29
    assert add_months(parse_month("2026-01"), -1) == parse_month("2025-12")
    assert add_months(parse_month("2026-12"), 1) == parse_month("2027-01")
    months = last_months(september, 12)
    assert (months[0], months[-1], len(months)) == (parse_month("2025-10"), september, 12)
    for bad in ("2026-13", "2026-9", "26-09", ""):
        with pytest.raises(ValueError):
            parse_month(bad)


# ---------- Patrimonio ----------


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/dashboard/net-worth").status_code == 401
    assert client.get("/api/dashboard/cashflow").status_code == 401


def test_net_worth_with_samples(gerard: TestClient, samples: dict[str, int]) -> None:
    data = _net_worth(gerard)  # sin month: el del último movimiento (septiembre)
    assert data["month"] == "2026-09"
    balances = {a["name"]: a["balance"] for a in data["accounts"]}
    assert balances == {"imagin": "67.23", "Wise": "147.45"}
    assert (data["liquidity"], data["net_worth"], data["investments"]) == (
        "214.68",
        "214.68",
        "0.00",
    )
    assert data["by_type"] == {"cash": "67.23", "money_market": "147.45"}
    assert data["savings"] == "44.68"  # 152,00 − 107,32

    history = {h["month"]: h["liquidity"] for h in data["history"]}
    assert len(data["history"]) == 12
    assert data["history"][-1]["month"] == "2026-09"
    assert history["2026-09"] == "214.68"
    assert history["2026-08"] == "170.00"  # 50,00 + 120,00: lo que había antes de septiembre


def test_balance_of_earlier_month_goes_back_from_reference(
    gerard: TestClient, samples: dict[str, int]
) -> None:
    """Con el saldo de referencia a 29/09, el saldo a 31/08 se calcula hacia atrás."""
    data = _net_worth(gerard, month="2026-08")
    balances = {a["name"]: a["balance"] for a in data["accounts"]}
    assert balances == {"imagin": "50.00", "Wise": "120.00"}


def test_balance_after_reference_adds_new_transactions(
    gerard: TestClient, samples: dict[str, int]
) -> None:
    _tx(gerard, samples["imagin"], "2026-10-02", "NETFLIX", "-12.99")
    data = _net_worth(gerard)
    assert data["month"] == "2026-10"
    balances = {a["name"]: a["balance"] for a in data["accounts"]}
    assert balances["imagin"] == "54.24"  # 67,23 − 12,99
    # Un movimiento apuntado a mano ANTES de la fecha de referencia ya está en el saldo del
    # extracto: el saldo de septiembre no cambia
    _tx(gerard, samples["imagin"], "2026-09-15", "Olvidado", "-5.00")
    september = {a["name"]: a["balance"] for a in _net_worth(gerard, month="2026-09")["accounts"]}
    assert september["imagin"] == "67.23"


def test_manual_account_balance_is_sum(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo", None)
    _tx(gerard, cash, "2026-08-20", "Cajero", "100.00")
    _tx(gerard, cash, "2026-09-03", "Mercado", "-30.50")
    assert _net_worth(gerard, month="2026-08")["liquidity"] == "100.00"
    assert _net_worth(gerard, month="2026-09")["liquidity"] == "69.50"


def test_empty_user(gerard: TestClient) -> None:
    data = _net_worth(gerard, month="2026-09")
    assert (data["net_worth"], data["accounts"], len(data["history"])) == ("0.00", [], 12)
    flow = _cashflow(gerard, month="2026-09")
    assert (flow["income"], flow["expense"], flow["savings_rate"]) == ("0.00", "0.00", None)
    assert flow["by_category"] == []


# ---------- Movimientos ----------


def test_cashflow_with_samples(gerard: TestClient, samples: dict[str, int]) -> None:
    data = _cashflow(gerard)
    assert data["month"] == "2026-09"
    assert (data["income"], data["expense"], data["savings"]) == ("152.00", "107.32", "44.68")
    assert data["savings_rate"] == 29  # 44,68 / 152,00 = 29,4 %
    assert data["cash_total"] == "214.68"
    assert (data["previous_expense"], data["expense_change"]) == ("0.00", None)

    by_category = {c["name"]: c["amount"] for c in data["by_category"]}
    assert by_category == {
        "Compras online": "69.73",
        "Sin categoría": "30.75",  # BIZUM ENVIAT 8,20 + los tres de Wise sin regla
        "Supermercado": "6.84",  # MERCADONA ×2 + BON AREA
    }
    assert [c["name"] for c in data["by_category"]][0] == "Compras online"  # de mayor a menor
    # El gasto por categoría suma exactamente el gasto del mes
    total = sum(int(c["amount"].replace(".", "")) for c in data["by_category"])
    assert total == 10732

    history = {h["month"]: h for h in data["history"]}
    assert len(history) == 12
    assert history["2026-09"] == {"month": "2026-09", "income": "152.00", "expense": "107.32"}
    assert history["2026-08"] == {"month": "2026-08", "income": "0.00", "expense": "0.00"}


def test_internal_transfers_do_not_count(gerard: TestClient) -> None:
    a = _account(gerard, "A", None)
    b = _account(gerard, "B", None)
    sent = _tx(gerard, a, "2026-09-10", "Traspaso a B", "-100.00")
    received = _tx(gerard, b, "2026-09-10", "Traspaso desde A", "100.00")
    assert sent["is_internal_transfer"] or received["is_internal_transfer"]
    data = _cashflow(gerard, month="2026-09")
    assert (data["income"], data["expense"]) == ("0.00", "0.00")
    # Pero sí mueven el saldo de cada cuenta
    balances = {x["name"]: x["balance"] for x in _net_worth(gerard, month="2026-09")["accounts"]}
    assert balances == {"A": "-100.00", "B": "100.00"}


def test_refund_counts_as_income(gerard: TestClient) -> None:
    """Una devolución con categoría de gasto cuenta como ingreso (DISENO 9.1: por el signo)."""
    cash = _account(gerard, "Efectivo", None)
    _tx(gerard, cash, "2026-09-05", "AMAZON compra", "-40.00")
    _tx(gerard, cash, "2026-09-09", "AMAZON devolucion", "15.00")
    data = _cashflow(gerard, month="2026-09")
    assert (data["income"], data["expense"]) == ("15.00", "40.00")
    assert {c["name"]: c["amount"] for c in data["by_category"]} == {"Compras online": "40.00"}


def test_expense_change_and_month_bounds(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo", None)
    _tx(gerard, cash, "2026-08-31", "MERCADONA", "-80.00")
    _tx(gerard, cash, "2026-09-01", "MERCADONA", "-100.00")
    _tx(gerard, cash, "2026-09-30", "Nómina", "1000.00")
    _tx(gerard, cash, "2026-10-01", "MERCADONA", "-1.00")
    data = _cashflow(gerard, month="2026-09")
    assert (data["income"], data["expense"], data["previous_expense"]) == (
        "1000.00",
        "100.00",
        "80.00",
    )
    assert data["expense_change"] == 25  # (100 − 80) / 80
    assert data["savings_rate"] == 90


def test_invalid_month(gerard: TestClient) -> None:
    for path in ("/api/dashboard/net-worth", "/api/dashboard/cashflow"):
        res = gerard.get(path, params={"month": "septiembre"})
        assert res.status_code == 422
        assert res.json()["detail"] == "El mes tiene que ser AAAA-MM"


def test_isolation(gerard: TestClient, padres: TestClient, samples: dict[str, int]) -> None:
    data = _net_worth(padres, month="2026-09")
    assert (data["net_worth"], data["accounts"]) == ("0.00", [])
    flow = _cashflow(padres, month="2026-09")
    assert (flow["income"], flow["expense"], flow["by_category"]) == ("0.00", "0.00", [])
    # Y lo de padres no se suma a gerard
    cash = _account(padres, "Efectivo", None)
    _tx(padres, cash, "2026-09-10", "Nómina", "2000.00")
    assert _cashflow(gerard)["income"] == "152.00"
    assert _net_worth(gerard)["liquidity"] == "214.68"
