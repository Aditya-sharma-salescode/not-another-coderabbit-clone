from pydantic import BaseModel, Field
from typing import Literal


class InlineComment(BaseModel):
    path: str = Field(description="File path relative to repo root, e.g. src/auth.py")
    line: int = Field(description="Line number in the new (RIGHT) version of the file")
    body: str = Field(description="Clear, actionable comment explaining the issue and how to fix it")
    severity: Literal["critical", "warning", "suggestion"] = Field(
        description="critical = potential bug/security issue, warning = bad practice, suggestion = improvement"
    )


class PRReview(BaseModel):
    rating: int = Field(ge=1, le=10, description="Overall code quality score 1-10")
    summary: str = Field(
        description=(
            "2-3 paragraph overall review summary covering: what the PR does, "
            "main findings, and whether it aligns with the Jira ticket requirements"
        )
    )
    inline_comments: list[InlineComment] = Field(
        default_factory=list,
        description="Specific inline comments at exact file + line locations. Only reference lines present in the diff.",
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Critical issues that MUST be fixed before merging (bugs, security holes, logic errors)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Non-blocking suggestions for code quality, performance, readability",
    )
    jira_alignment: str = Field(
        default="No Jira ticket provided",
        description="Assessment of how well the code satisfies the Jira ticket requirements",
    )
    security_concerns: list[str] = Field(
        default_factory=list,
        description="Any security vulnerabilities, injection risks, auth issues, or data exposure concerns",
    )
