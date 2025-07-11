import sys
from pathlib import Path
from unittest.mock import Mock

# Add the mcp_servers directory to Python path FIRST to prioritize local app
mcp_servers_root = Path(__file__).parent
sys.path.insert(0, str(mcp_servers_root))

# Mock the hiero_mirror module since it's a local SDK
sys.modules['hiero_mirror'] = Mock()
sys.modules['hiero_mirror'].MirrorNodeClient = Mock()

