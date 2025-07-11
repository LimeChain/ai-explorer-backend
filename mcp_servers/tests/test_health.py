import pytest
from app.main import health_check


@pytest.mark.asyncio
async def test_health_check():
    """Test the health check MCP tool."""
    result = await health_check()
    assert result["status"] == "ok"
    assert result["service"] == "HederaMirrorNode"