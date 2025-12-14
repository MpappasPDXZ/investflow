"""
Lease Defaults Configuration
Centralized default values for lease generation, supporting state-specific rules.
"""
from decimal import Decimal
from typing import Any, Dict
import json


# Base lease defaults (apply to all states unless overridden)
BASE_LEASE_DEFAULTS = {
    "status": "draft",
    "lease_version": 1,
    "rent_due_day": 1,
    "rent_due_by_day": 5,
    "rent_due_by_time": "6pm",
    "auto_convert_month_to_month": False,
    "max_occupants": 3,
    "max_adults": 2,
    "max_children": True,
    "pets_allowed": True,
    "max_pets": 2,
    "pet_fee_one": Decimal("350.00"),
    "pet_fee_two": Decimal("700.00"),
    "parking_spaces": 2,
    "parking_small_vehicles": 2,
    "parking_large_trucks": 1,
    "front_door_keys": 1,
    "back_door_keys": 1,
    "key_replacement_fee": Decimal("100.00"),
    "lead_paint_disclosure": True,
    "early_termination_allowed": True,
    "early_termination_notice_days": 60,
    "early_termination_fee_months": 2,
    "garage_outlets_prohibited": False,
    "snow_removal_responsibility": "tenant",
    "is_active": True,
}


# State-specific defaults
STATE_LEASE_DEFAULTS = {
    "NE": {
        "deposit_return_days": 14,
        "late_fee_day_1_10": Decimal("75.00"),  # By 11th
        "late_fee_day_11": Decimal("150.00"),  # By 16th
        "late_fee_day_16": Decimal("225.00"),  # By 21st
        "late_fee_day_21": Decimal("300.00"),  # After 21st
        "nsf_fee": Decimal("60.00"),
        "methamphetamine_disclosure": False,  # Not required in NE
        "moveout_inspection_rights": False,  # Not required in NE
        "military_termination_days": None,  # Not specific law in NE
    },
    "MO": {
        "deposit_return_days": 30,
        # Missouri late fees must be reasonable and not exceed 10% of rent or actual costs
        "late_fee_day_1_10": Decimal("75.00"),  # Conservative approach
        "late_fee_day_11": Decimal("150.00"),
        "late_fee_day_16": None,  # Simplify for MO
        "late_fee_day_21": None,
        "nsf_fee": Decimal("50.00"),  # Conservative for MO
        "methamphetamine_disclosure": True,  # Required by MO law
        "moveout_inspection_rights": True,  # Tenant has right to inspection in MO
        "military_termination_days": 30,  # MO requires 30 days
    }
}


# Default move-out costs (can be customized per lease)
DEFAULT_MOVEOUT_COSTS = [
    {
        "item": "Hardwood Floor Cleaning",
        "description": "Fee if hardwood floors are not returned in clean condition (includes vacuuming)",
        "amount": Decimal("100.00"),
        "order": 1
    },
    {
        "item": "Trash Removal Fee",
        "description": "Fee if Tenant fails to remove all trash",
        "amount": Decimal("150.00"),
        "order": 2
    },
    {
        "item": "Heavy Cleaning",
        "description": "For dirty appliances, bathrooms, or excessive filth",
        "amount": Decimal("400.00"),
        "order": 3
    },
    {
        "item": "Wall Repairs",
        "description": "Flat fee for filling/sanding/painting nail holes or minor wall damage (up to 10 standard holes). Extensive damage billed at cost.",
        "amount": Decimal("150.00"),
        "order": 4
    }
]


def get_lease_defaults(state: str) -> Dict[str, Any]:
    """
    Get complete lease defaults for a specific state.
    Merges base defaults with state-specific overrides.
    
    Args:
        state: Two-letter state code ("NE" or "MO")
    
    Returns:
        Dictionary of default values
    """
    defaults = BASE_LEASE_DEFAULTS.copy()
    
    # Apply state-specific overrides
    if state in STATE_LEASE_DEFAULTS:
        defaults.update(STATE_LEASE_DEFAULTS[state])
    
    return defaults


def get_default_moveout_costs_json() -> str:
    """
    Get default move-out costs as JSON string.
    Converts Decimal to string for JSON serialization.
    
    Returns:
        JSON string of move-out cost items
    """
    costs = []
    for item in DEFAULT_MOVEOUT_COSTS:
        costs.append({
            "item": item["item"],
            "description": item["description"],
            "amount": str(item["amount"]),
            "order": item["order"]
        })
    return json.dumps(costs)


def apply_lease_defaults(lease_data: Dict[str, Any], state: str) -> Dict[str, Any]:
    """
    Apply default values to lease data.
    Only fills in missing values, doesn't override provided values.
    
    Args:
        lease_data: Partial lease data
        state: Two-letter state code
    
    Returns:
        Complete lease data with defaults applied
    """
    defaults = get_lease_defaults(state)
    
    # Apply defaults only where values are not provided
    for key, default_value in defaults.items():
        if key not in lease_data or lease_data[key] is None:
            lease_data[key] = default_value
    
    # Apply default move-out costs if not provided
    if "moveout_costs" not in lease_data or lease_data["moveout_costs"] is None:
        lease_data["moveout_costs"] = get_default_moveout_costs_json()
    
    # Calculate early termination fee if not provided
    if "early_termination_fee_amount" not in lease_data or lease_data["early_termination_fee_amount"] is None:
        if lease_data.get("early_termination_allowed") and lease_data.get("monthly_rent"):
            months = lease_data.get("early_termination_fee_months", 2)
            lease_data["early_termination_fee_amount"] = lease_data["monthly_rent"] * months
    
    return lease_data


