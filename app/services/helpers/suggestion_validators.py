"""
Validation utilities for suggestion service operations.
"""
from app.exceptions import ValidationError
from app.schemas.suggestions import SuggestionContext
from app.services.helpers.constants import MAX_SUGGESTION_LIMIT


class SuggestionValidators:
    """Centralized validation logic for suggestion operations."""
    
    @staticmethod
    def validate_context(context: SuggestionContext) -> SuggestionContext:
        """Validate suggestion context."""
        if not isinstance(context, SuggestionContext):
            raise ValidationError(f"Invalid context type: {type(context)}. Must be SuggestionContext enum")
        return context
    
    @staticmethod
    def validate_limit(limit: int) -> int:
        """Validate suggestion query limit."""
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("Limit must be a positive integer")
        
        if limit > MAX_SUGGESTION_LIMIT:
            raise ValidationError(f"Limit too large (max {MAX_SUGGESTION_LIMIT} suggestions)")
        
        return limit