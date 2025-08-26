"""
Centralized logging configuration for the MCP server.
Provides structured logging with correlation IDs and configurable levels.
"""
import logging
import logging.config
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
import contextvars
from pathlib import Path

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
        
        return json.dumps(log_obj)

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
    log_file: Optional[str] = None
) -> None:
    """
    Setup centralized logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON formatting
        log_file: Optional log file path
    """
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
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': level,
                'formatter': 'json' if use_json else 'detailed',
                'filters': ['correlation'],
                'stream': 'ext://sys.stdout'
            }
        },
        'loggers': {
            # Application loggers
            'app': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            'app.services': {
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
            }
        },
        'root': {
            'level': level,
            'handlers': ['console']
        }
    }
    
    # Add file handler if specified
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': level,
            'formatter': 'json' if use_json else 'detailed',
            'filters': ['correlation'],
            'filename': log_file,
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf8'
        }
        
        # Add file handler to all loggers
        for logger_config in config['loggers'].values():
            logger_config['handlers'].append('file')
        config['root']['handlers'].append('file')
    
    logging.config.dictConfig(config)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"app.{name}")

# Convenience function for services
def get_service_logger(service_name: str) -> logging.Logger:
    """Get a logger for a service."""
    return logging.getLogger(f"app.services.{service_name}")