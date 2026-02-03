"""
@require_flag decorator for MCP tools.

Usage (must be placed INSIDE @mcp.tool(), i.e. closer to the function):

    @mcp.tool()
    @require_flag("tool.get_token_price", datasource_flags=["datasource.saucerswap"])
    async def get_token_price(...):
        ...

When any required flag is off the decorated function short-circuits and
returns a JSON-serialisable dict with success=False.  No exception is raised –
the LLM agent sees a normal tool response and can explain the situation to the
user.

The wrapper preserves the original function's signature via functools.wraps
(FastMCP introspects __wrapped__ for the tool schema) and correctly produces
an async wrapper for async functions / a sync wrapper for sync functions
(FastMCP checks inspect.iscoroutinefunction).
"""
import functools
import inspect
from typing import Any

from .feature_flag_reader import resolve_flag
from .logging_config import get_logger

logger = get_logger(__name__, service_name="mcp")


def _disabled_response(flag_key: str, is_datasource: bool) -> dict[str, Any]:
    error_type = "DataSourceDisabled" if is_datasource else "FeatureFlagDisabled"
    scope = "data source" if is_datasource else "tool"
    return {
        "success": False,
        "error": error_type,
        "message": f"This {scope} is currently disabled (flag: {flag_key}).  "
                   f"Please contact an administrator to re-enable it.",
    }


def require_flag(tool_flag: str, datasource_flags: list[str] | None = None) -> Any:
    """
    Decorator factory.  *tool_flag* is the primary flag that gates the tool
    itself; *datasource_flags* is an optional list of data-source flags that
    the tool also depends on.
    """
    if datasource_flags is None:
        datasource_flags = []

    def decorator(func: Any) -> Any:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Check tool flag first
                if not resolve_flag(tool_flag):
                    logger.info("Tool gated by flag %s (disabled)", tool_flag)
                    return _disabled_response(tool_flag, is_datasource=False)
                # Check each data-source dependency
                for ds_flag in datasource_flags:
                    if not resolve_flag(ds_flag):
                        logger.info("Tool gated by data-source flag %s (disabled)", ds_flag)
                        return _disabled_response(ds_flag, is_datasource=True)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not resolve_flag(tool_flag):
                    logger.info("Tool gated by flag %s (disabled)", tool_flag)
                    return _disabled_response(tool_flag, is_datasource=False)
                for ds_flag in datasource_flags:
                    if not resolve_flag(ds_flag):
                        logger.info("Tool gated by data-source flag %s (disabled)", ds_flag)
                        return _disabled_response(ds_flag, is_datasource=True)
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator
