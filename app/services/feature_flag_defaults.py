"""
Single source of truth for all feature flag keys and their hardcoded defaults.

Imported by both the API service and the MCP server so that the two containers
always agree on the full registry without duplicating values.
"""

# ---------------------------------------------------------------------------
# Data-source flags
# ---------------------------------------------------------------------------
DATASOURCE_MIRROR_NODE = "datasource.mirror_node"
DATASOURCE_GRAPHQL = "datasource.graphql"
DATASOURCE_BIGQUERY = "datasource.bigquery"
DATASOURCE_SAUCERSWAP = "datasource.saucerswap"

# ---------------------------------------------------------------------------
# Tool flags
# ---------------------------------------------------------------------------
TOOL_CALL_SDK_METHOD = "tool.call_sdk_method"
TOOL_RETRIEVE_SDK_METHOD = "tool.retrieve_sdk_method"
TOOL_CALCULATE_HBAR_VALUE = "tool.calculate_hbar_value"
TOOL_PROCESS_TOKENS_WITH_BALANCES = "tool.process_tokens_with_balances"
TOOL_ENRICH_TOKENS_WITH_USD_PRICES = "tool.enrich_tokens_with_usd_prices"
TOOL_CONVERT_TIMESTAMP = "tool.convert_timestamp"
TOOL_TEXT_TO_GRAPHQL_QUERY = "tool.text_to_graphql_query"
TOOL_GET_TOKEN_PRICE = "tool.get_token_price"
TOOL_FIND_TOKEN_BY_NAME = "tool.find_token_by_name"
TOOL_FORMAT_TRANSACTION_TYPES = "tool.format_transaction_types"

# ---------------------------------------------------------------------------
# Capability flags (stubs – not yet implemented)
# ---------------------------------------------------------------------------
CAPABILITY_MONETIZATION = "capability.monetization"
CAPABILITY_VISUALIZATIONS = "capability.visualizations"

# ---------------------------------------------------------------------------
# Master registry: key → default value
# ---------------------------------------------------------------------------
FLAG_DEFAULTS: dict[str, bool] = {
    # Data sources – all enabled by default
    DATASOURCE_MIRROR_NODE: True,
    DATASOURCE_GRAPHQL: True,
    DATASOURCE_BIGQUERY: True,
    DATASOURCE_SAUCERSWAP: True,
    # Tools – all enabled by default
    TOOL_CALL_SDK_METHOD: True,
    TOOL_RETRIEVE_SDK_METHOD: True,
    TOOL_CALCULATE_HBAR_VALUE: True,
    TOOL_PROCESS_TOKENS_WITH_BALANCES: True,
    TOOL_ENRICH_TOKENS_WITH_USD_PRICES: True,
    TOOL_CONVERT_TIMESTAMP: True,
    TOOL_TEXT_TO_GRAPHQL_QUERY: True,
    TOOL_GET_TOKEN_PRICE: True,
    TOOL_FIND_TOKEN_BY_NAME: True,
    TOOL_FORMAT_TRANSACTION_TYPES: True,
    # Capabilities – disabled until built
    CAPABILITY_MONETIZATION: False,
    CAPABILITY_VISUALIZATIONS: False,
}
