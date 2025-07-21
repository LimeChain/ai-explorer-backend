"""
Suggestions endpoint for the AI Explorer backend service.
"""
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.services.suggestion_service import SuggestionService
from app.schemas.suggestions import SuggestionContext, SuggestedQuery, SuggestedQueriesResponse
from app.db.session import get_db
from app.exceptions import SuggestionServiceError, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/suggested-queries",
    response_model=SuggestedQueriesResponse,
    summary="Get Suggested Queries",
    tags=["Suggestions"],
    responses={
        200: {"description": "Successfully retrieved suggested queries"},
        400: {"description": "Invalid request parameters"},
        500: {"description": "Internal server error"}
    }
)
def get_suggested_queries(
    context: SuggestionContext = Query(
        default=SuggestionContext.ANONYMOUS, 
        description="The user context for suggestions (anonymous or connected)"
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of suggestions to return (1-100)"
    ),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of suggested queries from the database based on the user's context.

    This endpoint provides contextually relevant query suggestions to help users
    explore blockchain data through natural language queries.

    Args:
        context: User context - 'anonymous' for general suggestions, 'connected' for wallet-specific
        limit: Maximum number of suggestions to return (1-100, default: 50)
        db: Database session (dependency injected)

    Returns:
        SuggestedQueriesResponse: List of suggested queries with metadata

    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    try:
        logger.info(f"Retrieving suggested queries for context: {context}, limit: {limit}")
        
        # Get suggestions using refactored service
        db_suggestions = SuggestionService.get_suggestions_by_context(
            db=db, 
            context=context,
            limit=limit
        )
        
        # Map SQLAlchemy models to Pydantic schemas for the response
        suggestions = [SuggestedQuery(query=s.query) for s in db_suggestions]
        
        logger.info(f"Successfully returned {len(suggestions)} suggestions for context: {context}")
        return SuggestedQueriesResponse(suggestions=suggestions)
        
    except ValidationError as e:
        logger.warning(f"Validation error in get_suggested_queries: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except SuggestionServiceError as e:
        logger.error(f"Service error in get_suggested_queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve suggestions")
    except Exception as e:
        logger.error(f"Unexpected error in get_suggested_queries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")