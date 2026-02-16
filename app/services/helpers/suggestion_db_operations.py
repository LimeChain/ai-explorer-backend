"""
Database operation utilities for suggestion service.
"""
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import SuggestedQuery as SuggestedQueryModel
from app.schemas.suggestions import SuggestionContext
from app.exceptions import SuggestionServiceError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SuggestionDBOperations:
    """Database operations for suggestion service."""

    @staticmethod
    async def get_suggestions_by_context(
        db: AsyncSession,
        context: SuggestionContext,
        limit: int
    ) -> List[SuggestedQueryModel]:
        """Retrieve suggested queries by context from database."""
        try:
            logger.info("Retrieving suggestions for context: %s, limit: %s", context, limit)

            result = await db.execute(
                select(SuggestedQueryModel)
                .where(SuggestedQueryModel.context == context)
                .order_by(SuggestedQueryModel.display_order)
                .limit(limit)
            )
            suggestions = result.scalars().all()

            logger.info("Retrieved %s suggestions for context: %s", len(suggestions), context)
            return list(suggestions)

        except SQLAlchemyError as e:
            logger.error("Database error retrieving suggestions: %s", e)
            raise SuggestionServiceError("Database error occurred while retrieving suggestions", e) from e
        except Exception as e:
            logger.error("Unexpected error retrieving suggestions: %s", e)
            raise SuggestionServiceError("Unexpected error occurred while retrieving suggestions", e) from e
