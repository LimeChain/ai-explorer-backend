"""
Centralized logging configuration for the AI Explorer project.
Provides consistent logging across all services with structured format and correlation IDs.
"""
import logging
import logging.config
import json
import uuid
import contextvars
import sys
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Context variable for correlation ID tracking
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar('correlation_id', default='')


class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get('')
        return True


class JSONFormatter(logging.Formatter):
    """Format logs as structured JSON."""
    
    def format(self, record):
        log_obj = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id') and record.correlation_id:
            log_obj['correlation_id'] = record.correlation_id
        
        # Add exception info if available
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                          'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'message', 'exc_info',
                          'exc_text', 'stack_info', 'correlation_id']:
                log_obj[key] = value
        
        return json.dumps(log_obj, default=str)


class RichCorrelationHandler(RichHandler if RICH_AVAILABLE else logging.Handler):
    """Custom Rich handler that includes correlation IDs in the output."""
    
    def __init__(self, *args, **kwargs):
        if not RICH_AVAILABLE:
            super().__init__()
            return
        super().__init__(*args, **kwargs)
    
    def emit(self, record):
        if not RICH_AVAILABLE:
            return
            
        # Add correlation ID to the message if available
        correlation_id_str = getattr(record, 'correlation_id', '')
        if correlation_id_str:
            # Create a new record with modified message to include correlation ID
            original_msg = record.getMessage()
            record.msg = f"[{correlation_id_str}] {original_msg}"
            record.args = ()
        
        super().emit(record)


class ColoredFormatter(logging.Formatter):
    """Simple ANSI color formatter as fallback when Rich is not available."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    # Simple emojis for visual clarity
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # Get the base formatted message
        message = super().format(record)
        
        # Add emoji and color codes if output supports it
        emoji = self.EMOJIS.get(record.levelname, '')
        if sys.stdout.isatty():
            level_color = self.COLORS.get(record.levelname, '')
            if level_color:
                # Color the level name and add emoji
                colored_level = f"{emoji} {level_color}{record.levelname}{self.RESET}"
                message = message.replace(record.levelname, colored_level, 1)
        else:
            # Add emoji even without color support
            if emoji:
                message = message.replace(record.levelname, f"{emoji} {record.levelname}", 1)
        
        # Add important extra fields to the message
        if hasattr(record, 'sql_query') and record.sql_query:
            message += f"\n    SQL: {record.sql_query}"
        
        if hasattr(record, 'estimated_cost') and record.estimated_cost is not None:
            message += f"\n    Cost: ${record.estimated_cost:.6f}"
        
        if hasattr(record, 'bytes_to_process') and record.bytes_to_process:
            gb = record.bytes_to_process / (10**9)
            message += f" ({gb:.2f} GB)"
            
        if hasattr(record, 'execution_time_ms') and record.execution_time_ms:
            message += f"\n    Time: {record.execution_time_ms}ms"
            
        if hasattr(record, 'rows_returned') and record.rows_returned is not None:
            message += f"\n    Rows: {record.rows_returned}"
        
        return message


class DetailedFormatter(logging.Formatter):
    """Enhanced formatter that shows important extra fields inline."""
    
    # Simple emojis for visual clarity
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # Get the base formatted message
        message = super().format(record)
        
        # Add emoji to level name
        emoji = self.EMOJIS.get(record.levelname, '')
        if emoji:
            message = message.replace(record.levelname, f"{emoji} {record.levelname}", 1)
        
        # Add important extra fields to the message
        if hasattr(record, 'sql_query') and record.sql_query:
            message += f"\n    SQL: {record.sql_query}"
        
        if hasattr(record, 'estimated_cost') and record.estimated_cost is not None:
            message += f"\n    Cost: ${record.estimated_cost:.6f}"
        
        if hasattr(record, 'bytes_to_process') and record.bytes_to_process:
            gb = record.bytes_to_process / (10**9)
            message += f" ({gb:.2f} GB)"
            
        if hasattr(record, 'execution_time_ms') and record.execution_time_ms:
            message += f"\n    Time: {record.execution_time_ms}ms"
            
        if hasattr(record, 'rows_returned') and record.rows_returned is not None:
            message += f"\n    Rows: {record.rows_returned}"
        
        return message


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:8]


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context."""
    if corr_id is None:
        corr_id = generate_correlation_id()
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id.get('')


