"""
Tool call parsing utilities for LLM responses.
"""
import json
import logging
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger(__name__)


class ToolCallParser:
    """Handles parsing of tool calls from LLM responses."""
    
    def __init__(self):
        self._extraction_strategies: List[Callable[[str], Optional[str]]] = [
            self._extract_json_from_codeblock,
            self._extract_json_from_braces,
            self._extract_raw_content
        ]
    
    def parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response expecting JSON format."""
        if not content or not content.strip():
            return None
        
        content = content.strip()
        
        for strategy in self._extraction_strategies:
            json_candidate = strategy(content)
            if json_candidate:
                tool_call = self._try_parse_json(json_candidate)
                if tool_call:
                    return tool_call
        
        return None
    
    def _extract_json_from_codeblock(self, content: str) -> Optional[str]:
        """Extract JSON from ```json code blocks."""
        if "```json" not in content:
            return None
        
        start_idx = content.find("```json") + 7
        end_idx = content.find("```", start_idx)
        if end_idx == -1:
            return None
        
        return content[start_idx:end_idx].strip()
    
    def _extract_json_from_braces(self, content: str) -> Optional[str]:
        """Extract JSON from first { to last } in content."""
        if "{" not in content or "}" not in content:
            return None
        
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            return None
        
        return content[start_idx:end_idx]
    
    def _extract_raw_content(self, content: str) -> str:
        """Return content as-is for direct JSON parsing."""
        return content
    
    def _try_parse_json(self, json_candidate: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse JSON and validate tool call structure."""
        try:
            parsed = json.loads(json_candidate)
            return self._validate_tool_call(parsed)
        except json.JSONDecodeError:
            return None
    
    def _validate_tool_call(self, parsed_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and extract tool call from parsed JSON."""
        if not isinstance(parsed_json, dict) or "tool_call" not in parsed_json:
            return None
    
        tool_call = parsed_json["tool_call"]
        if not isinstance(tool_call, dict) or "name" not in tool_call:
            return None
        
        return tool_call