"""
Utility functions for handling YAML files.
"""

from typing import Dict, Any, List

import yaml

from app.services.change_management.utils.schemas import ChangeTypeRule


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
                # Inject the key as 'id' since we moved to dict-based structure
                all_rules.append(ChangeTypeRule(id=rule_id, **rule_data))
            except Exception as e:
                print(f"Error parsing rule '{rule_id}' in level {level_name}: {e}")

    return all_rules
