# Contributing to ADAPT-Agents

Thank you for your interest in contributing to ADAPT-Agents! This document provides guidelines for contributing to the project.

## 🚀 Quick Start

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/ADAPT-Agents.git
cd ADAPT-Agents
```

### 2. Set Up Development Environment

```bash
# Install with all development dependencies
pip install -e ".[dev,full]"

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

## 📋 Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_log_analyzer_agent.py -v
```

### Code Quality

All code must pass our quality checks:

```bash
# Format code
black .

# Sort imports
isort .

# Lint
flake8 .

# Type check
mypy .

# Or run all checks
pre-commit run --all-files
```

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

- **black**: Code formatting (100 char line length)
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning

## 🎯 Contribution Guidelines

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Max line length: 100 characters
- Use docstrings for all public methods

### Commit Messages

Follow conventional commits:

```
feat: add new agent for network analysis
fix: resolve caching bug in LogAnalyzerAgent
docs: update README with v3.0 features
test: add unit tests for async orchestrator
```

### Pull Request Process

1. **Update tests**: Add/update tests for your changes
2. **Update documentation**: Update README, docstrings, and docs/
3. **Run quality checks**: Ensure all pre-commit hooks pass
4. **Update CHANGELOG**: Add entry under "Unreleased"
5. **Create PR**: Use the PR template and provide clear description

## 🧪 Testing Guidelines

### Unit Tests

- Test individual agent logic
- Mock external dependencies (LLM, cache, etc.)
- Aim for 80%+ coverage

Example:
```python
import pytest
from agents import LogAnalyzerAgent

@pytest.mark.asyncio
async def test_log_analyzer_basic():
    agent = LogAnalyzerAgent(use_llm=False)
    result = await agent.execute_async(input_data)
    assert result.status == AgentStatus.COMPLETED
```

### Integration Tests

- Test agent orchestration
- Test end-to-end workflows
- Use real (but small) test data

## 📝 Documentation

### Docstrings

Use Google-style docstrings:

```python
async def execute_async(self, input_data: BaseAgentInput) -> BaseAgentOutput:
    """
    Execute agent analysis asynchronously.

    Args:
        input_data: Input data containing context and parameters

    Returns:
        BaseAgentOutput with findings and analysis results

    Raises:
        ValueError: If input data is invalid
    """
```

### README Updates

When adding features:
1. Update feature list
2. Add usage example
3. Update configuration section if needed

## 🐛 Bug Reports

Include:
- ADAPT-Agents version
- Python version
- Minimal reproduction example
- Expected vs actual behavior
- Full error traceback

## 💡 Feature Requests

Include:
- Use case description
- Proposed API/interface
- Examples of how it would work
- Why existing features don't solve this

## 🔒 Security

Report security vulnerabilities to: security@adapt-agents.io (or create private security advisory on GitHub)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## ❓ Questions?

- Open a GitHub Discussion
- Join our community chat
- Check existing issues and PRs

Thank you for contributing to ADAPT-Agents! 🎉
