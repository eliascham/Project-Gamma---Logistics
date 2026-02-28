"""Validation schemas for extraction output verification."""

import enum

from pydantic import BaseModel, Field


class IssueSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """A single validation issue found in an extraction."""

    field: str = Field(..., description="Dot-path to the field (e.g., 'line_items.0.total')")
    severity: IssueSeverity = Field(..., description="error = must fix, warning = likely wrong, info = check")
    message: str = Field(..., description="Human-readable description of the issue")
    expected: str | None = Field(None, description="What was expected (if applicable)")
    actual: str | None = Field(None, description="What was found")
    rule: str = Field(..., description="Short rule name (e.g., 'totals_mismatch', 'missing_required')")


class ValidationResult(BaseModel):
    """Aggregate result of running all validators on an extraction."""

    passed: bool = Field(..., description="True if no errors (warnings are OK)")
    error_count: int = Field(0)
    warning_count: int = Field(0)
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0
