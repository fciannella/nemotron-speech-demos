import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict

from langchain_core.tools import tool

try:
    from .logic import (
        get_accounts,
        get_profile,
        find_customer_by_name,
        list_transactions,
        get_fee_schedule,
        detect_fees as detect_fees_logic,
        explain_fee as explain_fee_logic,
        check_dispute_eligibility as check_dispute_eligibility_logic,
        create_dispute_case,
        authenticate_user,
        evaluate_upgrade_savings,
    )
except ImportError:
    # Hot-reload/dev server may import without package context
    sys.path.append(os.path.dirname(__file__))
    from logic import (  # type: ignore
        get_accounts,
        get_profile,
        find_customer_by_name,
        list_transactions,
        get_fee_schedule,
        detect_fees as detect_fees_logic,
        explain_fee as explain_fee_logic,
        check_dispute_eligibility as check_dispute_eligibility_logic,
        create_dispute_case,
        authenticate_user,
        evaluate_upgrade_savings,
    )


@tool
def list_accounts(customer_id: str) -> str:
    """List customer's accounts with masked numbers for identification. Returns JSON string."""
    accts = get_accounts(customer_id)
    return json.dumps(accts)


@tool
def get_customer_profile(customer_id: str) -> str:
    """Fetch basic customer profile for greetings/ID checks (first/last name, dob, secret question). Returns JSON string."""
    return json.dumps(get_profile(customer_id))


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
def fetch_activity(account_id: str, start_date: str, end_date: str) -> str:
    """Fetch transactions for an account over a date range. Returns JSON string."""
    txns = list_transactions(account_id, start_date, end_date)
    return json.dumps(txns)


@tool
def detect_fees(account_id: str, product_type: str, start_date: str, end_date: str) -> str:
    """Detect fee events on an account using its product fee schedule. Returns JSON string with either `events` or an `error`.

    If the date range is invalid, in the future, or yields no fees, return a structured error so the agent can ask for clarification.
    """
    now = datetime.utcnow()
    def _parse(d: str) -> datetime | None:
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return None
    sd = _parse(start_date)
    ed = _parse(end_date)
    if sd is None or ed is None:
        return json.dumps({"error": "invalid_date", "message": "The provided date(s) are invalid. Please provide a valid date or range."})
    if ed < sd:
        return json.dumps({"error": "invalid_range", "message": "The end date is before the start date. Please adjust the range."})
    if sd > now and ed > now:
        return json.dumps({"error": "future_range", "message": "The dates are in the future. Please provide past dates."})
    txns = list_transactions(account_id, sd.strftime("%Y-%m-%d"), ed.strftime("%Y-%m-%d"))
    sched = get_fee_schedule(product_type)
    events = detect_fees_logic(txns, sched)
    if not events:
        return json.dumps({"error": "no_fees", "message": "No fees found in that timeframe. Would you like to try a different date or a wider range (e.g., last 90 days)?"})
    return json.dumps({"events": events})


@tool
def explain_fee(fee_event_json: str) -> str:
    """Explain a single fee event in friendly tone. Input is JSON dict string."""
    fee_event = json.loads(fee_event_json)
    return explain_fee_logic(fee_event)


@tool
def check_dispute_eligibility(fee_event_json: str) -> str:
    """Check if fee is eligible for courtesy refund. Input is JSON dict string; returns JSON."""
    fee_event = json.loads(fee_event_json)
    return json.dumps(check_dispute_eligibility_logic(fee_event))


@tool
def create_dispute(fee_event_json: str) -> str:
    """Create a dispute (courtesy refund) for a fee event. Input is JSON dict string; returns JSON."""
    fee_event = json.loads(fee_event_json)
    return json.dumps(create_dispute_case(fee_event, idempotency_key=fee_event.get("id", "fee")))


@tool
def verify_identity(session_id: str, name: str | None = None, dob_yyyy_mm_dd: str | None = None, last4: str | None = None, secret_answer: str | None = None, customer_id: str | None = None) -> str:
    """Verify user identity before accessing accounts. Provide any of: name, dob (YYYY-MM-DD), last4, secret_answer. Returns JSON with verified flag, needed fields, and optional secret question."""
    res = authenticate_user(session_id, name, dob_yyyy_mm_dd, last4, secret_answer, customer_id)
    return json.dumps(res)


