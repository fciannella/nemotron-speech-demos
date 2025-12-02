import os
import json
from typing import Any, Dict

from langchain_core.tools import tool

# Robust logic import that avoids cross-module leakage during hot reloads
try:
    from . import logic as telco_logic  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _logic_path = os.path.join(_dir, "logic.py")
    _spec = _ilu.spec_from_file_location("telco_agent_logic", _logic_path)
    telco_logic = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(telco_logic)  # type: ignore


# --- Identity tools ---

@tool
def start_login_tool(session_id: str, msisdn: str) -> str:
    """Send a one-time code via SMS to the given mobile number. Returns masked destination and status (JSON)."""
    return json.dumps(telco_logic.start_login(session_id, msisdn))


@tool
def verify_login_tool(session_id: str, msisdn: str, otp: str) -> str:
    """Verify the one-time code sent to the user's phone. Returns {verified, session_id, msisdn}."""
    return json.dumps(telco_logic.verify_login(session_id, msisdn, otp))


# --- Customer/package tools ---

@tool
def get_current_package_tool(msisdn: str) -> str:
    """Get the customer's current package, contract status, and addons (JSON)."""
    return json.dumps(telco_logic.get_current_package(msisdn))


@tool
def get_data_balance_tool(msisdn: str) -> str:
    """Get the customer's current month data usage and remaining allowance (JSON)."""
    return json.dumps(telco_logic.get_data_balance(msisdn))


@tool
def list_available_packages_tool() -> str:
    """List all available mobile packages with fees and features (JSON array)."""
    return json.dumps(telco_logic.list_available_packages())


@tool
def recommend_packages_tool(msisdn: str, preferences_json: str | None = None) -> str:
    """Recommend up to 3 packages based on the customer's usage and optional preferences JSON."""
    prefs: Dict[str, Any] = {}
    try:
        if isinstance(preferences_json, str) and preferences_json.strip():
            prefs = json.loads(preferences_json)
    except Exception:
        prefs = {}
    return json.dumps(telco_logic.recommend_packages(msisdn, prefs))


@tool
def get_roaming_info_tool(msisdn: str, country_code: str) -> str:
    """Get roaming pricing and available passes for a country; indicates if included by current package (JSON)."""
    return json.dumps(telco_logic.get_roaming_info(msisdn, country_code))


@tool
def close_contract_tool(msisdn: str, confirm: bool = False) -> str:
    """Close the customer's contract. Use confirm=true only after explicit user confirmation. Returns summary (JSON)."""
    return json.dumps(telco_logic.close_contract(msisdn, bool(confirm)))


# --- Extended tools ---

@tool
def list_addons_tool(msisdn: str) -> str:
    """List customer's active addons (e.g., roaming passes)."""
    return json.dumps(telco_logic.list_addons(msisdn))


@tool
def purchase_roaming_pass_tool(msisdn: str, country_code: str, pass_id: str) -> str:
    """Purchase a roaming pass for a country by pass_id. Returns the added addon (JSON)."""
    return json.dumps(telco_logic.purchase_roaming_pass(msisdn, country_code, pass_id))


@tool
def change_package_tool(msisdn: str, package_id: str, effective: str = "next_cycle") -> str:
    """Change customer's package now or next_cycle. Returns status summary (JSON)."""
    return json.dumps(telco_logic.change_package(msisdn, package_id, effective))


@tool
def get_billing_summary_tool(msisdn: str) -> str:
    """Get billing summary including monthly fee and last bill amount (JSON)."""
    return json.dumps(telco_logic.get_billing_summary(msisdn))


@tool
def set_data_alerts_tool(msisdn: str, threshold_percent: int | None = None, threshold_gb: float | None = None) -> str:
    """Set data usage alerts by percent and/or GB. Returns updated alert settings (JSON)."""
    return json.dumps(telco_logic.set_data_alerts(msisdn, threshold_percent, threshold_gb))

