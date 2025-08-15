"""
Simple cost calculation utility for LLM token usage based on environment configuration.
"""
import logging
from typing import Tuple
from app.config import settings

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate costs for LLM token usage based on configured pricing."""
    
    def calculate_token_costs(
        self, 
        input_tokens: int, 
        output_tokens: int
    ) -> Tuple[float, float, float]:
        """
        Calculate costs for input and output tokens.
        
        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            
        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD
        """
        # Get pricing directly from settings
        input_cost_per_token = settings.llm_input_cost_per_token
        output_cost_per_token = settings.llm_output_cost_per_token
        
        # Calculate costs
        input_cost = input_tokens * input_cost_per_token
        output_cost = output_tokens * output_cost_per_token
        total_cost = input_cost + output_cost
        
        logger.debug(f"Cost calculation: {input_tokens} input tokens × {input_cost_per_token:.8f} = ${input_cost:.6f}")
        logger.debug(f"Cost calculation: {output_tokens} output tokens × {output_cost_per_token:.8f} = ${output_cost:.6f}")
        logger.debug(f"Total cost: ${total_cost:.6f}")
        
        return input_cost, output_cost, total_cost
    
    def get_pricing_info(self) -> dict:
        """Get current pricing configuration."""
        return {
            "input_cost_per_token": settings.llm_input_cost_per_token,
            "output_cost_per_token": settings.llm_output_cost_per_token,
            "model": settings.llm_model,
            "provider": settings.llm_provider
        }