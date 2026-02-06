"""
Risk priority utilities.

Pure module — loads YAML directly, no loader.py or service imports.
"""

from functools import lru_cache
from typing import Dict
import os
import yaml


DEFAULT_POLICY_PATH = os.path.join(os.path.dirname(__file__), "policy.yaml")


@lru_cache(maxsize=1)
def get_default_risk_priority() -> Dict[str, int]:
    """
    Get risk priorities from the default policy file.

    Priority is derived from the order of keys in the YAML.
    Earlier keys = lower priority, later keys = higher priority.

    Returns:
        Dict mapping risk level names to priority integers.
    """
    try:
        with open(DEFAULT_POLICY_PATH, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
        risk_levels = list(policy.get("risk_levels", {}).keys())
        return {level: i for i, level in enumerate(risk_levels)}
    except Exception as e:
        print(f"Warning: Could not load default policy for priorities: {e}")
        # Fallback to some defaults if file missing
        return {"LOW": 0, "UNKNOWN": 1, "HIGH": 2}
