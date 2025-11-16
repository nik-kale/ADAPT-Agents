"""
ADAPT-Agents Setup
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="adapt-agents",
    version="3.0.0",
    description="Production-Ready Modular Diagnostic Agents Library with Async/Await, LLM Integration, and Enterprise Features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ADAPT-Agents Contributors",
    author_email="",
    url="https://github.com/yourusername/ADAPT-Agents",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
    ],
    extras_require={
        "full": requirements,
        "api": [
            "fastapi>=0.109.0",
            "uvicorn[standard]>=0.27.0",
            "httpx>=0.26.0",
        ],
        "llm": [
            "openai>=1.0.0",
            "anthropic>=0.18.0",
            "tiktoken>=0.5.0",
        ],
        "cache": [
            "aioredis>=2.0.1",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
            "opentelemetry-api>=1.22.0",
            "opentelemetry-sdk>=1.22.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.12.0",
            "ruff>=0.1.0",
            "mypy>=1.8.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.5.0",
            "mkdocstrings[python]>=0.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "adapt-agents=cli.main:cli",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Monitoring",
    ],
    keywords="rca diagnostics agents llm observability",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/ADAPT-Agents/issues",
        "Source": "https://github.com/yourusername/ADAPT-Agents",
        "Documentation": "https://adapt-agents.readthedocs.io",
    },
)
