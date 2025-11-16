"""
Structured logging with OpenTelemetry support
"""

import logging
import sys
from typing import Any, Dict
from datetime import datetime


class StructuredLogger:
    """Structured logger with JSON output"""

    def __init__(self, name: str, level: str = "INFO"):
        self.name = name
        self.level = getattr(logging, level.upper())
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger with JSON formatter"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(self.level)

            # Use JSON formatter
            from utils.json_formatter import JSONFormatter
            formatter = JSONFormatter()
            handler.setFormatter(formatter)

            logger.addHandler(handler)

        return logger

    def _log(self, level: str, message: str, **kwargs):
        """Internal log method"""
        extra = {
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        getattr(self._logger, level)(message, extra={"fields": extra})

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log("error", message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log("debug", message, **kwargs)


class JSONFormatter(logging.Formatter):
    """JSON log formatter"""

    def format(self, record: logging.LogRecord) -> str:
        """Format record as JSON"""
        import json

        log_dict = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "fields"):
            log_dict.update(record.fields)

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_dict)


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    from config.settings import get_settings
    settings = get_settings()
    return StructuredLogger(name, level=settings.log_level)
