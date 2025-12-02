"""Tools for claims investigation agent.

LangChain tools that provide access to claims data and investigation guidance.
"""

import json
from typing import Optional
from langchain_core.tools import tool

# Import logic functions
try:
    from . import logic as claims_logic
except Exception:
    import importlib.util as _ilu
    import os
    _dir = os.path.dirname(__file__)
    _logic_path = os.path.join(_dir, "logic.py")
    _spec = _ilu.spec_from_file_location("claims_logic", _logic_path)
    claims_logic = _ilu.module_from_spec(_spec)
    assert _spec and _spec.loader
    _spec.loader.exec_module(claims_logic)


@tool
def get_suspicious_claims_tool(
    min_risk_score: int = 50,
    status: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Get list of suspicious healthcare claims that need investigation.
    
    Use this tool when asked about suspicious claims, claims that need review,
    or high-risk claims.
    
    Args:
        min_risk_score: Minimum risk score to include (0-100). Higher scores are more suspicious. Default: 50
        status: Filter by status ('pending_investigation', 'approved', 'denied'). Default: all statuses
        limit: Maximum number of claims to return. Default: 10
    
    Returns:
        JSON string with list of suspicious claims, including beneficiary info and phone numbers.
        Each claim includes: claim_id, beneficiary_name, phone_number, suspicion_reason, risk_score
    """
    claims = claims_logic.get_suspicious_claims(min_risk_score, status, limit)
    
    # Format for easy reading
    result = {
        "total_suspicious_claims": len(claims),
        "claims": [
            {
                "claim_id": c["claim_id"],
                "beneficiary_name": c["beneficiary_name"],
                "phone_number": c["phone_number"],
                "claim_type": c.get("claim_type"),
                "claim_amount": c.get("claim_amount"),
                "risk_score": c.get("risk_score"),
                "suspicion_reason": c.get("suspicion_reason"),
                "status": c.get("status")
            }
            for c in claims
        ]
    }
    
    return json.dumps(result, indent=2)


@tool
def get_claim_investigation_guidance_tool(claim_id: str) -> str:
    """
    Get detailed investigation guidance for a specific claim.
    
    Use this tool to understand HOW to investigate a claim and WHAT information to gather.
    This will tell you:
    - If a call to the beneficiary is needed
    - Why the claim is suspicious
    - What specific questions to ask
    - What information to verify
    
    Args:
        claim_id: The claim ID to investigate (e.g., 'CLM-001')
    
    Returns:
        JSON string with investigation guidance including:
        - requires_call: Boolean indicating if a call is needed
        - call_reason: Why the call is necessary
        - information_needed: List of specific questions/info to gather
        - risk_score: How suspicious the claim is (0-100)
        - beneficiary contact info (name and phone)
    """
    guidance = claims_logic.get_claim_investigation_guidance(claim_id)
    return json.dumps(guidance, indent=2)


@tool
def search_claims_by_beneficiary_tool(name: str) -> str:
    """
    Search for claims by beneficiary name.
    
    Use this to find all claims for a specific person or to search by partial name.
    
    Args:
        name: Beneficiary name or partial name (case-insensitive)
    
    Returns:
        JSON string with list of matching claims
    """
    claims = claims_logic.search_claims_by_beneficiary(name)
    
    result = {
        "total_found": len(claims),
        "beneficiary_search": name,
        "claims": [
            {
                "claim_id": c["claim_id"],
                "beneficiary_name": c["beneficiary_name"],
                "claim_type": c.get("claim_type"),
                "claim_amount": c.get("claim_amount"),
                "is_suspicious": c.get("is_suspicious"),
                "risk_score": c.get("risk_score"),
                "status": c.get("status")
            }
            for c in claims
        ]
    }
    
    return json.dumps(result, indent=2)


@tool
def get_claim_details_tool(claim_id: str) -> str:
    """
    Get complete details for a specific claim.
    
    Args:
        claim_id: The claim ID (e.g., 'CLM-001')
    
    Returns:
        JSON string with full claim details including all medical codes, dates, and flags
    """
    claim = claims_logic.get_claim_by_id(claim_id)
    
    if not claim:
        return json.dumps({"error": f"Claim {claim_id} not found"})
    
    return json.dumps(claim, indent=2)


@tool
def get_high_risk_claims_tool() -> str:
    """
    Get high-risk claims that need immediate investigation attention.
    
    Returns claims with risk score >= 75 that are pending investigation.
    These are the most critical cases requiring urgent attention.
    
    Returns:
        JSON string with list of high-risk claims sorted by risk score (highest first)
    """
    claims = claims_logic.get_high_risk_claims(min_score=75)
    
    result = {
        "total_high_risk": len(claims),
        "urgent_attention_needed": len([c for c in claims if c.get("risk_score", 0) >= 90]),
        "claims": [
            {
                "claim_id": c["claim_id"],
                "beneficiary_name": c["beneficiary_name"],
                "phone_number": c["phone_number"],
                "risk_score": c.get("risk_score"),
                "suspicion_reason": c.get("suspicion_reason"),
                "requires_call": c.get("requires_call"),
                "claim_amount": c.get("claim_amount")
            }
            for c in claims
        ]
    }
    
    return json.dumps(result, indent=2)

