"""
TPS (Transactions Per Second) validation utilities.

This module provides validation and calculation helpers for TPS queries
to ensure accurate transaction rate reporting and prevent calculation errors.
"""
from typing import Dict, Optional


class TPSValidator:
    """Validates TPS calculations to prevent inaccurate responses."""

    # Hedera TPS thresholds based on network behavior
    TYPICAL_MIN_TPS = 0.1  # Network can be quiet
    TYPICAL_MAX_TPS = 50.0  # Normal peak activity
    THEORETICAL_MAX_TPS = 10000.0  # Theoretical maximum
    WARNING_THRESHOLD = 100.0  # Values above this need validation

    @staticmethod
    def validate_tps(
        transaction_count: int,
        time_period_seconds: int,
        context: Optional[str] = None
    ) -> Dict:
        """
        Validates TPS calculation and returns result with warnings if needed.

        Args:
            transaction_count: Number of transactions in the period
            time_period_seconds: Time period in seconds
            context: Optional context for the calculation (e.g., "last 60 seconds")

        Returns:
            Dict with validation results:
            {
                "tps": float,
                "is_valid": bool,
                "warning": Optional[str],
                "calculation": str,
                "context_message": str
            }

        Example:
            >>> TPSValidator.validate_tps(480, 60)
            {
                "tps": 8.0,
                "is_valid": True,
                "warning": None,
                "calculation": "480 transactions / 60 seconds = 8.00 TPS",
                "context_message": "Hedera mainnet typically processes..."
            }
        """
        if time_period_seconds <= 0:
            return {
                "tps": 0.0,
                "is_valid": False,
                "warning": "Invalid time period: must be greater than 0 seconds",
                "calculation": f"{transaction_count} / {time_period_seconds} = INVALID",
                "context_message": ""
            }

        tps = transaction_count / time_period_seconds
        calculation = (
            f"{transaction_count:,} transactions / "
            f"{time_period_seconds:,} seconds = {tps:.2f} TPS"
        )

        # Validate TPS value
        is_valid = True
        warning = None
        context_message = (
            "Hedera mainnet typically processes 5-10 transactions per second, "
            "with peaks up to 20-50 TPS during high activity."
        )

        if tps > TPSValidator.WARNING_THRESHOLD:
            is_valid = False
            warning = (
                f"VALIDATION FAILED: Calculated TPS ({tps:.2f}) exceeds expected "
                f"threshold ({TPSValidator.WARNING_THRESHOLD}). Please verify your "
                f"calculation. Hedera mainnet typically runs at 5-10 TPS, rarely "
                f"exceeding 50 TPS."
            )
        elif tps > TPSValidator.TYPICAL_MAX_TPS:
            warning = (
                f"Note: This TPS value ({tps:.2f}) is higher than typical Hedera "
                f"mainnet activity (5-10 TPS). This may indicate a period of "
                f"unusually high network activity."
            )

        return {
            "tps": round(tps, 2),
            "is_valid": is_valid,
            "warning": warning,
            "calculation": calculation,
            "context_message": context_message
        }

    @staticmethod
    def get_recommended_time_window(query_type: str) -> int:
        """
        Returns recommended time window in seconds for different TPS query types.

        Args:
            query_type: Type of query
                - "current" or "now": Last 1 minute
                - "recent": Last 5 minutes
                - "average": Last 10 minutes
                - "hourly": Last 1 hour
                - "daily": Last 24 hours

        Returns:
            Time window in seconds

        Example:
            >>> TPSValidator.get_recommended_time_window("current")
            60
        """
        windows = {
            "current": 60,      # Last 1 minute
            "now": 60,          # Last 1 minute
            "recent": 300,      # Last 5 minutes
            "average": 600,     # Last 10 minutes
            "hourly": 3600,     # Last 1 hour
            "daily": 86400      # Last 24 hours
        }
        return windows.get(query_type.lower(), 300)  # Default to 5 minutes

    @staticmethod
    def format_tps_response(
        tps: float,
        transaction_count: int,
        time_period_seconds: int,
        include_context: bool = True
    ) -> str:
        """
        Formats a user-friendly TPS response with calculation details.

        Args:
            tps: Calculated TPS value
            transaction_count: Number of transactions
            time_period_seconds: Time period in seconds
            include_context: Whether to include Hedera context message

        Returns:
            Formatted response string

        Example:
            >>> TPSValidator.format_tps_response(8.2, 492, 60)
            "The current transaction rate is approximately 8.2 TPS (492 transactions
            in the last 60 seconds). Hedera mainnet typically processes 5-10
            transactions per second..."
        """
        # Convert seconds to human-readable time
        if time_period_seconds == 60:
            time_desc = "60 seconds (1 minute)"
        elif time_period_seconds == 300:
            time_desc = "300 seconds (5 minutes)"
        elif time_period_seconds == 3600:
            time_desc = "3,600 seconds (1 hour)"
        elif time_period_seconds == 86400:
            time_desc = "86,400 seconds (24 hours)"
        else:
            time_desc = f"{time_period_seconds:,} seconds"

        response = (
            f"The current transaction rate is approximately {tps:.2f} TPS "
            f"({transaction_count:,} transactions in the last {time_desc})."
        )

        if include_context:
            response += (
                " Hedera mainnet typically processes 5-10 transactions per second, "
                "with peaks up to 20-50 TPS during high network activity."
            )

        return response
