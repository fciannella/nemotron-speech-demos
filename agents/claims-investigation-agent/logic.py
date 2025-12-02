"""Business logic for healthcare claims investigation.

Functions for querying and analyzing claims data.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Cache for fixture data
_FIXTURE_CACHE: Dict[str, Any] = {}


def _fixtures_dir() -> Path:
    """Get path to mock_data directory."""
    return Path(__file__).parent / "mock_data"


def _load_fixture(name: str) -> Any:
    """Load fixture from JSON file with caching."""
    if name in _FIXTURE_CACHE:
        return _FIXTURE_CACHE[name]
    
    path = _fixtures_dir() / name
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    _FIXTURE_CACHE[name] = data
    return data


def get_all_claims() -> Dict[str, Dict]:
    """Get all claims from mock data."""
    data = _load_fixture("claims.json")
    return data.get("claims", {})


def get_claim_by_id(claim_id: str) -> Optional[Dict]:
    """Get a specific claim by ID."""
    claims = get_all_claims()
    return claims.get(claim_id)


def get_suspicious_claims(
    min_risk_score: int = 50,
    status: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Get suspicious claims based on criteria.
    
    Args:
        min_risk_score: Minimum risk score to include (0-100)
        status: Filter by status (e.g., 'pending_investigation', 'approved', 'denied')
        limit: Maximum number of claims to return
    
    Returns:
        List of suspicious claims sorted by risk score (highest first)
    """
    claims = get_all_claims()
    
    # Filter suspicious claims
    suspicious = []
    for claim_id, claim in claims.items():
        # Must be marked suspicious
        if not claim.get("is_suspicious"):
            continue
        
        # Must meet minimum risk score
        if claim.get("risk_score", 0) < min_risk_score:
            continue
        
        # Filter by status if specified
        if status and claim.get("status") != status:
            continue
        
        suspicious.append(claim)
    
    # Sort by risk score (highest first)
    suspicious.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    
    # Limit results
    return suspicious[:limit]


def search_claims_by_beneficiary(name: str) -> List[Dict]:
    """
    Search claims by beneficiary name (case-insensitive partial match).
    
    Args:
        name: Beneficiary name or partial name
    
    Returns:
        List of matching claims
    """
    claims = get_all_claims()
    search_term = name.lower().strip()
    
    results = []
    for claim_id, claim in claims.items():
        beneficiary = claim.get("beneficiary_name", "").lower()
        if search_term in beneficiary:
            results.append(claim)
    
    return results


def get_claim_investigation_guidance(claim_id: str) -> Dict[str, Any]:
    """
    Get investigation guidance for a specific claim.
    
    Args:
        claim_id: The claim ID to investigate
    
    Returns:
        Dict with investigation guidance including:
        - requires_call: Whether a call is needed
        - call_reason: Why the call is needed
        - information_needed: List of questions to ask
        - risk_assessment: Risk score and details
    """
    claim = get_claim_by_id(claim_id)
    
    if not claim:
        return {
            "error": f"Claim {claim_id} not found",
            "claim_id": claim_id
        }
    
    if not claim.get("is_suspicious"):
        return {
            "claim_id": claim_id,
            "beneficiary_name": claim.get("beneficiary_name"),
            "requires_call": False,
            "recommendation": "Claim appears legitimate. No investigation needed.",
            "risk_score": claim.get("risk_score", 0),
            "status": claim.get("status")
        }
    
    return {
        "claim_id": claim_id,
        "beneficiary_name": claim.get("beneficiary_name"),
        "phone_number": claim.get("phone_number"),
        "requires_call": claim.get("requires_call", True),
        "call_reason": claim.get("suspicion_reason"),
        "suspicion_details": claim.get("suspicion_details"),
        "information_needed": claim.get("information_needed", []),
        "risk_score": claim.get("risk_score", 0),
        "claim_amount": claim.get("claim_amount"),
        "service_date": claim.get("service_date"),
        "provider": claim.get("provider"),
        "status": claim.get("status"),
        "recommended_action": "Call beneficiary to verify details and gather additional information"
    }


