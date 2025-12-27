"""
Configuration management for ADAPT-Agents
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, Dict, Any
from pathlib import Path
import json


class AgentSettings(BaseSettings):
    """Global settings for ADAPT-Agents"""

    # === Execution Settings ===
    default_timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    enable_async: bool = True

    # === Agent-Specific Settings ===
    log_analyzer_max_findings: int = 10
    log_analyzer_confidence_threshold: float = 0.7

    metrics_analyzer_anomaly_threshold: float = 3.0
    metrics_analyzer_correlation_min: float = 0.7
    metrics_analyzer_min_data_points: int = 10

    change_correlator_window_minutes: int = 60
    change_correlator_risk_threshold: int = 40

    topology_min_confidence: float = 0.7

    hypothesis_max_hypotheses: int = 5
    hypothesis_min_evidence_sources: int = 2

    remediation_prioritize_speed: bool = True

    # === LLM Settings ===
    llm_provider: str = "openai"  # openai, anthropic, azure, bedrock
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4000
    llm_timeout_seconds: int = 60

    # === Caching Settings ===
    enable_caching: bool = True
    cache_backend: str = "memory"  # memory, redis
    cache_redis_url: Optional[str] = "redis://localhost:6379"
    cache_ttl_seconds: int = 300

    # === Observability Settings ===
    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"
    log_format: str = "json"  # json, text

    # === OpenTelemetry Settings ===
    otel_endpoint: Optional[str] = None
    otel_service_name: str = "adapt-agents"

    # === Metrics Settings ===
    metrics_port: int = 9090
    metrics_enabled: bool = True

    # === API Settings ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_cors_origins: list = ["*"]

    # === Security Settings ===
    enable_pii_filtering: bool = True
    enable_audit_logging: bool = False
    audit_log_path: Optional[str] = None
    
    # API Key Management
    api_keys: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    
    @field_validator('api_keys', mode='before')
    @classmethod
    def parse_api_keys(cls, v):
        """Parse API keys from JSON string or dict"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v or {}

    # === Performance Settings ===
    max_parallel_agents: int = 10
    agent_pool_size: int = 5
    
    # === Data Retention Settings ===
    data_retention_days: int = 90
    cleanup_batch_size: int = 100
    enable_auto_cleanup: bool = True
    cleanup_schedule_hours: int = 24  # Run cleanup every N hours

    class Config:
        env_file = ".env"
        env_prefix = "ADAPT_"
        case_sensitive = False


class LogAnalyzerConfig(BaseSettings):
    """LogAnalyzer-specific configuration"""
    max_findings: int = 10
    confidence_threshold: float = 0.7
    error_grouping_similarity: float = 0.8
    cascade_detection_enabled: bool = True
    temporal_window_minutes: int = 5

    class Config:
        env_prefix = "ADAPT_LOG_ANALYZER_"


class MetricsAnalyzerConfig(BaseSettings):
    """MetricsAnalyzer-specific configuration"""
    anomaly_threshold: float = 3.0
    correlation_min: float = 0.7
    min_data_points: int = 10
    threshold_cpu: float = 80.0
    threshold_memory: float = 90.0
    threshold_disk: float = 85.0

    class Config:
        env_prefix = "ADAPT_METRICS_ANALYZER_"


# Singleton instance
_settings: Optional[AgentSettings] = None


def get_settings() -> AgentSettings:
    """Get global settings instance"""
    global _settings
    if _settings is None:
        _settings = AgentSettings()
    return _settings


def load_config_from_file(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    import yaml

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}
