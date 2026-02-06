"""
Policy loading utilities.
"""

from typing import Dict, Any, List

from functools import lru_cache
import yaml

from app.schemas.change_type_rule import ChangeTypeRule
import os

DEFAULT_POLICY_PATH = os.path.join(os.path.dirname(__file__), "policy.yaml")


@lru_cache(maxsize=1)
def load_policy(policy_path: str) -> Dict[str, Any]:
    """
    Load policy from YAML file.

    Args:
        policy_path: Path to the policy YAML file.

    Returns:
        Dictionary containing the policy.
    """
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    return policy


def get_change_rules(
    policy: Dict[str, Any], excluded_risk_levels: List[str] = None
) -> List[ChangeTypeRule]:
    """
    Extract change type rules from policy, excluding specific risk levels.

    Args:
        policy: The policy dictionary.
        excluded_risk_levels: List of risk levels to exclude. Defaults to ["LOW"].

    Returns:
        List of ChangeTypeRule objects.
    """
    if excluded_risk_levels is None:
        excluded_risk_levels = ["LOW"]

    all_rules = []
    risk_levels = policy.get("risk_levels", {})

    for level_name, level_data in risk_levels.items():
        if level_name in excluded_risk_levels:
            continue

        change_types = level_data.get("change_types", {})
        for rule_id, rule_data in change_types.items():
            try:
                # Inject the key as 'id' and level_name as 'risk_level'
                all_rules.append(
                    ChangeTypeRule(id=rule_id, risk_level=level_name, **rule_data)
                )
            except Exception as e:
                print(f"Error parsing rule '{rule_id}' in level {level_name}: {e}")

    return all_rules


def get_risk_priority(policy: Dict[str, Any]) -> Dict[str, int]:
    """
    Derive risk level priority from the order in the policy YAML.
    Earlier keys = lower priority, later keys = higher priority.

    Args:
        policy: The policy dictionary.

    Returns:
        Dict mapping risk level names to priority integers.
    """
    risk_levels = list(policy.get("risk_levels", {}).keys())
    return {level: i for i, level in enumerate(risk_levels)}


@lru_cache(maxsize=1)
def get_default_risk_priority() -> Dict[str, int]:
    """
    Get risk priorities from the default policy file.
    """
    try:
        policy = load_policy(DEFAULT_POLICY_PATH)
        return get_risk_priority(policy)
    except Exception as e:
        print(f"Warning: Could not load default policy for priorities: {e}")
        # Fallback to some defaults if file missing
        return {"LOW": 0, "UNKNOWN": 1, "HIGH": 2}
