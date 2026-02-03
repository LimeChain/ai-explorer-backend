"""
Feature-flags REST endpoints.

Read endpoints (GET) are open.  Write endpoints (PUT, DELETE) require a valid
X-Admin-Key header.  This guard is intentionally self-contained and does not
depend on a session-based admin auth system (that is Epic 9).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.schemas.feature_flags import (
    FeatureFlagDefaultEntry,
    FeatureFlagDeleteRequest,
    FeatureFlagResolveResponse,
    FeatureFlagRow,
    FeatureFlagUpsertRequest,
)
from app.services import feature_flag_service as svc
from app.services.feature_flag_defaults import FLAG_DEFAULTS
from app.utils.logging_config import get_api_logger

logger = get_api_logger("feature_flags")

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin-key guard
# ---------------------------------------------------------------------------
def _require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """Raise 403 if the provided key does not match the configured secret."""
    expected = settings.admin_api_key.get_secret_value()
    if x_admin_key is None or x_admin_key != expected:
        logger.warning("Admin key check failed")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


# ---------------------------------------------------------------------------
# GET endpoints (no auth required)
# ---------------------------------------------------------------------------
@router.get("/feature-flags", response_model=list[FeatureFlagRow])
def list_flags(db: Session = Depends(get_db)) -> list[FeatureFlagRow]:
    """List all persisted feature-flag overrides."""
    return [FeatureFlagRow(**row) for row in svc.list_flags(db)]


@router.get("/feature-flags/defaults", response_model=list[FeatureFlagDefaultEntry])
def get_defaults() -> list[FeatureFlagDefaultEntry]:
    """Return the full registry of flag keys and their hardcoded defaults."""
    return [FeatureFlagDefaultEntry(key=k, default_value=v) for k, v in FLAG_DEFAULTS.items()]


@router.get("/feature-flags/resolve", response_model=FeatureFlagResolveResponse)
def resolve_flag(
    key: str,
    account_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> FeatureFlagResolveResponse:
    """
    Resolve a single flag for the given scope.

    Resolution order: per-account → global → hardcoded default.
    """
    try:
        value = svc.resolve_flag(db, key, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return FeatureFlagResolveResponse(key=key, value=value, account_id=account_id)


# ---------------------------------------------------------------------------
# Write endpoints (admin key required)
# ---------------------------------------------------------------------------
@router.put("/feature-flags", response_model=FeatureFlagRow, dependencies=[Depends(_require_admin_key)])
def upsert_flag(
    body: FeatureFlagUpsertRequest,
    db: Session = Depends(get_db),
) -> FeatureFlagRow:
    """Create or update a feature flag.  Requires X-Admin-Key header."""
    try:
        row = svc.upsert_flag(db, body.key, body.value, body.account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return FeatureFlagRow(**row)


@router.delete("/feature-flags", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_require_admin_key)])
def delete_flag(
    body: FeatureFlagDeleteRequest,
    db: Session = Depends(get_db),
) -> None:
    """Delete a persisted flag override (reverts to hardcoded default).  Requires X-Admin-Key header."""
    deleted = svc.delete_flag(db, body.key, body.account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")
