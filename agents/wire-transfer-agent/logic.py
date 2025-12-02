import os
import json
import uuid
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI


_FIXTURE_CACHE: Dict[str, Any] = {}
_DISPUTES_DB: Dict[str, Dict[str, Any]] = {}
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_OTP_DB: Dict[str, Dict[str, Any]] = {}
_QUOTES: Dict[str, Dict[str, Any]] = {}
_BENEFICIARIES_DB: Dict[str, List[Dict[str, Any]]] = {}


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


def find_customer_by_full_name(full_name: str) -> Dict[str, Any]:
    data = _load_fixture("accounts.json")
    customers = data.get("customers", {})
    target = (full_name or "").strip().lower()
    for cid, blob in customers.items():
        prof = blob.get("profile") if isinstance(blob, dict) else None
        if isinstance(prof, dict):
            fn = f"{str(prof.get('first_name') or '').strip()} {str(prof.get('last_name') or '').strip()}".strip().lower()
            ff = str(prof.get("full_name") or "").strip().lower()
            if target and (target == fn or target == ff):
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
    # YYYY MM DD or YYYY/MM/DD or YYYY.MM.DD (loosely)
    try:
        import re as _re
        parts = _re.findall(r"\d+", t)
        if len(parts) >= 3 and len(parts[0]) == 4:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                dt = datetime(y, m, d)
                return dt.strftime("%Y-%m-%d")
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


def _find_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    data = _load_fixture("accounts.json")
    customers = data.get("customers", {})
    for _, blob in customers.items():
        accts = (blob or {}).get("accounts", [])
        for a in accts or []:
            if str(a.get("account_id")) == account_id:
                return a
    return None


def get_account_balance(account_id: str) -> Dict[str, Any]:
    acc = _find_account_by_id(account_id) or {}
    return {
        "account_id": account_id,
        "currency": acc.get("currency"),
        "balance": float(acc.get("balance", 0.0)),
        "daily_wire_limit": float(acc.get("daily_wire_limit", 0.0)),
        "wire_enabled": bool(acc.get("wire_enabled", False)),
    }


def get_exchange_rate(from_currency: str, to_currency: str, amount: float) -> Dict[str, Any]:
    if from_currency.upper() == to_currency.upper():
        return {
            "from": from_currency.upper(),
            "to": to_currency.upper(),
            "mid_rate": 1.0,
            "applied_rate": 1.0,
            "margin_bps": 0,
            "converted_amount": round(float(amount), 2),
        }
    data = _load_fixture("exchange_rates.json")
    pairs = data.get("pairs", [])
    mid = None
    bps = 150
    fc = from_currency.upper()
    tc = to_currency.upper()
    for p in pairs:
        if str(p.get("from")).upper() == fc and str(p.get("to")).upper() == tc:
            mid = float(p.get("mid_rate"))
            bps = int(p.get("margin_bps", bps))
            break
    if mid is None:
        # naive inverse lookup
        for p in pairs:
            if str(p.get("from")).upper() == tc and str(p.get("to")).upper() == fc:
                inv = float(p.get("mid_rate"))
                mid = 1.0 / inv if inv else None
                bps = int(p.get("margin_bps", bps))
                break
    if mid is None:
        mid = 1.0
    applied = mid * (1.0 - bps / 10000.0)
    converted = float(amount) * applied
    return {
        "from": fc,
        "to": tc,
        "mid_rate": round(mid, 6),
        "applied_rate": round(applied, 6),
        "margin_bps": bps,
        "converted_amount": round(converted, 2),
    }


