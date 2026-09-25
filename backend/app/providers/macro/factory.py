from __future__ import annotations

from app.providers.macro.base import MacroDataProvider
from app.providers.macro.nbs import NBSMacroProvider
from app.providers.macro.nuprc import NUPRCProductionProvider
from app.providers.macro.spglobal_pmi import SPGlobalPMIProvider


def get_macro_providers() -> list[MacroDataProvider]:
    """Return all configured official macro data providers."""
    return [
        NBSMacroProvider(),
        SPGlobalPMIProvider(),
        NUPRCProductionProvider(),
    ]
