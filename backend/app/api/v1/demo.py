"""Demo data seeding endpoints for vertical slice demonstrations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.demo.seeder import DemoDataSeeder, get_demo_scenarios

router = APIRouter()


@router.post("/seed")
async def seed_demo_data(
    db: AsyncSession = Depends(get_db),
):
    """Seed demo invoices and matching shipments for vertical slice demo.

    Creates 5 freight invoices with corresponding shipment records,
    each representing a different reconciliation scenario:
    - perfect_match: All fields align, auto-approve expected
    - amount_mismatch: Invoice vs shipment amount differs
    - no_match: No matching shipment found
    - high_value_review: Mandatory review due to dollar threshold
    - close_candidates: Two shipments match, ambiguous — needs human decision
    """
    seeder = DemoDataSeeder()
    result = await seeder.seed(db)
    await db.commit()
    return result


@router.get("/scenarios")
async def list_demo_scenarios():
    """List available demo scenarios and their document IDs."""
    return {"scenarios": get_demo_scenarios()}
