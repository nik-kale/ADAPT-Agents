"""
ADAPT-Agents Schema Package
Provides standard schemas and base classes for all diagnostic agents.
"""

from .base_agent import (
    BaseAgent,
    BaseAgentInput,
    BaseAgentOutput,
    Finding,
    AgentStatus,
    ConfidenceLevel,
    AgentCapabilities
)

__all__ = [
    'BaseAgent',
    'BaseAgentInput',
    'BaseAgentOutput',
    'Finding',
    'AgentStatus',
    'ConfidenceLevel',
    'AgentCapabilities'
]
