"""
Suggestions endpoint for the AI Explorer backend service.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.suggestion_service import SuggestionService
from app.schemas.suggestions import SuggestionContext, SuggestedQuery, SuggestedQueriesResponse
from app.db.session import get_async_db
from app.exceptions import SuggestionServiceError, ValidationError
from app.utils.logging_config import get_api_logger

logger = get_api_logger("suggestions")
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
async def get_suggested_queries(
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
    db: AsyncSession = Depends(get_async_db)
) -> SuggestedQueriesResponse:
    """
    Retrieves a list of suggested queries from the database based on the user's context.
    """
    try:
        logger.info("Retrieving suggested queries for context: %s, limit: %s", context, limit)

        db_suggestions = await SuggestionService.get_suggestions_by_context(
            db=db,
            context=context,
            limit=limit
        )

        suggestions = [SuggestedQuery(query=s.query) for s in db_suggestions]

        logger.info("Successfully returned %s suggestions for context: %s", len(suggestions), context)
        return SuggestedQueriesResponse(suggestions=suggestions)

    except ValidationError as e:
        logger.warning("Validation error in get_suggested_queries: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SuggestionServiceError as e:
        logger.error("Service error in get_suggested_queries: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve suggestions") from e
    except Exception as e:
        logger.error("Unexpected error in get_suggested_queries: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
