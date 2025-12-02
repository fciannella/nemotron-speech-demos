import os
import sys
import json
from typing import Any, Dict, Optional

from langchain_core.tools import tool

# Robust logic import isolated to this agent
try:
    from . import logic as hc_logic  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _logic_path = os.path.join(_dir, "logic.py")
    _spec = _ilu.spec_from_file_location("healthcare_agent_logic", _logic_path)
    hc_logic = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(hc_logic)  # type: ignore

find_patient_by_name = hc_logic.find_patient_by_name
find_patient_by_full_name = hc_logic.find_patient_by_full_name
get_patient_profile = hc_logic.get_patient_profile
authenticate_patient = hc_logic.authenticate_patient
get_preferred_pharmacy = hc_logic.get_preferred_pharmacy
list_providers = hc_logic.list_providers
get_provider_slots = hc_logic.get_provider_slots
schedule_appointment = hc_logic.schedule_appointment
triage_symptoms = hc_logic.triage_symptoms
log_call = hc_logic.log_call


@tool
def find_patient(first_name: str | None = None, last_name: str | None = None, full_name: str | None = None) -> str:
    """Find a patient_id by name to use in subsequent tool calls.
    
    WHEN TO CALL: After the caller provides their name, call this tool FIRST before any other tools.
    
    PARAMETERS:
    - full_name: Full name like "John Marshall" (PREFERRED - use this if you have it)
    - first_name, last_name: Split names if full_name not available
    
    RETURNS: JSON object with either:
    - {"patient_id": "pt_abc123", "profile": {...}} if found
    - {} if not found (ask caller to verify spelling or provide more info)
    
    NEXT STEP: If patient_id found, call verify_identity() next to authenticate them.
    If not found, politely ask the caller to verify their name spelling.
    
    EXAMPLE:
    Caller says: "My name is John Marshall"
    → Call find_patient(full_name="John Marshall")
    → Get {"patient_id": "pt_jmarshall", ...}
    → Next call verify_identity(patient_id="pt_jmarshall", ...)
    """
    if isinstance(full_name, str) and full_name.strip():
        return json.dumps(find_patient_by_full_name(full_name))
    return json.dumps(find_patient_by_name(first_name or "", last_name or ""))


@tool
def get_patient_profile_tool(patient_id: str) -> str:
    """Fetch comprehensive patient medical profile including allergies, medications, conditions, and recent visits.
    
    WHEN TO CALL: ONLY after verify_identity() returns verified=true. Call this before giving medical advice.
    
    PARAMETERS:
    - patient_id: From find_patient() result (auto-injected if available)
    
    RETURNS: JSON with:
    - "profile": {first_name, last_name, dob, phone, email, etc.}
    - "allergies": ["Penicillin", ...] - CRITICAL for prescriptions/recommendations
    - "medications": [{name, sig, otc}, ...] - Current meds (check before recommending OTC drugs)
    - "conditions": ["Hypertension", ...] - Existing conditions
    - "recent_visits": [{date, type, reason, outcome}, ...]
    - "vitals": {last: {date, bp, hr, temp_f, bmi}}
    
    WHAT TO DO WITH THIS DATA:
    - Check allergies before ANY medication recommendations (including OTC)
    - Review current medications to avoid duplicates or interactions
    - Consider existing conditions when giving advice
    - Reference recent visits if relevant to current symptoms
    
    EXAMPLE:
    → Call get_patient_profile_tool(patient_id="pt_jmarshall")
    ← Returns: {"allergies": ["Penicillin"], "medications": [{"name": "Acetaminophen", "sig": "500mg as needed", "otc": true}], ...}
    → When giving advice: "Since you're already taking acetaminophen as needed and have a penicillin allergy, I recommend..."
    """
    return json.dumps(get_patient_profile(patient_id))


