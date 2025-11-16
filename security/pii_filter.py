"""
PII (Personally Identifiable Information) Filtering
Removes sensitive data from logs before analysis
"""

import re
from typing import List, Dict, Pattern


class PIIFilter:
    """Filter PII from log messages"""

    # Common PII patterns
    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "api_key": r"\b[A-Za-z0-9]{32,}\b",
        "jwt": r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    }

    def __init__(self, patterns: Dict[str, str] = None):
        """
        Initialize PII filter

        Args:
            patterns: Custom PII patterns (overrides defaults)
        """
        self.patterns = patterns or self.PATTERNS
        self.compiled_patterns = {
            name: re.compile(pattern)
            for name, pattern in self.patterns.items()
        }

    def filter_text(self, text: str) -> str:
        """
        Filter PII from text

        Args:
            text: Text to filter

        Returns:
            Text with PII replaced with placeholders
        """
        filtered = text

        for pii_type, pattern in self.compiled_patterns.items():
            replacement = f"[REDACTED_{pii_type.upper()}]"
            filtered = pattern.sub(replacement, filtered)

        return filtered

    def filter_logs(self, logs: List[Dict]) -> List[Dict]:
        """
        Filter PII from log entries

        Args:
            logs: List of log dictionaries

        Returns:
            Logs with PII filtered from message field
        """
        filtered_logs = []

        for log in logs:
            filtered_log = log.copy()

            # Filter message field
            if "message" in filtered_log:
                filtered_log["message"] = self.filter_text(filtered_log["message"])

            # Filter any additional text fields
            for key in ["description", "error", "details"]:
                if key in filtered_log and isinstance(filtered_log[key], str):
                    filtered_log[key] = self.filter_text(filtered_log[key])

            filtered_logs.append(filtered_log)

        return filtered_logs

    def add_pattern(self, name: str, pattern: str):
        """
        Add custom PII pattern

        Args:
            name: Pattern name
            pattern: Regex pattern
        """
        self.patterns[name] = pattern
        self.compiled_patterns[name] = re.compile(pattern)