def setup_logging(
    level: str = "INFO",
    use_json: bool = False,
    log_file: Optional[str] = None,
    service_name: str = "mcp",
    use_colors: Optional[bool] = None
) -> bool:
    """
    Setup centralized logging configuration for all services.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON formatting
        log_file: Optional log file path
        service_name: Name of the service (for logger hierarchy)
        use_colors: Whether to use colored output (auto-detect if None)
        
    Returns:
        bool: True if setup was successful, False otherwise
    """
    try:
        # Auto-detect color support if not specified
        if use_colors is None:
            use_colors = (
                RICH_AVAILABLE and 
                not use_json and 
                sys.stdout.isatty() and 
                not log_file  # Don't use colors when logging to file
            )
        
        # Create logs directory if needed
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Base configuration
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'detailed': {
                    '()': DetailedFormatter,
                    'format': '%(asctime)s [%(levelname)s] %(name)s [%(correlation_id)s]: %(message)s (%(filename)s:%(lineno)d)',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'colored': {
                    '()': ColoredFormatter,
                    'format': '%(asctime)s [%(levelname)s] %(name)s [%(correlation_id)s]: %(message)s (%(filename)s:%(lineno)d)',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'json': {
                    '()': JSONFormatter,
                }
            },
            'filters': {
                'correlation': {
                    '()': CorrelationIDFilter,
                }
            },
            'handlers': {},
        }

        # Configure console handler based on color support
        if use_colors and RICH_AVAILABLE and not use_json:
            # Use Rich handler for colored console output (only in development)
            from app.settings import settings
            console = Console(
                stderr=False,  # Use stdout
                force_terminal=settings.force_terminal, 
                color_system="auto",
                width=None  # Auto-detect width
            )
            
            config['handlers']['console'] = {
                '()': RichCorrelationHandler,
                'level': level,
                'console': console,
                'show_time': True,
                'show_level': True,
                'show_path': False,  # Disable path for performance
                'enable_link_path': False,
                'markup': False,
                'rich_tracebacks': False,  # Disable for performance in production
                'tracebacks_show_locals': False,
                'filters': ['correlation']
            }
        else:
            # Use standard console handler
            formatter = 'json' if use_json else ('colored' if use_colors and sys.stdout.isatty() else 'detailed')
            config['handlers']['console'] = {
                'class': 'logging.StreamHandler',
                'level': level,
                'formatter': formatter,
                'filters': ['correlation'],
                'stream': 'ext://sys.stdout'
            }

        # Configure loggers
        config['loggers'] = {
            # Main application loggers
            f'{service_name}': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            f'{service_name}.services': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            f'{service_name}.api': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            # Third-party library loggers (reduce noise)
            'httpx': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'openai': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'sqlalchemy.engine': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'fastapi': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            }
        }
        
        config['root'] = {
            'level': level,
            'handlers': ['console']
        }
        
        # Add file handler if specified
        if log_file:
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': level,
                'formatter': 'json' if use_json else 'detailed',
                'filters': ['correlation'],
                'filename': log_file,
                'maxBytes': 52428800,  # 50MB (increased for production)
                'backupCount': 10,  # Keep more backups for investigation
                'encoding': 'utf8',
                'delay': True  # Don't create log file until first log
            }
            
            # Add file handler to all loggers
            for logger_config in config['loggers'].values():
                if 'handlers' in logger_config:
                    logger_config['handlers'].append('file')
            config['root']['handlers'].append('file')
        
        logging.config.dictConfig(config)
        
        return True
        
    except Exception as e:
        # Fallback to basic configuration
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.error("Failed to setup advanced logging configuration: %s", e)
        return False


def get_logger(name: str, service_name: str = "mcp") -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        service_name: Service name prefix
        
    Returns:
        Logger instance
    """
    # Convert module path to service-specific logger name
    if name.startswith('app.'):
        logger_name = name.replace('app.', f'{service_name}.')
    elif name.startswith('mcp_servers.'):
        logger_name = name.replace('mcp_servers.', f'{service_name}.')
    else:
        logger_name = f"{service_name}.{name}"
    
    return logging.getLogger(logger_name)


# Convenience functions for different service types
def get_service_logger(service_name: str, app_name: str = "mcp") -> logging.Logger:
    """Get a logger for a service."""
    return logging.getLogger(f"{app_name}.services.{service_name}")


def get_api_logger(endpoint_name: str, app_name: str = "mcp") -> logging.Logger:
    """Get a logger for an API endpoint."""
    return logging.getLogger(f"{app_name}.api.{endpoint_name}")