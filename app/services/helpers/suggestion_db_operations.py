"""
Database operation utilities for suggestion service.
"""
import logging
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import SuggestedQuery as SuggestedQueryModel
from app.schemas.suggestions import SuggestionContext
from app.exceptions import SuggestionServiceError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SuggestionDBOperations:
    """Database operations for suggestion service."""
    
    @staticmethod
    def get_suggestions_by_context(
        db: Session, 
        context: SuggestionContext, 
        limit: int
    ) -> List[SuggestedQueryModel]:
        """Retrieve suggested queries by context from database."""
        try:
            logger.info(f"Retrieving suggestions for context: {context}, limit: {limit}")
            
            suggestions = db.query(SuggestedQueryModel)\
                           .filter(SuggestedQueryModel.context == context)\
                           .order_by(SuggestedQueryModel.display_order)\
                           .limit(limit)\
                           .all()
            
            logger.info(f"Retrieved {len(suggestions)} suggestions for context: {context}")
            return suggestions
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving suggestions: {e}")
            raise SuggestionServiceError("Database error occurred while retrieving suggestions", e) from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving suggestions: {e}")
            raise SuggestionServiceError("Unexpected error occurred while retrieving suggestions", e) from e