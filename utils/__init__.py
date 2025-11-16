"""Utilities Package"""

from .logging import get_logger
from .caching import get_cache, AgentCache

try:
    from .metrics import record_execution_metrics, start_metrics_server
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

__all__ = ['get_logger', 'get_cache', 'AgentCache']

if METRICS_AVAILABLE:
    __all__.extend(['record_execution_metrics', 'start_metrics_server'])
