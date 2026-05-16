"""Per-merchant demo seeding.

Hooked into POST /auth/start so every fresh visitor sees a populated demo
workspace immediately. Filled in by Task 3 — Task 2 only needs the symbol
to exist so the router can import it.
"""

from sqlmodel import Session


async def seed_new_merchant(session: Session, merchant_id: str) -> None:
    """Populate a fresh merchant with Shopify + Meta + Shiprocket demo data.

    Task 3 fills this in. Task 2 just needs the symbol to exist.
    """
    return None