@tool
def verify_identity(session_id: str, patient_id: str | None = None, full_name: str | None = None, dob_yyyy_mm_dd: str | None = None, mrn_last4: str | None = None, secret_answer: str | None = None) -> str:
    """Verify caller identity before accessing medical records. CRITICAL: Identity verification is MANDATORY before any medical information access.
    
    WHEN TO CALL: After find_patient() returns a patient_id. Call this repeatedly until verified=true.
    
    PARAMETERS (collect these from caller):
    - session_id: Current session/thread ID (REQUIRED - auto-injected)
    - patient_id: From find_patient() result (REQUIRED - auto-injected if available)
    - full_name: Caller's full name
    - dob_yyyy_mm_dd: Date of birth in ANY format (we normalize it). Examples: "January 1st 1960", "01/01/1960", "1960-01-01"
    - mrn_last4: Last 4 digits of Medical Record Number (MRN)
    - secret_answer: Answer to the secret question (if question was provided in previous call)
    
    AUTHENTICATION LOGIC:
    Caller is verified ONLY if: DOB matches AND (MRN last-4 matches OR secret_answer matches)
    
    RETURNS: JSON with:
    - "verified": true/false - Whether identity is confirmed
    - "needs": ["dob", "mrn_last4_or_secret"] - List of missing required fields
    - "question": "What is your favorite color?" - Secret question to ask caller (if available and mrn_last4 not provided)
    
    CRITICAL SECRET QUESTION FLOW:
    1. First call: verify_identity(patient_id="pt_abc", dob_yyyy_mm_dd="1960-01-01")
    2. Response: {"verified": false, "needs": ["mrn_last4_or_secret"], "question": "What is your favorite color?"}
    3. YOU MUST: Read the question verbatim to the caller: "What is your favorite color?"
    4. Collect their answer (e.g., "blue")
    5. Second call: verify_identity(patient_id="pt_abc", dob_yyyy_mm_dd="1960-01-01", secret_answer="blue")
    6. Response: {"verified": true, "needs": []}
    
    WHAT TO DO:
    - If "verified": true → Proceed to get_patient_profile_tool()
    - If "verified": false AND "question" present → ASK the question to the caller, collect answer, call verify_identity again with secret_answer
    - If "verified": false AND "needs" has items → Ask caller for missing info ONLY, then call verify_identity again
    - If verification fails after all info provided → Politely explain you cannot verify identity and cannot proceed
    
    EXAMPLE CONVERSATION:
    Agent: "Please confirm your date of birth."
    Caller: "January 1st, 1960"
    → Call verify_identity(dob_yyyy_mm_dd="January 1st, 1960")
    ← Returns: {"verified": false, "needs": ["mrn_last4_or_secret"], "question": "What is your favorite color?"}
    Agent: "Thank you. For security, what is your favorite color?"
    Caller: "Blue"
    → Call verify_identity(dob_yyyy_mm_dd="January 1st, 1960", secret_answer="Blue")
    ← Returns: {"verified": true, "needs": []}
    Agent: "Thank you, you're verified. What brings you in today?"
    """
    res = authenticate_patient(session_id, patient_id, full_name, dob_yyyy_mm_dd, mrn_last4, secret_answer)
    return json.dumps(res)


@tool
def get_preferred_pharmacy_tool(patient_id: str) -> str:
    """Get the patient's preferred pharmacy on file for prescription fulfillment.
    
    WHEN TO CALL: When booking an appointment that may result in a prescription, or if caller asks about pharmacy.
    
    PARAMETERS:
    - patient_id: From find_patient() result (auto-injected if available)
    
    RETURNS: JSON with:
    - "pharmacy_id": "ph_sc_1010"
    - "name": "CVS Pharmacy"
    - "address": "1010 El Camino Real, Santa Clara, CA 95050"
    - "phone": "+1-408-555-9999"
    
    Or {} if no preferred pharmacy on file.
    
    WHAT TO DO:
    - Confirm with patient: "Should we keep your pharmacy at [address] for any prescriptions?"
    - If they want to change it, note that for the provider
    
    EXAMPLE:
    → Call get_preferred_pharmacy_tool(patient_id="pt_jmarshall")
    ← Returns: {"name": "CVS Pharmacy", "address": "1010 El Camino Real, Santa Clara, CA"}
    → Say: "Should we keep the pharmacy at 1010 El Camino Real in Santa Clara for any prescriptions?"
    """
    return json.dumps(get_preferred_pharmacy(patient_id))


@tool
def list_providers_tool(specialty: str | None = None) -> str:
    """List available healthcare providers for appointment booking.
    
    WHEN TO CALL: When ready to book an appointment after triage and patient wants to schedule.
    
    PARAMETERS:
    - specialty: Filter by specialty (e.g., "Primary Care", "Urgent Care", "Cardiology"). Leave None for all providers.
    
    RETURNS: JSON array of providers with:
    - "provider_id": "prov_smith_md"
    - "name": "Dr. Emily Smith"
    - "specialty": "Primary Care"
    - "credentials": "MD"
    
    WHAT TO DO:
    - Present 1-2 options to patient: "I can book you with Dr. Emily Smith, our primary care physician, or Alex Chang, nurse practitioner."
    - Don't overwhelm with too many choices
    - After patient chooses, call get_provider_slots_tool() to show available times
    
    EXAMPLE:
    → Call list_providers_tool(specialty="Primary Care")
    ← Returns: [{"provider_id": "prov_smith_md", "name": "Dr. Emily Smith", "specialty": "Primary Care"}, ...]
    → Say: "I can book you with Dr. Emily Smith. Let me check her availability."
    → Next: Call get_provider_slots_tool(provider_id="prov_smith_md")
    """
    return json.dumps(list_providers(specialty))