@tool
def parse_date_range(text: str) -> str:
    """Parse a natural-language date or range into ISO start_date/end_date.

    Supports:
    - "from YYYY-MM-DD to YYYY-MM-DD"
    - "last N months"
    - single date (expands to ±15 days)

    Returns {start_date,end_date}. If the input is invalid or clearly future-only, returns {error, message}.
    Defaults to last 12 months if no date is found.
    """
    now = datetime.utcnow()
    tl = (text or "").lower()
    # explicit range
    m = re.search(r"from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", tl)
    if m:
        try:
            sd = datetime.strptime(m.group(1), "%Y-%m-%d")
            ed = datetime.strptime(m.group(2), "%Y-%m-%d")
            if ed < sd:
                return json.dumps({"error": "invalid_range", "message": "End date is before start date."})
            if sd > now and ed > now:
                return json.dumps({"error": "future_range", "message": "Dates are in the future."})
            return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})
        except Exception:
            return json.dumps({"error": "invalid_date", "message": "Please use valid dates (YYYY-MM-DD)."})
    # last N months
    m = re.search(r"(last|past)\s+(\d{1,2})\s+months?", tl)
    if m:
        n = int(m.group(2))
        ed = now
        sd = ed - timedelta(days=30 * max(1, n))
        return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})
    # single ISO date
    m = re.search(r"(\d{4}-\d{2}-\d{2})", tl)
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d")
            if d > now:
                return json.dumps({"error": "future_date", "message": "The date is in the future."})
            sd = d - timedelta(days=15)
            ed = d + timedelta(days=15)
            return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})
        except Exception:
            return json.dumps({"error": "invalid_date", "message": "Please provide a valid date (YYYY-MM-DD)."})

    # natural language month names, e.g., "august the 11th 2025", "Aug 11, 2025", "11th of August 2025"
    try:
        # normalize ordinals like 11th -> 11
        norm = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\\1", tl)
        norm = norm.replace(",", " ").replace(" of ", " ")
        MONTHS = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        # pattern: month day year
        m = re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\s+(\d{4})\b", norm)
        if m:
            month = MONTHS[m.group(1)]
            day = int(m.group(2))
            year = int(m.group(3))
            d = datetime(year, month, day)
            if d > now:
                return json.dumps({"error": "future_date", "message": "The date is in the future."})
            sd = d - timedelta(days=15)
            ed = d + timedelta(days=15)
            return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})
        # pattern: day month year
        m = re.search(r"\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b", norm)
        if m:
            day = int(m.group(1))
            month = MONTHS[m.group(2)]
            year = int(m.group(3))
            d = datetime(year, month, day)
            if d > now:
                return json.dumps({"error": "future_date", "message": "The date is in the future."})
            sd = d - timedelta(days=15)
            ed = d + timedelta(days=15)
            return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})
    except Exception:
        pass
    # No date found -> default safe window
    ed = now
    sd = ed - timedelta(days=365)
    return json.dumps({"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")})


@tool
def check_upgrade_options(product_type: str, fee_events_json: str) -> str:
    """After the fee has been explained and any refund/relief is handled, propose a single upgrade package.

    Given a product_type (e.g., CHK/SAV) and recent fee events (JSON array), return package options ranked by estimated net benefit. The agent should proactively offer the top option at the end of the interaction: if net benefit > 0, emphasize savings; otherwise, frame as optional convenience.
    """
    try:
        events = json.loads(fee_events_json)
        if not isinstance(events, list):
            events = []
    except Exception:
        events = []
    recs = evaluate_upgrade_savings(product_type, events)
    return json.dumps(recs)


@tool
def find_customer(first_name: str, last_name: str) -> str:
    """Find a customer_id by first and last name (exact match, case-insensitive). Returns JSON with customer_id or {}."""
    return json.dumps(find_customer_by_name(first_name, last_name))


