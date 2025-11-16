"""
Base Agent Schema
Defines the standard interface for all ADAPT diagnostic agents.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    """Agent execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    """Confidence levels for agent findings"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class BaseAgentInput(BaseModel):
    """Standard input schema for all agents"""
    context: Dict[str, Any] = Field(..., description="Contextual information for the agent")
    parameters: Optional[Dict[str, Any]] = Field(default={}, description="Agent-specific parameters")
    metadata: Optional[Dict[str, str]] = Field(default={}, description="Additional metadata")

    class Config:
        extra = "allow"


class Finding(BaseModel):
    """A single finding from an agent"""
    type: str = Field(..., description="Type of finding (anomaly, correlation, pattern, etc.)")
    description: str = Field(..., description="Human-readable description")
    confidence: ConfidenceLevel = Field(..., description="Confidence level")
    evidence: List[str] = Field(default=[], description="Supporting evidence")
    severity: Optional[str] = Field(None, description="Severity level if applicable")
    timestamp: Optional[datetime] = Field(None, description="When the finding was detected")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")


class BaseAgentOutput(BaseModel):
    """Standard output schema for all agents"""
    agent_name: str = Field(..., description="Name of the agent that produced this output")
    status: AgentStatus = Field(..., description="Execution status")
    findings: List[Finding] = Field(default=[], description="List of findings")
    summary: str = Field(..., description="High-level summary of results")
    reasoning: Optional[str] = Field(None, description="Agent's reasoning process (if not suppressed)")
    confidence: ConfidenceLevel = Field(..., description="Overall confidence in the output")
    next_steps: List[str] = Field(default=[], description="Recommended next steps")
    errors: List[str] = Field(default=[], description="Any errors encountered")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    execution_time_ms: Optional[float] = Field(None, description="Execution time in milliseconds")


class AgentCapabilities(BaseModel):
    """Defines what an agent can do"""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    dependencies: List[str] = []
    supports_streaming: bool = False
    max_context_tokens: Optional[int] = None


class BaseAgent:
    """
    Base class for all ADAPT agents.
    Provides common functionality and enforces standard interface.
    """

    def __init__(self, name: str, capabilities: AgentCapabilities):
        self.name = name
        self.capabilities = capabilities

    def validate_input(self, input_data: BaseAgentInput) -> bool:
        """Validate input data against schema"""
        # Implemented by subclasses
        return True

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """
        Execute the agent logic.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def get_capabilities(self) -> AgentCapabilities:
        """Return agent capabilities"""
        return self.capabilities