def get_claims_by_status(status: str) -> List[Dict]:
    """
    Get all claims with a specific status.
    
    Args:
        status: Status to filter by (e.g., 'pending_investigation', 'approved', 'denied')
    
    Returns:
        List of claims with that status
    """
    claims = get_all_claims()
    
    results = []
    for claim_id, claim in claims.items():
        if claim.get("status") == status:
            results.append(claim)
    
    return results


def get_high_risk_claims(min_score: int = 75) -> List[Dict]:
    """
    Get high-risk claims that need immediate attention.
    
    Args:
        min_score: Minimum risk score (default: 75)
    
    Returns:
        List of high-risk claims sorted by score
    """
    return get_suspicious_claims(min_risk_score=min_score, status="pending_investigation")


def get_claim_summary(claim: Dict) -> str:
    """
    Generate a human-readable summary of a claim (TTS-friendly).
    
    Args:
        claim: Claim dictionary
    
    Returns:
        Plain text summary suitable for TTS
    """
    beneficiary = claim.get("beneficiary_name", "Unknown")
    claim_id = claim.get("claim_id", "Unknown")
    amount = claim.get("claim_amount", 0)
    claim_type = claim.get("claim_type", "Unknown")
    risk_score = claim.get("risk_score", 0)
    
    summary = f"Claim {claim_id} for {beneficiary}. Type: {claim_type}. Amount: {amount} dollars. Risk score: {risk_score}."
    
    if claim.get("is_suspicious"):
        reason = claim.get("suspicion_reason", "Unknown reason")
        summary += f" This claim is flagged as suspicious. Reason: {reason}."
        
        if claim.get("requires_call"):
            summary += " A call to the beneficiary is recommended to gather more information."
    else:
        summary += " This claim appears legitimate."
    
    return summary


def format_date(iso_date: str) -> str:
    """
    Format ISO date to human-readable format.
    
    Args:
        iso_date: Date in ISO format (YYYY-MM-DD)
    
    Returns:
        Human-readable date (e.g., "November 1, 2025")
    """
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except:
        return iso_date  # Return as-is if parsing fails


def build_call_metadata(claim_id: str) -> Dict[str, Any]:
    """
    Build complete metadata for claim verification call.
    
    This creates the structured metadata required by the claim-verification-agent
    according to the integration guide format.
    
    Args:
        claim_id: The claim ID to build metadata for
    
    Returns:
        Dict with complete metadata structure including:
        - beneficiary_name
        - phone_number
        - claim_details (nested object)
        - verification_context
        - verification_tasks
        - risk_score
    """
    claim = get_claim_by_id(claim_id)
    
    if not claim:
        raise ValueError(f"Claim {claim_id} not found")
    
    # Build claim_details nested object
    claim_details = {
        "claim_type": claim.get("claim_type"),
        "claim_amount": f"${claim.get('claim_amount', 0):,.2f}",  # Format: "$16,000.00"
        "service_date": format_date(claim.get("service_date", "")),
        "submission_date": format_date(claim.get("submission_date", "")),
        "provider": claim.get("provider"),
    }
    
    # Add optional medical codes if present
    if claim.get("diagnosis_code"):
        claim_details["diagnosis_code"] = claim["diagnosis_code"]
    if claim.get("procedure_code"):
        claim_details["procedure_code"] = claim["procedure_code"]
    
    # Build complete metadata structure
    metadata = {
        "beneficiary_name": claim["beneficiary_name"],
        "phone_number": claim["phone_number"],
        "claim_details": claim_details,
        "verification_context": claim.get("suspicion_details", claim.get("suspicion_reason", "")),
        "verification_tasks": claim.get("information_needed", []),
        "risk_score": claim.get("risk_score", 0)
    }
    
    return metadata