def calculate_wire_fee(kind: str, amount: float, from_currency: str, to_currency: str, payer: str) -> Dict[str, Any]:
    fees = _load_fixture("fee_schedules.json")
    k = (kind or "").strip().upper()
    payer_opt = (payer or "SHA").strip().upper()
    if k not in ("DOMESTIC", "INTERNATIONAL"):
        return {"error": "invalid_type", "message": "type must be DOMESTIC or INTERNATIONAL"}
    if payer_opt not in ("OUR", "SHA", "BEN"):
        return {"error": "invalid_payer", "message": "payer must be OUR, SHA, or BEN"}
    breakdown: Dict[str, float] = {}
    if k == "DOMESTIC":
        breakdown["DOMESTIC_BASE"] = float(fees.get("DOMESTIC", {}).get("base_fee", 15.0))
    else:
        intl = fees.get("INTERNATIONAL", {})
        breakdown["INTERNATIONAL_BASE"] = float(intl.get("base_fee", 25.0))
        breakdown["SWIFT"] = float(intl.get("swift_network_fee", 5.0))
        breakdown["CORRESPONDENT"] = float(intl.get("correspondent_fee", 10.0))
        breakdown["LIFTING"] = float(intl.get("lifting_fee", 5.0))

    initiator = 0.0
    recipient = 0.0
    for code, fee in breakdown.items():
        if payer_opt == "OUR":
            initiator += fee
        elif payer_opt == "SHA":
            # Sender pays origin bank fees (base, swift); recipient pays intermediary (correspondent/lifting)
            if code in ("DOMESTIC_BASE", "INTERNATIONAL_BASE", "SWIFT"):
                initiator += fee
            else:
                recipient += fee
        elif payer_opt == "BEN":
            recipient += fee
    return {
        "type": k,
        "payer": payer_opt,
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "amount": float(amount),
        "initiator_fees_total": round(initiator, 2),
        "recipient_fees_total": round(recipient, 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
    }


def screen_sanctions(name: str, country: str) -> Dict[str, Any]:
    data = _load_fixture("sanctions_list.json")
    blocked = data.get("blocked", [])
    nm = (name or "").strip().lower()
    cc = (country or "").strip().upper()
    for e in blocked:
        if str(e.get("name", "")).strip().lower() == nm and str(e.get("country", "")).strip().upper() == cc:
            return {"cleared": False, "reason": "Sanctions match"}
    return {"cleared": True}


def check_wire_limits(account_id: str, amount: float) -> Dict[str, Any]:
    acc = _find_account_by_id(account_id) or {}
    if not acc:
        return {"ok": False, "reason": "account_not_found"}
    bal = float(acc.get("balance", 0.0))
    lim = float(acc.get("daily_wire_limit", 0.0))
    if not bool(acc.get("wire_enabled", False)):
        return {"ok": False, "reason": "wire_not_enabled"}
    if amount > lim:
        return {"ok": False, "reason": "exceeds_daily_limit", "limit": lim}
    if amount > bal:
        return {"ok": False, "reason": "insufficient_funds", "balance": bal}
    return {"ok": True, "balance": bal, "limit": lim}


def get_cutoff_and_eta(kind: str, country: str) -> Dict[str, Any]:
    cfg = _load_fixture("cutoff_times.json")
    k = (kind or "").strip().upper()
    key = "DOMESTIC" if k == "DOMESTIC" else "INTERNATIONAL"
    info = cfg.get(key, {})
    return {
        "cutoff_local": info.get("cutoff_local", "17:00"),
        "eta_hours": list(info.get("eta_hours", [24, 72])),
        "country": country
    }


def get_country_requirements(code: str) -> List[str]:
    data = _load_fixture("country_requirements.json")
    return list(data.get(code.upper(), []))


def validate_beneficiary(country_code: str, beneficiary: Dict[str, Any]) -> Dict[str, Any]:
    required = get_country_requirements(country_code)
    missing: List[str] = []
    for field in required:
        if not isinstance(beneficiary.get(field), str) or not str(beneficiary.get(field)).strip():
            missing.append(field)
    return {"ok": len(missing) == 0, "missing": missing}


def save_beneficiary(customer_id: str, beneficiary: Dict[str, Any]) -> Dict[str, Any]:
    arr = _BENEFICIARIES_DB.setdefault(customer_id, [])
    bid = beneficiary.get("beneficiary_id") or f"B-{uuid.uuid4().hex[:6]}"
    entry = dict(beneficiary)
    entry["beneficiary_id"] = bid
    arr.append(entry)
    return {"beneficiary_id": bid}


def generate_otp(customer_id: str) -> Dict[str, Any]:
    # Prefer static OTP from fixture for predictable testing
    static = None
    try:
        data = _load_fixture("otps.json")
        if isinstance(data, dict):
            byc = data.get("by_customer", {}) or {}
            static = byc.get(customer_id) or data.get("default")
    except Exception:
        static = None
    code = str(static or f"{uuid.uuid4().int % 1000000:06d}").zfill(6)
    _OTP_DB[customer_id] = {"otp": code, "created_at": datetime.utcnow().isoformat() + "Z"}
    # In real world, send to phone/email; here we mask
    resp = {"sent": True, "destination": "on-file", "masked": "***-***-****"}
    try:
        if os.getenv("WIRE_DEBUG_OTP", "0").lower() not in ("", "0", "false"):  # dev convenience
            resp["debug_code"] = code
    except Exception:
        pass
    return resp


def verify_otp(customer_id: str, otp: str) -> Dict[str, Any]:
    rec = _OTP_DB.get(customer_id) or {}
    ok = str(rec.get("otp")) == str(otp)
    if ok:
        rec["used_at"] = datetime.utcnow().isoformat() + "Z"
        _OTP_DB[customer_id] = rec
    return {"verified": ok}


def authenticate_user_wire(session_id: str, customer_id: Optional[str], full_name: Optional[str], dob_yyyy_mm_dd: Optional[str], ssn_last4: Optional[str], secret_answer: Optional[str]) -> Dict[str, Any]:
    session = _SESSIONS.get(session_id) or {"verified": False, "customer_id": customer_id, "name": full_name}
    if isinstance(customer_id, str) and customer_id:
        session["customer_id"] = customer_id
    if isinstance(full_name, str) and full_name:
        session["name"] = full_name
    if isinstance(dob_yyyy_mm_dd, str) and dob_yyyy_mm_dd:
        session["dob"] = dob_yyyy_mm_dd
    if isinstance(ssn_last4, str) and ssn_last4:
        session["ssn_last4"] = ssn_last4
    if isinstance(secret_answer, str) and secret_answer:
        session["secret"] = secret_answer

    ok = False
    cid = session.get("customer_id")
    if isinstance(cid, str):
        prof = get_profile(cid)
        user_dob_norm = _normalize_dob(session.get("dob"))
        prof_dob_norm = _normalize_dob(prof.get("dob"))
        dob_ok = (user_dob_norm is not None) and (user_dob_norm == prof_dob_norm)
        ssn_ok = str(session.get("ssn_last4") or "") == str(prof.get("ssn_last4") or "")
        def _norm(x: Optional[str]) -> str:
            # Extract only the core answer, removing common phrases
            s = (x or "").strip().lower()
            # Remove common prefixes that users might add
            for prefix in ["my favorite color is ", "my favorite ", "it is ", "it's ", "the answer is "]:
                if s.startswith(prefix):
                    s = s[len(prefix):].strip()
            return s
        secret_ok = _norm(session.get("secret")) == _norm(prof.get("secret_answer"))
        
        # Enhanced logging for verification
        print(f"🔐 IDENTITY VERIFICATION DEBUG (customer_id: {cid}):")
        print(f"   • Customer: {prof.get('full_name')}")
        print(f"   • DOB provided: {session.get('dob')} | Expected: {prof.get('dob')} | Match: {dob_ok}")
        print(f"   • SSN provided: {session.get('ssn_last4')} | Expected: {prof.get('ssn_last4')} | Match: {ssn_ok}")
        if session.get("secret"):
            print(f"   • Secret provided: '{_norm(session.get('secret'))}' | Expected: '{_norm(prof.get('secret_answer'))}' | Match: {secret_ok}")
        print(f"   • Verification logic: dob_ok={dob_ok} AND (ssn_ok={ssn_ok} OR secret_ok={secret_ok})")
        
        # Check if strict mode is enabled (requires ALL provided fields to match)
        strict_mode = os.getenv("WIRE_TRANSFER_STRICT_VERIFICATION", "false").lower() == "true"
        
        if strict_mode:
            # Strict: ALL provided fields must match
            all_ok = dob_ok
            if session.get("ssn_last4"):
                all_ok = all_ok and ssn_ok
            if session.get("secret"):
                all_ok = all_ok and secret_ok
            
            print(f"   • STRICT MODE: All provided fields must match")
            if session.get("ssn_last4") and not ssn_ok:
                print(f"   ⚠️  SSN mismatch detected!")
            if session.get("secret") and not secret_ok:
                print(f"   ⚠️  Secret answer mismatch detected!")
            print(f"   • Result: {'✅ VERIFIED' if all_ok else '❌ FAILED'}")
            ok = all_ok
        else:
            # Standard: DOB + (SSN OR Secret)
            print(f"   • STANDARD MODE: DOB + (SSN OR Secret)")
            print(f"   • Result: {'✅ VERIFIED' if (dob_ok and (ssn_ok or secret_ok)) else '❌ FAILED'}")
            if dob_ok and (ssn_ok or secret_ok):
                ok = True
    session["verified"] = ok
    _SESSIONS[session_id] = session
    need: List[str] = []
    if _normalize_dob(session.get("dob")) is None:
        need.append("dob")
    if not session.get("ssn_last4") and not session.get("secret"):
        need.append("ssn_last4_or_secret")
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


def quote_wire(kind: str, from_account_id: str, beneficiary: Dict[str, Any], amount: float, from_currency: str, to_currency: str, payer: str) -> Dict[str, Any]:
    # FX
    fx = get_exchange_rate(from_currency, to_currency, amount)
    converted_amount = fx["converted_amount"]
    # Fees
    fee = calculate_wire_fee(kind, amount, from_currency, to_currency, payer)
    # Limits and balance
    limits = check_wire_limits(from_account_id, amount)
    if not limits.get("ok"):
        return {"error": "limit_or_balance", "details": limits}
    # Sanctions
    sanc = screen_sanctions(str(beneficiary.get("account_name") or beneficiary.get("name") or ""), str(beneficiary.get("country") or ""))
    if not sanc.get("cleared"):
        return {"error": "sanctions", "details": sanc}
    # ETA
    eta = get_cutoff_and_eta(kind, str(beneficiary.get("country") or ""))

    payer_opt = (payer or "SHA").upper()
    initiator_fees = float(fee.get("initiator_fees_total", 0.0))
    recipient_fees = float(fee.get("recipient_fees_total", 0.0))
    net_sent = float(amount) + (initiator_fees if payer_opt in ("OUR", "SHA") else 0.0)
    # recipient side fees reduce the amount received when SHA/BEN
    net_received = float(converted_amount)
    if payer_opt in ("SHA", "BEN"):
        net_received = max(0.0, net_received - recipient_fees)

    qid = f"Q-{uuid.uuid4().hex[:8]}"
    quote = {
        "quote_id": qid,
        "type": kind.upper(),
        "from_account_id": from_account_id,
        "amount": float(amount),
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "payer": payer_opt,
        "fx": fx,
        "fees": fee,
        "net_sent": round(net_sent, 2),
        "net_received": round(net_received, 2),
        "eta": eta,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "expires_at": (datetime.utcnow().isoformat() + "Z")
    }
    _QUOTES[qid] = quote
    return quote


def wire_transfer_domestic(quote_id: str, otp: str) -> Dict[str, Any]:
    q = _QUOTES.get(quote_id)
    if not q or q.get("type") != "DOMESTIC":
        return {"error": "invalid_quote"}
    # OTP expected: we need customer_id context; skip and assume OTP verified externally
    conf = f"WD-{uuid.uuid4().hex[:8]}"
    return {"confirmation_id": conf, "status": "submitted"}


def wire_transfer_international(quote_id: str, otp: str) -> Dict[str, Any]:
    q = _QUOTES.get(quote_id)
    if not q or q.get("type") != "INTERNATIONAL":
        return {"error": "invalid_quote"}
    conf = f"WI-{uuid.uuid4().hex[:8]}"
    return {"confirmation_id": conf, "status": "submitted"}


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


