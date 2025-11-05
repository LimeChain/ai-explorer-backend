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

    def parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """Parse multiple tool calls from LLM response (supports batch calling)."""
        if not content or not content.strip():
            return []

        content = content.strip()
        tool_calls = []

        # Extract complete JSON objects by counting braces
        # Look for multiple {"tool_call": {...}} objects
        tool_calls = self._extract_multiple_json_objects(content)

        if tool_calls:
            logger.info(f"📦 Parsed {len(tool_calls)} tool calls in batch")
            return tool_calls

        # Fallback: try parsing entire content as single tool call
        for strategy in self._extraction_strategies:
            json_candidate = strategy(content)
            if json_candidate:
                tool_call = self._try_parse_json(json_candidate)
                if tool_call:
                    return [tool_call]

        return []

    def _extract_multiple_json_objects(self, content: str) -> List[Dict[str, Any]]:
        """Extract multiple complete JSON objects from content by counting braces."""
        tool_calls = []
        i = 0

        while i < len(content):
            # Skip whitespace
            while i < len(content) and content[i].isspace():
                i += 1

            if i >= len(content):
                break

            # Look for start of JSON object
            if content[i] != '{':
                i += 1
                continue

            # Count braces to find complete JSON object
            brace_count = 0
            start = i
            in_string = False
            escape_next = False
            found_complete = False

            while i < len(content):
                char = content[i]

                if escape_next:
                    escape_next = False
                    i += 1
                    continue

                if char == '\\':
                    escape_next = True
                    i += 1
                    continue

                if char == '"':
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found complete JSON object
                            json_str = content[start:i+1]
                            tool_call = self._try_parse_json(json_str)
                            if tool_call:
                                tool_calls.append(tool_call)
                            i += 1
                            found_complete = True
                            break

                i += 1

            # If we reached end of content with incomplete JSON, try to fix it
            if not found_complete and brace_count > 0:
                json_str = content[start:]
                # Try to fix missing braces
                fixed_json = self._fix_missing_braces(json_str)
                tool_call = self._try_parse_json(fixed_json)
                if tool_call:
                    tool_calls.append(tool_call)
                    logger.info("✅ Fixed incomplete JSON object at end of content")
                # Move to end since we consumed the rest
                break

        return tool_calls

    def parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse single tool call from LLM response (legacy method)."""
        tool_calls = self.parse_tool_calls(content)
        return tool_calls[0] if tool_calls else None
    
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
            # Fix common Python-to-JSON conversion issues
            fixed_json = self._fix_python_syntax(json_candidate)
            parsed = json.loads(fixed_json)
            return self._validate_tool_call(parsed)
        except json.JSONDecodeError as e:
            # Try to fix missing closing braces
            logger.debug(f"JSON parse error: {e}. Attempting to fix...")
            try:
                fixed_json = self._fix_missing_braces(json_candidate)
                parsed = json.loads(fixed_json)
                logger.info("✅ Fixed malformed JSON by adding missing closing braces")
                return self._validate_tool_call(parsed)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON even after fixes: {json_candidate[:100]}...")
                return None
    
    def _fix_missing_braces(self, json_str: str) -> str:
        """Fix missing closing braces/brackets in JSON string."""
        # First apply Python syntax fixes
        json_str = self._fix_python_syntax(json_str)

        # Count opening and closing braces
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')

        # Add missing closing characters
        if close_braces < open_braces:
            json_str += '}' * (open_braces - close_braces)
        if close_brackets < open_brackets:
            json_str += ']' * (open_brackets - close_brackets)

        return json_str

    def _fix_python_syntax(self, json_str: str) -> str:
        """Fix common Python syntax issues in JSON strings."""
        # Replace Python boolean literals with JSON boolean literals
        json_str = json_str.replace(': True', ': true')
        json_str = json_str.replace(': False', ': false')
        json_str = json_str.replace(': None', ': null')

        # Handle cases with different spacing
        json_str = json_str.replace(':True', ':true')
        json_str = json_str.replace(':False', ':false')
        json_str = json_str.replace(':None', ':null')

        return json_str
    
    def _validate_tool_call(self, parsed_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and extract tool call from parsed JSON."""
        if not isinstance(parsed_json, dict) or "tool_call" not in parsed_json:
            return None
    
        tool_call = parsed_json["tool_call"]
        if not isinstance(tool_call, dict) or "name" not in tool_call:
            return None
        
        return tool_call