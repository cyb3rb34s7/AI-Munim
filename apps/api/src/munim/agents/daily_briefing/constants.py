"""Sector taxonomy for the daily-briefing agent.

The sector is per-run (chosen from a frontend dropdown), not stored on
the merchant — we want stateless multi-tenant demo experience. The hint
maps to a sentence the agent splices into its system prompt to bias the
narrative toward sector-specific concerns.
"""

from enum import StrEnum


class Sector(StrEnum):
    FASHION = "fashion"
    BEAUTY = "beauty"
    FMCG = "fmcg"
    ELECTRONICS = "electronics"
    HOME = "home"
    GENERIC = "generic"


SECTOR_HINT: dict[Sector, str] = {
    Sector.FASHION: (
        "Watch for high return/RTO rates (size and fit issues), seasonal "
        "demand windows, and repeat-RTO customers who keep ordering COD."
    ),
    Sector.BEAUTY: (
        "Watch for repurchase windows (30-60 day SKU lifecycle), review-driven "
        "Meta campaigns, and low-AOV bundling opportunities."
    ),
    Sector.FMCG: (
        "Watch for cart-size optimisation, repeat-customer retention, and "
        "low-margin order cancellation risk."
    ),
    Sector.ELECTRONICS: (
        "Watch for high-AOV COD risk (an RTO loses thousands per order), "
        "warranty-driven retention, and fraud signals on first-time buyers."
    ),
    Sector.HOME: (
        "Watch for heavy/oversize logistics cost, slow delivery zones, and "
        "low repurchase frequency."
    ),
    Sector.GENERIC: (
        "Watch for RTO patterns, ad-spend efficiency, and customer "
        "concentration risk."
    ),
}


SECTOR_LABEL: dict[Sector, str] = {
    Sector.FASHION: "Fashion & Apparel",
    Sector.BEAUTY: "Beauty & Cosmetics",
    Sector.FMCG: "FMCG / Consumables",
    Sector.ELECTRONICS: "Electronics & Gadgets",
    Sector.HOME: "Home & Lifestyle",
    Sector.GENERIC: "Generic D2C",
}
