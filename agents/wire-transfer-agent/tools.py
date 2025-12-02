import os
import sys
import json
from typing import Any, Dict

from langchain_core.tools import tool

# Robust logic import to avoid crossing into other agent modules during hot reloads
try:
    from . import logic as wt_logic  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _logic_path = os.path.join(_dir, "logic.py")
    _spec = _ilu.spec_from_file_location("wire_transfer_agent_logic", _logic_path)
    wt_logic = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(wt_logic)  # type: ignore

get_accounts = wt_logic.get_accounts
get_profile = wt_logic.get_profile
find_customer_by_name = wt_logic.find_customer_by_name
find_customer_by_full_name = getattr(wt_logic, "find_customer_by_full_name", wt_logic.find_customer_by_name)
get_account_balance = wt_logic.get_account_balance
get_exchange_rate = wt_logic.get_exchange_rate
calculate_wire_fee = wt_logic.calculate_wire_fee
check_wire_limits = wt_logic.check_wire_limits
get_cutoff_and_eta = wt_logic.get_cutoff_and_eta
get_country_requirements = wt_logic.get_country_requirements
validate_beneficiary = wt_logic.validate_beneficiary
save_beneficiary = wt_logic.save_beneficiary
generate_otp = wt_logic.generate_otp
verify_otp = wt_logic.verify_otp
authenticate_user_wire = wt_logic.authenticate_user_wire
quote_wire = wt_logic.quote_wire
wire_transfer_domestic_logic = wt_logic.wire_transfer_domestic
wire_transfer_international_logic = wt_logic.wire_transfer_international


@tool
def list_accounts(customer_id: str) -> str:
    """List customer's accounts with masked numbers, balances, currency, and wire eligibility. Returns JSON string."""
    return json.dumps(get_accounts(customer_id))


@tool
def get_customer_profile(customer_id: str) -> str:
    """Fetch basic customer profile (full_name, dob, ssn_last4, secret question). Returns JSON string."""
    return json.dumps(get_profile(customer_id))


@tool
def find_customer(first_name: str | None = None, last_name: str | None = None, full_name: str | None = None) -> str:
    """Find a customer_id by name. Prefer full_name; otherwise use first and last name. Returns JSON with customer_id or {}."""
    if isinstance(full_name, str) and full_name.strip():
        return json.dumps(find_customer_by_full_name(full_name))
    return json.dumps(find_customer_by_name(first_name or "", last_name or ""))


@tool
def find_account_by_last4(customer_id: str, last4: str) -> str:
    """Find a customer's account by last 4 digits. Returns JSON with account or {} if not found."""
    accts = get_accounts(customer_id)
    for a in accts:
        num = str(a.get("account_number") or "")
        if num.endswith(str(last4)):
            return json.dumps(a)
    return json.dumps({})


@tool
def verify_identity(session_id: str, customer_id: str | None = None, full_name: str | None = None, dob_yyyy_mm_dd: str | None = None, ssn_last4: str | None = None, secret_answer: str | None = None) -> str:
    """Verify user identity before wires. Provide any of: full_name, dob (YYYY-MM-DD), ssn_last4, secret_answer. Returns JSON with verified flag, needed fields, and optional secret question."""
    res = authenticate_user_wire(session_id, customer_id, full_name, dob_yyyy_mm_dd, ssn_last4, secret_answer)
    return json.dumps(res)


@tool
def get_account_balance_tool(account_id: str) -> str:
    """Get balance, currency, and wire limits for an account. Returns JSON."""
    return json.dumps(get_account_balance(account_id))


@tool
def get_exchange_rate_tool(from_currency: str, to_currency: str, amount: float) -> str:
    """Get exchange rate and converted amount for a given amount. Returns JSON."""
    return json.dumps(get_exchange_rate(from_currency, to_currency, amount))


@tool
def convert_currency_tool(from_currency: str, to_currency: str, amount: float) -> str:
    """Convert an arbitrary amount between currencies using banking FX rates. Returns JSON with rate and converted amount."""
    result = get_exchange_rate(from_currency, to_currency, amount)
    # Add helper text for the agent
    payload: Dict[str, Any] = {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "requested_amount": amount,
        **result,
    }
    return json.dumps(payload)


@tool
def calculate_wire_fee_tool(kind: str, amount: float, from_currency: str, to_currency: str, payer: str) -> str:
    """Calculate wire fee breakdown and who pays (OUR/SHA/BEN). Returns JSON."""
    return json.dumps(calculate_wire_fee(kind, amount, from_currency, to_currency, payer))


@tool
def check_wire_limits_tool(account_id: str, amount: float) -> str:
    """Check sufficient funds and daily wire limit on an account. Returns JSON."""
    return json.dumps(check_wire_limits(account_id, amount))


@tool
def get_cutoff_and_eta_tool(kind: str, country: str) -> str:
    """Get cutoff time and estimated arrival window by type and country. Returns JSON."""
    return json.dumps(get_cutoff_and_eta(kind, country))


@tool
def get_country_requirements_tool(country_code: str) -> str:
    """Get required beneficiary fields for a country. Returns JSON array."""
    return json.dumps(get_country_requirements(country_code))


@tool
def validate_beneficiary_tool(country_code: str, beneficiary_json: str) -> str:
    """Validate beneficiary fields for a given country. Input is JSON dict string; returns {ok, missing}."""
    try:
        beneficiary = json.loads(beneficiary_json)
    except Exception:
        beneficiary = {}
    return json.dumps(validate_beneficiary(country_code, beneficiary))


@tool
def save_beneficiary_tool(customer_id: str, beneficiary_json: str) -> str:
    """Save a beneficiary for future use. Input is JSON dict string; returns {beneficiary_id}."""
    try:
        beneficiary = json.loads(beneficiary_json)
    except Exception:
        beneficiary = {}
    return json.dumps(save_beneficiary(customer_id, beneficiary))


@tool
def quote_wire_tool(kind: str, from_account_id: str, beneficiary_json: str, amount: float, from_currency: str, to_currency: str, payer: str) -> str:
    """Create a wire quote including FX, fees, limits, sanctions, eta; returns JSON with quote_id and totals."""
    try:
        beneficiary = json.loads(beneficiary_json)
    except Exception:
        beneficiary = {}
    return json.dumps(quote_wire(kind, from_account_id, beneficiary, amount, from_currency, to_currency, payer))


@tool
def generate_otp_tool(customer_id: str) -> str:
    """Generate a one-time passcode for wire authorization. Returns masked destination info."""
    return json.dumps(generate_otp(customer_id))


@tool
def verify_otp_tool(customer_id: str, otp: str) -> str:
    """Verify the one-time passcode for wire authorization. Returns {verified}."""
    return json.dumps(verify_otp(customer_id, otp))


@tool
def wire_transfer_domestic(quote_id: str, otp: str) -> str:
    """Execute a domestic wire with a valid quote_id and OTP. Returns confirmation."""
    return json.dumps(wire_transfer_domestic_logic(quote_id, otp))


@tool
def wire_transfer_international(quote_id: str, otp: str) -> str:
    """Execute an international wire with a valid quote_id and OTP. Returns confirmation."""
    return json.dumps(wire_transfer_international_logic(quote_id, otp))


