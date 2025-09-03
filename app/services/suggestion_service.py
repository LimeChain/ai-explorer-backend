"""
Service for managing suggested queries.
"""
from sqlalchemy.orm import Session
from typing import List

from app.db.models import SuggestedQuery as SuggestedQueryModel
from app.schemas.suggestions import SuggestionContext
from app.exceptions import ValidationError
from app.services.helpers.suggestion_validators import SuggestionValidators
from app.services.helpers.suggestion_db_operations import SuggestionDBOperations
from app.services.helpers.constants import DEFAULT_SUGGESTION_LIMIT
from app.utils.logging_config import get_service_logger

logger = get_service_logger("suggestion_service")


class SuggestionService:
    """Service class for managing suggested queries."""

    
    @staticmethod
    def get_suggestions_by_context(
        db: Session, 
        context: SuggestionContext,
        limit: int = DEFAULT_SUGGESTION_LIMIT
    ) -> List[SuggestedQueryModel]:
        """Retrieve suggested queries from the database filtered by context."""
        try:
            # Validate inputs
            validated_context = SuggestionValidators.validate_context(context)
            validated_limit = SuggestionValidators.validate_limit(limit)
            
            # Query suggestions
            return SuggestionDBOperations.get_suggestions_by_context(
                db, validated_context, validated_limit
            )
            
        except ValidationError:
            logger.warning("⚠️ Validation error in get_suggestions_by_context: context=%s, limit=%s", context, limit)
            raise