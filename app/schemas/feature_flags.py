"""
Pydantic schemas for the feature-flags REST endpoints.
"""
from typing import Optional
from pydantic import BaseModel, Field


class FeatureFlagUpsertRequest(BaseModel):
    """Body for PUT /feature-flags."""
    key: str = Field(..., min_length=1, description="Flag key (must exist in FLAG_DEFAULTS)")
    value: bool = Field(..., description="Desired flag value")
    account_id: Optional[str] = Field(
        default=None,
        description="Hedera account ID for per-account scope.  Omit or set to null for global scope.",
    )


class FeatureFlagDeleteRequest(BaseModel):
    """Body for DELETE /feature-flags."""
    key: str = Field(..., min_length=1, description="Flag key to delete")
    account_id: Optional[str] = Field(
        default=None,
        description="Account scope to delete.  Omit or null for global.",
    )


class FeatureFlagResolveResponse(BaseModel):
    """Response for GET /feature-flags/resolve."""
    key: str
    value: bool
    account_id: Optional[str] = None


class FeatureFlagRow(BaseModel):
    """Single persisted flag row returned by list / upsert."""
    id: str
    key: str
    value: bool
    account_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FeatureFlagDefaultEntry(BaseModel):
    """One entry in the defaults listing."""
    key: str
    default_value: bool
