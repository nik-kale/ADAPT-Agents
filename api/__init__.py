"""API Package"""

try:
    from .server import app
except ImportError:
    app = None

__all__ = ['app'] if app else []
