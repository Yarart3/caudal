"""Registro de importadores de extractos. Para añadir un banco: su módulo y una línea aquí."""

from openpyxl.workbook.workbook import Workbook

from app.importers.base import Importer, ImportFormatError
from app.importers.imagin import ImaginImporter
from app.importers.wise import WiseImporter

# Orden de detección: del formato más concreto al más general (Wise exige una hoja con nombre)
IMPORTERS: dict[str, Importer] = {
    importer.name: importer for importer in (WiseImporter(), ImaginImporter())
}


def get_importer(name: str) -> Importer:
    importer = IMPORTERS.get(name)
    if importer is None:
        raise ImportFormatError(f"No hay importador para «{name}»")
    return importer


def detect_format(workbook: Workbook) -> Importer | None:
    """El importador que reconoce el archivo, o None si no es de ningún banco conocido."""
    return next((imp for imp in IMPORTERS.values() if imp.detect(workbook)), None)


def check_format(workbook: Workbook, expected: str) -> Importer:
    """Comprueba que el archivo es del banco de la cuenta elegida (DISENO 6.0) antes de leerlo."""
    importer = get_importer(expected)
    if importer.detect(workbook):
        return importer
    detected = detect_format(workbook)
    if detected is not None:
        raise ImportFormatError(
            f"Este archivo parece de {detected.label}, pero has elegido una cuenta de "
            f"{importer.label}"
        )
    missing = importer.missing_columns(workbook)
    # Si casi todo encaja, el banco ha cambiado algo: se dice exactamente qué falta
    if missing and len(missing) < len(importer.required):
        raise ImportFormatError(f"No se encuentra la columna «{missing[0]}»")
    raise ImportFormatError(f"Este archivo no tiene el formato del extracto de {importer.label}")
