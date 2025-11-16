"""
Async Base Agent Implementation
Provides async/await support for all agents
"""

import asyncio
from abc import abstractmethod
from typing import Optional
from datetime import datetime

from .base_agent import BaseAgent, BaseAgentInput, BaseAgentOutput, AgentCapabilities, AgentStatus, ConfidenceLevel


class AsyncBaseAgent(BaseAgent):
    """
    Async version of BaseAgent.
    Provides non-blocking execution for better performance in orchestration.
    """

    def __init__(self, name: str, capabilities: AgentCapabilities):
        super().__init__(name, capabilities)

    @abstractmethod
    async def execute_async(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """
        Execute the agent logic asynchronously.
        Must be implemented by subclasses.

        Args:
            input_data: Input data conforming to BaseAgentInput schema

        Returns:
            BaseAgentOutput with findings and analysis results
        """
        raise NotImplementedError("Subclasses must implement execute_async()")

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """
        Synchronous wrapper for backward compatibility.
        Runs async execution in event loop.

        Args:
            input_data: Input data conforming to BaseAgentInput schema

        Returns:
            BaseAgentOutput with findings and analysis results
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create task
                # This is for nested async calls
                return asyncio.create_task(self.execute_async(input_data))
            else:
                # Run in existing loop
                return loop.run_until_complete(self.execute_async(input_data))
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(self.execute_async(input_data))

    async def execute_with_timeout(
        self,
        input_data: BaseAgentInput,
        timeout_seconds: Optional[int] = None
    ) -> BaseAgentOutput:
        """
        Execute agent with timeout.

        Args:
            input_data: Input data
            timeout_seconds: Timeout in seconds (default from config)

        Returns:
            BaseAgentOutput or timeout error

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
        """
        if timeout_seconds is None:
            from config.settings import get_settings
            timeout_seconds = get_settings().default_timeout_seconds

        try:
            return await asyncio.wait_for(
                self.execute_async(input_data),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                findings=[],
                summary=f"Execution exceeded {timeout_seconds}s timeout",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Increase timeout", "Reduce input data size"],
                errors=[f"TimeoutError: Execution exceeded {timeout_seconds}s"],
                execution_time_ms=timeout_seconds * 1000
            )

    async def execute_with_retry(
        self,
        input_data: BaseAgentInput,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None
    ) -> BaseAgentOutput:
        """
        Execute agent with exponential backoff retry logic.

        Args:
            input_data: Input data
            max_retries: Maximum retry attempts
            backoff_base: Base for exponential backoff (seconds)

        Returns:
            BaseAgentOutput
        """
        if max_retries is None:
            from config.settings import get_settings
            max_retries = get_settings().max_retries

        if backoff_base is None:
            from config.settings import get_settings
            backoff_base = get_settings().retry_backoff_base

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await self.execute_async(input_data)

            except Exception as e:
                last_error = e

                # Don't retry on last attempt
                if attempt == max_retries:
                    break

                # Exponential backoff
                wait_time = backoff_base ** attempt
                await asyncio.sleep(wait_time)

        # All retries failed
        return BaseAgentOutput(
            agent_name=self.name,
            status=AgentStatus.FAILED,
            findings=[],
            summary=f"Failed after {max_retries + 1} attempts: {str(last_error)}",
            confidence=ConfidenceLevel.UNCERTAIN,
            next_steps=["Review error logs", "Check input data", "Verify agent configuration"],
            errors=[str(last_error)],
            execution_time_ms=0
        )
