import os
import json
import uuid
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

try:
    from .prompts import EXPLAIN_FEE_PROMPT
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from prompts import EXPLAIN_FEE_PROMPT  # type: ignore


_FIXTURE_CACHE: Dict[str, Any] = {}
_DISPUTES_DB: Dict[str, Dict[str, Any]] = {}
_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "mock_data"


def _load_fixture(name: str) -> Any:
    if name in _FIXTURE_CACHE:
        return _FIXTURE_CACHE[name]
    p = _fixtures_dir() / name
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    _FIXTURE_CACHE[name] = data
    return data


def _parse_iso_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        return None


def _get_customer_blob(customer_id: str) -> Dict[str, Any]:
    data = _load_fixture("accounts.json")
    return dict(data.get("customers", {}).get(customer_id, {}))


def get_accounts(customer_id: str) -> List[Dict[str, Any]]:
    cust = _get_customer_blob(customer_id)
    if isinstance(cust, list):
        # backward-compat: old format was a list of accounts
        return list(cust)
    return list(cust.get("accounts", []))


def get_profile(customer_id: str) -> Dict[str, Any]:
    cust = _get_customer_blob(customer_id)
    if isinstance(cust, dict):
        return dict(cust.get("profile", {}))
    return {}


def find_customer_by_name(first_name: str, last_name: str) -> Dict[str, Any]:
    data = _load_fixture("accounts.json")
    customers = data.get("customers", {})
    fn = (first_name or "").strip().lower()
    ln = (last_name or "").strip().lower()
    for cid, blob in customers.items():
        prof = blob.get("profile") if isinstance(blob, dict) else None
        if isinstance(prof, dict):
            pfn = str(prof.get("first_name") or "").strip().lower()
            pln = str(prof.get("last_name") or "").strip().lower()
            if fn == pfn and ln == pln:
                return {"customer_id": cid, "profile": prof}
    return {}


def _normalize_dob(text: Optional[str]) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    t = text.strip().lower()
    # YYYY-MM-DD
    try:
        if len(t) >= 10 and t[4] == '-' and t[7] == '-':
            d = datetime.strptime(t[:10], "%Y-%m-%d")
            return d.strftime("%Y-%m-%d")
    except Exception:
        pass
    # Month name DD YYYY
    MONTHS = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    try:
        parts = t.replace(',', ' ').split()
        if len(parts) >= 3 and parts[0] in MONTHS:
            m = MONTHS[parts[0]]
            day = int(''.join(ch for ch in parts[1] if ch.isdigit()))
            year = int(parts[2])
            d = datetime(year, m, day)
            return d.strftime("%Y-%m-%d")
    except Exception:
        pass
    # DD/MM/YYYY or MM/DD/YYYY
    try:
        for sep in ('/', '-'):
            if sep in t and t.count(sep) == 2:
                a, b, c = t.split(sep)[:3]
                if len(c) == 4 and a.isdigit() and b.isdigit() and c.isdigit():
                    da, db, dy = int(a), int(b), int(c)
                    # If first looks like month, assume MM/DD
                    if 1 <= da <= 12 and 1 <= db <= 31:
                        d = datetime(dy, da, db)
                    else:
                        # assume DD/MM
                        d = datetime(dy, db, da)
                    return d.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def get_packages(product_type: str) -> List[Dict[str, Any]]:
    data = _load_fixture("packages.json")
    return list(data.get(product_type.upper(), []))


