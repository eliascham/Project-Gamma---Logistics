"""
Business rules manager for cost allocation.

Rules are stored in the allocation_rules DB table and define how freight invoice
line items should be mapped to project codes, cost centers, and GL accounts.
"""

import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_allocation import AllocationRule

logger = logging.getLogger("gamma.cost_allocator.rules")

# Demo rules covering common logistics cost categories.
# match_pattern contains keywords that Claude will compare against line item descriptions.
DEFAULT_RULES = [
    {
        "rule_name": "Ocean Freight",
        "description": "Ocean/sea freight charges for container shipping",
        "match_pattern": "ocean freight, sea freight, container shipping, FCL, LCL",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5100-FREIGHT",
        "priority": 1,
    },
    {
        "rule_name": "Air Freight",
        "description": "Air cargo and express freight charges",
        "match_pattern": "air freight, air cargo, air express, air shipment",
        "project_code": "INTL-FREIGHT-002",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5100-FREIGHT",
        "priority": 2,
    },
    {
        "rule_name": "Ground Transportation",
        "description": "Drayage, trucking, and inland ground transport",
        "match_pattern": "drayage, trucking, ground transport, inland, delivery, truck",
        "project_code": "DOM-TRANS-003",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5110-TRUCKING",
        "priority": 3,
    },
    {
        "rule_name": "Customs & Brokerage",
        "description": "Customs clearance, brokerage, and duty fees",
        "match_pattern": "customs, brokerage, clearance, duty, import, export",
        "project_code": "CUSTOMS-OPS-002",
        "cost_center": "COMPLIANCE",
        "gl_account": "5200-CUSTOMS",
        "priority": 4,
    },
    {
        "rule_name": "Warehousing & Storage",
        "description": "Warehouse storage, handling, and distribution fees",
        "match_pattern": "warehousing, storage, warehouse, distribution, handling fee",
        "project_code": "WH-OPS-004",
        "cost_center": "WAREHOUSE",
        "gl_account": "5300-STORAGE",
        "priority": 5,
    },
    {
        "rule_name": "Cargo Insurance",
        "description": "Insurance coverage for cargo in transit",
        "match_pattern": "insurance, cargo insurance, transit insurance, coverage",
        "project_code": "RISK-MGT-005",
        "cost_center": "FINANCE",
        "gl_account": "5400-INSURANCE",
        "priority": 6,
    },
    {
        "rule_name": "Terminal Handling",
        "description": "Port terminal handling charges (THC)",
        "match_pattern": "terminal handling, THC, port handling, terminal charge",
        "project_code": "PORT-OPS-009",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5130-TERMINAL",
        "priority": 7,
    },
    {
        "rule_name": "Demurrage & Detention",
        "description": "Container demurrage and detention fees",
        "match_pattern": "demurrage, detention, container delay, port storage",
        "project_code": "PORT-OPS-008",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5120-DEMURRAGE",
        "priority": 8,
    },
    {
        "rule_name": "Inspections & Compliance",
        "description": "Fumigation, inspection, and regulatory compliance fees",
        "match_pattern": "fumigation, inspection, compliance, regulatory, phytosanitary",
        "project_code": "COMPLIANCE-007",
        "cost_center": "COMPLIANCE",
        "gl_account": "5210-INSPECTION",
        "priority": 9,
    },
    {
        "rule_name": "Fuel Surcharge",
        "description": "Fuel surcharges and bunker adjustment factors",
        "match_pattern": "fuel surcharge, BAF, bunker, fuel adjustment, fuel",
        "project_code": "INTL-FREIGHT-001",
        "cost_center": "LOGISTICS-OPS",
        "gl_account": "5100-FREIGHT",
        "priority": 10,
    },
]


async def get_active_rules(db: AsyncSession) -> list[AllocationRule]:
    """Load all active allocation rules, ordered by priority."""
    result = await db.execute(
        select(AllocationRule)
        .where(AllocationRule.is_active.is_(True))
        .order_by(AllocationRule.priority)
    )
    return list(result.scalars().all())


def format_rules_for_prompt(rules: list[AllocationRule]) -> str:
    """Format allocation rules as text for inclusion in a Claude prompt."""
    if not rules:
        return "No allocation rules configured. Use your best judgment to categorize each charge."

    lines = []
    for rule in rules:
        lines.append(
            f"Rule {rule.priority}: \"{rule.rule_name}\"\n"
            f"  Keywords: {rule.match_pattern}\n"
            f"  Project Code: {rule.project_code}\n"
            f"  Cost Center: {rule.cost_center}\n"
            f"  GL Account: {rule.gl_account}\n"
            f"  Description: {rule.description or 'N/A'}"
        )
    return "\n\n".join(lines)


async def seed_default_rules(db: AsyncSession) -> int:
    """Seed the allocation_rules table with demo business rules.

    Returns the number of rules inserted.
    """
    # Check if rules already exist
    existing = await db.execute(select(AllocationRule).limit(1))
    if existing.scalar_one_or_none() is not None:
        logger.info("Allocation rules already seeded, skipping")
        return 0

    count = 0
    for rule_data in DEFAULT_RULES:
        rule = AllocationRule(id=uuid.uuid4(), **rule_data)
        db.add(rule)
        count += 1

    await db.flush()
    logger.info("Seeded %d default allocation rules", count)
    return count
