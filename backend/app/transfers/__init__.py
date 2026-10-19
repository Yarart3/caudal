"""Transferencias internas: dinero que pasa entre cuentas del mismo usuario (DISENO 9.3)."""

from app.transfers.matcher import match_internal_transfers

__all__ = ["match_internal_transfers"]