def evaluate_upgrade_savings(product_type: str, fee_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Given product_type and recent fee events, compute potential savings per package.

    reduces: mapping of fee_code -> factor (0.5 halves, 0.0 waives). waives list implies factor 0.0.
    Returns list sorted by highest estimated savings.
    """
    packages = get_packages(product_type)
    recommendations: List[Dict[str, Any]] = []
    for pkg in packages:
        waives = set((pkg.get("waives") or []))
        reduces = dict(pkg.get("reduces") or {})
        monthly_fee = float(pkg.get("monthly_fee", 0.0))
        saved = 0.0
        for evt in fee_events:
            code = (evt.get("fee_code") or "").upper()
            amt = float(evt.get("amount", 0))
            if code in waives:
                saved += amt
            elif code in reduces:
                factor = float(reduces.get(code, 1.0))
                saved += amt * (1.0 - factor)
        # Estimate net benefit = savings - monthly fee
        net = saved - monthly_fee
        # Business requirement: always offer an upsell; include packages even if net <= 0, but annotate benefit
        recommendations.append({
            "package_id": pkg.get("id"),
            "name": pkg.get("name"),
            "monthly_fee": monthly_fee,
            "estimated_monthly_savings": round(saved, 2),
            "estimated_net_benefit": round(net, 2),
            "notes": pkg.get("notes", "")
        })
    recommendations.sort(key=lambda x: x.get("estimated_net_benefit", 0.0), reverse=True)
    return recommendations


def list_transactions(account_id: str, start: Optional[str], end: Optional[str]) -> List[Dict[str, Any]]:
    data = _load_fixture("transactions.json")
    txns = list(data.get(account_id, []))
    if start or end:
        start_dt = _parse_iso_date(start) or datetime.min
        end_dt = _parse_iso_date(end) or datetime.max
        out: List[Dict[str, Any]] = []
        for t in txns:
            td = _parse_iso_date(t.get("date"))
            if td and start_dt <= td <= end_dt:
                out.append(t)
        return out
    return txns


def get_fee_schedule(product_type: str) -> Dict[str, Any]:
    data = _load_fixture("fee_schedules.json")
    return dict(data.get(product_type.upper(), {}))


def detect_fees(transactions: List[Dict[str, Any]], schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for t in transactions:
        if str(t.get("entry_type")).upper() == "FEE":
            fee_code = (t.get("fee_code") or "").upper()
            sched_entry = None
            for s in schedule.get("fees", []) or []:
                if str(s.get("code", "")).upper() == fee_code:
                    sched_entry = s
                    break
            evt = {
                "id": t.get("id") or str(uuid.uuid4()),
                "posted_date": t.get("date"),
                "amount": float(t.get("amount", 0)),
                "description": t.get("description") or fee_code,
                "fee_code": fee_code,
                "schedule": sched_entry or None,
            }
            results.append(evt)
    try:
        results.sort(key=lambda x: x.get("posted_date") or "")
    except Exception:
        pass
    return results


def explain_fee(fee_event: Dict[str, Any]) -> str:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    code = (fee_event.get("fee_code") or "").upper()
    name = fee_event.get("schedule", {}).get("name") or code.title()
    posted = fee_event.get("posted_date") or ""
    amount = float(fee_event.get("amount") or 0)
    policy = fee_event.get("schedule", {}).get("policy") or ""
    if not openai_api_key:
        base = f"You were charged {name} on {posted} for CAD {amount:.2f}."
        if code == "NSF":
            return base + " This is applied when a payment is attempted but the account balance was insufficient."
        if code == "MAINTENANCE":
            return base + " This is the monthly account fee as per your account plan."
        if code == "ATM":
            return base + " This fee applies to certain ATM withdrawals."
        return base + " This fee was identified based on your recent transactions."

    llm = ChatOpenAI(model=os.getenv("EXPLAIN_MODEL", "gpt-4o"), api_key=openai_api_key)
    chain = EXPLAIN_FEE_PROMPT | llm
    out = chain.invoke(
        {
            "fee_code": code,
            "posted_date": posted,
            "amount": f"{amount:.2f}",
            "schedule_name": name,
            "schedule_policy": policy,
        }
    )
    text = getattr(out, "content", None)
    return text if isinstance(text, str) and text.strip() else f"You were charged {name} on {posted} for CAD {amount:.2f}."


def check_dispute_eligibility(fee_event: Dict[str, Any]) -> Dict[str, Any]:
    code = (fee_event.get("fee_code") or "").upper()
    amount = float(fee_event.get("amount", 0))
    first_time = bool(fee_event.get("first_time_90d", False))
    eligible = False
    reason = ""
    if code in {"NSF", "ATM", "MAINTENANCE", "WITHDRAWAL"} and amount <= 20.0 and first_time:
        eligible = True
        reason = "First occurrence in 90 days and small amount"
    return {"eligible": eligible, "reason": reason}


def create_dispute_case(fee_event: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
    if idempotency_key in _DISPUTES_DB:
        return _DISPUTES_DB[idempotency_key]
    case = {
        "case_id": str(uuid.uuid4()),
        "status": "submitted",
        "fee_id": fee_event.get("id"),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _DISPUTES_DB[idempotency_key] = case
    return case


def authenticate_user(session_id: str, name: Optional[str], dob_yyyy_mm_dd: Optional[str], last4: Optional[str], secret_answer: Optional[str], customer_id: Optional[str] = None) -> Dict[str, Any]:
    """Mock identity verification.

    Rules (mock):
    - If dob == 1990-01-01 and last4 == 6001 or secret_answer == "blue", auth succeeds.
    - Otherwise, remains pending with which fields are still missing.
    Persists per session_id.
    """
    session = _SESSIONS.get(session_id) or {"verified": False, "name": name, "customer_id": customer_id}
    if isinstance(name, str) and name:
        session["name"] = name
    if isinstance(customer_id, str) and customer_id:
        session["customer_id"] = customer_id
    if isinstance(dob_yyyy_mm_dd, str) and dob_yyyy_mm_dd:
        # Normalize DOB to YYYY-MM-DD
        norm = _normalize_dob(dob_yyyy_mm_dd)
        session["dob"] = norm or dob_yyyy_mm_dd
    if isinstance(last4, str) and last4:
        session["last4"] = last4
    if isinstance(secret_answer, str) and secret_answer:
        session["secret"] = secret_answer

    ok = False
    # If a specific customer is in context, validate against their profile and accounts
    if isinstance(session.get("customer_id"), str):
        prof = get_profile(session.get("customer_id"))
        accts = get_accounts(session.get("customer_id"))
        dob_ok = _normalize_dob(session.get("dob")) == _normalize_dob(prof.get("dob")) and bool(session.get("dob"))
        last4s = {str(a.get("account_number"))[-4:] for a in accts if a.get("account_number")}
        last4_ok = isinstance(session.get("last4"), str) and session.get("last4") in last4s
        def _norm_secret(x: Optional[str]) -> str:
            return (x or "").strip().lower()
        secret_ok = _norm_secret(session.get("secret")) == _norm_secret(prof.get("secret_answer"))
        if dob_ok and (last4_ok or secret_ok):
            ok = True
    else:
        # Optional demo fallback (disabled by default)
        allow_fallback = os.getenv("RBC_FEES_ALLOW_GLOBAL_FALLBACK", "0") not in ("", "0", "false", "False")
        if allow_fallback and session.get("dob") == "1990-01-01" and (session.get("last4") == "6001" or (session.get("secret") or "").strip().lower() == "blue"):
            ok = True
    session["verified"] = ok
    _SESSIONS[session_id] = session
    need: list[str] = []
    if not session.get("dob"):
        need.append("dob")
    if not session.get("last4") and not session.get("secret"):
        need.append("last4_or_secret")
    if not session.get("customer_id"):
        need.append("customer")
    resp: Dict[str, Any] = {"session_id": session_id, "verified": ok, "needs": need, "profile": {"name": session.get("name")}}
    try:
        if isinstance(session.get("customer_id"), str):
            prof = get_profile(session.get("customer_id"))
            if isinstance(prof, dict) and prof.get("secret_question"):
                resp["question"] = prof.get("secret_question")
    except Exception:
        pass
    return resp


