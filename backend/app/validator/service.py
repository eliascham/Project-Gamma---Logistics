"""
ValidationService — runs all deterministic validators against an extraction.

Stateless, no DB, no Claude. Can be called from the pipeline or standalone.
"""

from __future__ import annotations

import logging

from app.schemas.extraction import DocumentType
from app.schemas.validation import IssueSeverity, ValidationResult
from app.validator.validators import ALL_VALIDATORS

logger = logging.getLogger("gamma.validator")


class ValidationService:
    """Runs deterministic validation checks on extraction output."""

    @staticmethod
    def validate(
        extraction: dict,
        doc_type: DocumentType,
    ) -> ValidationResult:
        """Run all validators and aggregate results.

        Args:
            extraction: The extraction dict (from Pass 2 / refined output).
            doc_type: Document type for type-specific rules.

        Returns:
            ValidationResult with all issues found.
        """
        all_issues = []

        for validator_fn in ALL_VALIDATORS:
            try:
                issues = validator_fn(extraction, doc_type)
                all_issues.extend(issues)
            except Exception:
                logger.exception(
                    "Validator %s raised an exception", validator_fn.__name__
                )

        error_count = sum(
            1 for issue in all_issues if issue.severity == IssueSeverity.ERROR
        )
        warning_count = sum(
            1 for issue in all_issues if issue.severity == IssueSeverity.WARNING
        )

        result = ValidationResult(
            passed=error_count == 0,
            error_count=error_count,
            warning_count=warning_count,
            issues=all_issues,
        )

        if error_count > 0:
            logger.warning(
                "Validation failed: %d errors, %d warnings",
                error_count,
                warning_count,
            )
        elif warning_count > 0:
            logger.info("Validation passed with %d warnings", warning_count)
        else:
            logger.info("Validation passed (clean)")

        return result
