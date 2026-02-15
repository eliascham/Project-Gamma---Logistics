"""
Eval endpoints — run extraction accuracy evaluations and view results.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.eval.extraction_eval import ExtractionEvaluator

router = APIRouter()


@router.post("/run")
async def run_eval(
    db: AsyncSession = Depends(get_db),
):
    """Run the extraction eval suite against ground truth documents.

    This calls Claude for each ground truth document (2 passes each),
    so it may take a few minutes depending on document count.
    """
    evaluator = ExtractionEvaluator(settings)

    try:
        report = await evaluator.run()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eval failed: {e}")

    # Store results in eval_results table
    eval_id = uuid.uuid4()
    await db.execute(
        sa_text("""
            INSERT INTO eval_results (
                id, eval_type, results, document_count,
                overall_accuracy, field_scores, model_used, created_at
            ) VALUES (
                :id, :eval_type, CAST(:results AS json), :document_count,
                :overall_accuracy, CAST(:field_scores AS json), :model_used, NOW()
            )
        """),
        {
            "id": eval_id,
            "eval_type": "extraction",
            "results": json.dumps(report.to_dict(), default=str),
            "document_count": report.total_documents,
            "overall_accuracy": report.overall_pass2_accuracy,
            "field_scores": json.dumps({
                "pass1_accuracy": report.overall_pass1_accuracy,
                "pass2_accuracy": report.overall_pass2_accuracy,
            }),
            "model_used": report.model_used,
        },
    )
    await db.flush()

    return report.to_dict()


@router.get("/results")
async def list_eval_results(
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
):
    """List past eval run results, most recent first."""
    result = await db.execute(
        sa_text("""
            SELECT id, eval_type, document_count, overall_accuracy,
                   model_used, created_at
            FROM eval_results
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()

    return {
        "results": [
            {
                "id": str(row[0]),
                "eval_type": row[1],
                "document_count": row[2],
                "overall_accuracy": row[3],
                "model_used": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/results/{eval_id}")
async def get_eval_result(
    eval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed results for a specific eval run."""
    result = await db.execute(
        sa_text("SELECT id, eval_type, results, created_at FROM eval_results WHERE id = :id"),
        {"id": eval_id},
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Eval result not found")

    results_data = row[2]
    if isinstance(results_data, str):
        results_data = json.loads(results_data)

    return {
        "id": str(row[0]),
        "eval_type": row[1],
        "results": results_data,
        "created_at": row[3].isoformat() if row[3] else None,
    }