@tool
def get_provider_slots_tool(provider_id: str, count: int = 3) -> str:
    """Get available appointment time slots for a specific provider.
    
    WHEN TO CALL: After patient chooses a provider from list_providers_tool().
    
    PARAMETERS:
    - provider_id: From list_providers_tool() result (e.g., "prov_smith_md")
    - count: Number of slots to return (default 3, keep it 2-4 for voice conversation)
    
    RETURNS: JSON array of ISO datetime strings like:
    - ["2025-10-08T20:00:00", "2025-10-09T08:30:00", "2025-10-09T16:00:00"]
    
    WHAT TO DO:
    - Convert times to friendly format: "today at 8pm", "tomorrow at 8:30am", "tomorrow at 4pm"
    - Present 2-3 options: "Next openings are today at 8pm, or tomorrow at 8:30am or 4pm. Which works for you?"
    - Wait for patient to choose ONE specific time
    - After patient chooses, call schedule_appointment_tool() with their chosen slot
    
    EXAMPLE:
    → Call get_provider_slots_tool(provider_id="prov_smith_md", count=3)
    ← Returns: ["2025-10-08T20:00:00", "2025-10-09T08:30:00", "2025-10-09T16:00:00"]
    → Say: "Next openings are today at 8pm, or tomorrow at 8:30am or 4pm. Which works for you?"
    Caller: "Tomorrow at 8:30am"
    → Call schedule_appointment_tool(provider_id="prov_smith_md", slot_iso="2025-10-09T08:30:00")
    """
    return json.dumps(get_provider_slots(provider_id, count))


@tool
def schedule_appointment_tool(provider_id: str, slot_iso: str, patient_id: str | None = None) -> str:
    """Book/confirm an appointment slot with a provider for the patient.
    
    WHEN TO CALL: After patient verbally confirms which time slot they want from get_provider_slots_tool().
    
    PARAMETERS:
    - provider_id: From list_providers_tool() (e.g., "prov_smith_md")
    - slot_iso: EXACT ISO datetime string from get_provider_slots_tool() that patient chose (e.g., "2025-10-09T08:30:00")
    - patient_id: From find_patient() result (auto-injected if available)
    
    RETURNS: JSON with:
    - "appointment_id": "A-abc12345"
    - "provider_id": "prov_smith_md"
    - "slot": "2025-10-09T08:30:00"
    - "status": "booked"
    
    WHAT TO DO AFTER:
    - Confirm to patient: "Booked. I'll send details to your phone ending in [last 4 digits]."
    - Ask about pharmacy if appointment may involve prescriptions: call get_preferred_pharmacy_tool()
    - At end of call, call log_call_tool() to document the visit
    
    EXAMPLE:
    Caller chose: "Tomorrow at 8:30am"
    → Call schedule_appointment_tool(provider_id="prov_smith_md", slot_iso="2025-10-09T08:30:00")
    ← Returns: {"appointment_id": "A-abc12345", "status": "booked"}
    → Say: "Booked. I'll send details to your phone. Should we keep your pharmacy at [address]?"
    """
    return json.dumps(schedule_appointment(provider_id, slot_iso, patient_id))


