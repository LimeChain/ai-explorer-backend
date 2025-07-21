"""
Service for managing suggested queries.

This service provides methods to:
- Retrieve suggested queries based on user context
- Maintain production-ready patterns with dependency injection
- Provide comprehensive error handling and validation
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List

from app.db.models import SuggestedQuery as SuggestedQueryModel
from app.schemas.suggestions import SuggestionContext
from app.exceptions import SuggestionServiceError, ValidationError

logger = logging.getLogger(__name__)


class SuggestionService:
    """
    Service class for managing suggested queries.
    
    This service provides methods to retrieve suggested queries based on
    user context, following production-ready patterns with dependency
    injection and comprehensive error handling.
    """

    @staticmethod
    def _validate_context(context: SuggestionContext) -> SuggestionContext:
        """
        Validate suggestion context.
        
        Args:
            context: The suggestion context to validate
            
        Returns:
            SuggestionContext: Validated context
            
        Raises:
            ValidationError: If context is invalid
        """
        if not isinstance(context, SuggestionContext):
            raise ValidationError(f"Invalid context type: {type(context)}. Must be SuggestionContext enum")
        
        return context
    
    @staticmethod
    def get_suggestions_by_context(
        db: Session, 
        context: SuggestionContext,
        limit: int = 100
    ) -> List[SuggestedQueryModel]:
        """
        Retrieves suggested queries from the database filtered by context.
        
        Args:
            db: Database session (dependency injected)
            context: The suggestion context (anonymous or connected)
            limit: Maximum number of suggestions to retrieve (default: 100)
            
        Returns:
            List[SuggestedQueryModel]: List of suggestion objects ordered by display_order
            
        Raises:
            SuggestionServiceError: If database operation fails
            ValidationError: If input validation fails
        """
        try:
            # Validate inputs
            validated_context = SuggestionService._validate_context(context)
            
            if not isinstance(limit, int) or limit <= 0:
                raise ValidationError("Limit must be a positive integer")
            
            if limit > 500:  # Reasonable upper bound
                raise ValidationError("Limit too large (max 500 suggestions)")
            
            logger.debug(f"Retrieving suggestions for context: {validated_context}, limit: {limit}")
            
            # Query suggestions
            suggestions = db.query(SuggestedQueryModel)\
                           .filter(SuggestedQueryModel.context == validated_context)\
                           .order_by(SuggestedQueryModel.display_order)\
                           .limit(limit)\
                           .all()
            
            logger.info(f"Retrieved {len(suggestions)} suggestions for context: {validated_context}")
            return suggestions
            
        except ValidationError:
            logger.warning(f"Validation error in get_suggestions_by_context: context={context}, limit={limit}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_suggestions_by_context: {e}")
            raise SuggestionServiceError("Database error occurred while retrieving suggestions", e)
        except Exception as e:
            logger.error(f"Unexpected error in get_suggestions_by_context: {e}")
            raise SuggestionServiceError("Unexpected error occurred while retrieving suggestions", e)