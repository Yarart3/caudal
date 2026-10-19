"""Importador de imagin (DISENO, sección 6.1).

Una hoja con `Concepto`, `Fecha`, `Importe` y `Saldo` en la fila 1. Los valores suelen ser
texto (`29/09/2026`, `-69,73EUR`), pero también se aceptan fechas y números de Excel.
"""

from openpyxl.workbook.workbook import Workbook

from app.importers.base import (
    Importer,
    ParsedTransaction,
    ParseResult,
    RowError,
    UnreadableValueError,
    check_balance_chain,
    closing,
    data_rows,
    has_headers,
    header_map,
    missing_headers,
    parse_date,
    parse_es_amount,
    require_headers,
    row_error,
)

CONCEPT = "Concepto"
DATE = "Fecha"
AMOUNT = "Importe"
BALANCE = "Saldo"
REQUIRED = [CONCEPT, DATE, AMOUNT, BALANCE]


class ImaginImporter(Importer):
    name = "imagin"
    label = "imagin"
    required = REQUIRED

    def detect(self, workbook: Workbook) -> bool:
        return has_headers(workbook.worksheets[0], REQUIRED)

    def missing_columns(self, workbook: Workbook) -> list[str]:
        return missing_headers(workbook.worksheets[0], REQUIRED)

    def parse(self, workbook: Workbook) -> ParseResult:
        sheet = workbook.worksheets[0]
        headers = header_map(sheet)
        require_headers(headers, REQUIRED)
        result = ParseResult()

        for row in data_rows(sheet, headers):
            description = row.text(CONCEPT)
            if description is None:
                message = f"Fila {row.number}: el concepto está vacío"
                result.errors.append(RowError(row.number, CONCEPT, "", message))
                continue
            try:
                when = parse_date(row.get(DATE))
            except UnreadableValueError as problem:
                result.errors.append(
                    row_error(row.number, DATE, row.get(DATE), "la fecha", problem)
                )
                continue
            try:
                amount = parse_es_amount(row.get(AMOUNT))
            except UnreadableValueError as problem:
                result.errors.append(
                    row_error(row.number, AMOUNT, row.get(AMOUNT), "el importe", problem)
                )
                continue
            try:
                # El saldo forma parte de la huella (DISENO 9.2): sin él no se puede importar
                balance = parse_es_amount(row.get(BALANCE))
            except UnreadableValueError as problem:
                result.errors.append(
                    row_error(row.number, BALANCE, row.get(BALANCE), "el saldo", problem)
                )
                continue
            result.transactions.append(
                ParsedTransaction(
                    row=row.number,
                    date=when,
                    description=description,
                    amount=amount,
                    balance=balance,
                )
            )

        result.warnings.extend(check_balance_chain(result.transactions, self.label))
        result.closing_balance, result.closing_date = closing(result.transactions)
        return result