@tool
def triage_symptoms_tool(patient_id: str | None, symptoms_text: str) -> str:
    """Analyze patient symptoms using clinical triage rules to determine urgency and guidance.
    
    WHEN TO CALL: ONLY after thorough symptom assessment. Ask clarifying questions about red flags BEFORE calling this tool.
    
    CRITICAL: This tool uses simple keyword matching, so be VERY CAREFUL with your symptoms_text.
    - Only include symptoms that ARE PRESENT
    - Do NOT mention symptoms that are absent (saying "no numbness" will trigger the "numbness" keyword!)
    - Instead, after screening for red flags, ONLY list positive findings in symptoms_text
    - Use descriptive language: "mild headache for 2 days, gradual onset, no concerning features"
    - If patient denies all red flags, do NOT list them - just describe the actual complaint
    
    PARAMETERS:
    - patient_id: From find_patient() result (auto-injected if available, used for age-based rules)
    - symptoms_text: Description of PRESENT symptoms only (DO NOT list absent symptoms to avoid false triggers)
      Good: "mild headache for 2 days, gradual onset, relieved by rest"
      Good: "moderate headache with fever 101F, started yesterday"
      Bad: "headache, no numbness, no confusion" (will trigger "numbness" and "confusion" keywords!)
      Bad: "headache" (too vague, lacks detail for proper triage)
    
    RETURNS: JSON with:
    - "risk": "urgent" | "soon" | "self_care" - Urgency level
    - "advice": "Try rest, hydration..." - Clinical guidance to share with patient
    - "red_flags": ["stiff neck", "high fever"] - Keywords detected (may include false positives!)
    - "rule": "Headache - typical" - Internal rule name that matched
    
    RISK LEVELS:
    - "urgent": Potential emergency (but verify with clinical judgment)
    - "soon": Schedule appointment within 1-2 days
    - "self_care": Home care with OTC medications, monitor symptoms
    
    WHAT TO DO WITH RESULTS (USE CLINICAL JUDGMENT):
    - If risk="urgent" AND red_flags has items AND patient confirmed those symptoms: Direct to ER/911
    - If risk="urgent" BUT patient explicitly denied red flag symptoms: FALSE POSITIVE - schedule appointment instead
    - If risk="soon": Give advice and offer appointment within 1-2 days
    - If risk="self_care": Give advice, check allergies/meds for safety, offer optional follow-up
    - ALWAYS tailor advice based on patient's allergies and current medications from get_patient_profile_tool()
    - Remember: Most common symptoms (headache, fever, fatigue) are NOT emergencies
    
    EXAMPLE 1 (TRUE URGENT):
    Conversation: Patient says "severe crushing chest pain, sweating, short of breath"
    → Call triage_symptoms_tool(symptoms_text="severe chest pain with sweating and shortness of breath")
    ← Returns: {"risk": "urgent", "red_flags": ["chest pain"]}
    → Clinical judgment: Patient confirmed severe chest pain = TRUE URGENT
    → Say: "This sounds serious. Please call 911 now or go to the nearest emergency room."
    
    EXAMPLE 2 (AVOIDING FALSE POSITIVES):
    Conversation: You ask "Any severe symptoms like confusion, weakness, or numbness?" Patient says "No, none of those"
    → Call triage_symptoms_tool(symptoms_text="mild headache for 2 days, gradual onset, relieved with rest")
    ← Returns: {"risk": "self_care", "red_flags": []}
    → Say: "Try rest, hydration, and acetaminophen. Would you like a follow-up appointment?"
    (Note: Did NOT mention "no confusion, no numbness" to avoid triggering those keywords)
    
    EXAMPLE 3 (SELF-CARE):
    → Call triage_symptoms_tool(symptoms_text="low-grade fever 100.5F for 1 day with mild fatigue")
    ← Returns: {"risk": "self_care", "advice": "Hydration, rest, and acetaminophen can help..."}
    → Say: "For a low-grade fever, rest and hydration are key. You're already taking acetaminophen as needed, which is safe with your medications."
    """
    return json.dumps(triage_symptoms(patient_id, symptoms_text))


@tool
def log_call_tool(session_id: str, patient_id: str | None = None, notes: str | None = None, triage_json: str | None = None) -> str:
    """Log the call encounter details, symptoms, triage outcome, and advice provided for medical records.
    
    WHEN TO CALL: At the END of the call, after all guidance provided and appointments scheduled.
    
    PARAMETERS:
    - session_id: Current session/thread ID (REQUIRED - auto-injected)
    - patient_id: From find_patient() result (auto-injected if available)
    - notes: Brief summary of the call in plain text (e.g., "Patient called with headache and fatigue. No red flags. Advised rest and hydration. Appointment scheduled for tomorrow 8:30am with Dr. Smith.")
    - triage_json: JSON string of triage_symptoms_tool() output (pass the entire JSON result as a string)
    
    RETURNS: JSON with:
    - "logged": true
    - "log_id": "L-abc12345"
    
    WHAT TO DO:
    - Call this as the final step before ending the call
    - Include key details: symptoms reported, advice given, appointments booked, pharmacy confirmed
    - No need to tell the patient you're logging it, just do it silently
    
    EXAMPLE:
    After full call with symptom discussion and appointment booking:
    → Call log_call_tool(
        notes="Patient reported mild headache and fatigue. No red flags. Has penicillin allergy and takes acetaminophen PRN. Advised rest, hydration, acetaminophen as needed. Booked appointment tomorrow 8:30am with Dr. Smith. Pharmacy confirmed at CVS Santa Clara.",
        triage_json='{"risk": "self_care", "advice": "Try rest and hydration...", "red_flags": []}'
      )
    ← Returns: {"logged": true, "log_id": "L-abc12345"}
    """
    triage: Dict[str, Any] | None
    try:
        triage = json.loads(triage_json or "null") if triage_json else None
    except Exception:
        triage = None
    return json.dumps(log_call(session_id, patient_id, notes, triage))


