# Healthcare Telehealth Nurse Agent

This agent is a 24/7 AI voice nurse for existing patients. It authenticates callers, retrieves mock patient profiles (medications, allergies, recent visits), recognizes common symptoms, performs contextual triage using decision rules, offers self‑care guidance, escalates urgent cases, and books appointments. All interactions aim to be clear, compassionate, and brief.

**✨ Recent Improvements**: Tool docstrings and system prompts have been significantly enhanced with:
- Clear step-by-step instructions for each tool
- Explicit guidance on the secret question authentication flow
- Detailed examples showing expected inputs/outputs
- Better error handling instructions
- Improved conversation flow structure

## What it does

- Authenticate the caller (name + DOB + MRN last‑4 or secret answer)
- Look up patient profile, allergies, medications, recent visits, preferred pharmacy
- Recognize symptoms (e.g., "I have a headache") and identify red flags
- Risk stratify and triage (self‑care, soon, urgent) using rules in `mock_data/triage_rules.json`
- Provide tailored advice based on symptoms and medication history
- Escalate urgent cases with clear instructions
- Offer scheduling with available providers from `mock_data/providers.json`
- Confirm preferred pharmacy for prescriptions if needed

## How to use (typical flow)

1. Start by stating your name.
2. Verify identity: provide DOB and either MRN last‑4 or your secret answer. If a secret question is returned, answer it.
3. Describe your symptoms in your own words.
4. The agent will ask brief, focused follow‑ups (one question at a time), provide guidance, and book if needed.

## Tool Call Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  1. GREETING & NAME                                         │
│     User: "My name is John Marshall"                        │
│     → find_patient(full_name="John Marshall")               │
│     ← {patient_id: "pt_jmarshall"}                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. IDENTITY VERIFICATION (CRITICAL)                        │
│     Agent: "Please confirm your date of birth"              │
│     User: "January 1st, 1960"                               │
│     → verify_identity(dob="January 1st, 1960")              │
│     ← {verified: false, question: "What is your favorite    │
│        color?", needs: ["mrn_last4_or_secret"]}             │
│                                                              │
│     Agent: "For security, what is your favorite color?"     │
│     User: "Blue"                                            │
│     → verify_identity(dob="...", secret_answer="Blue")      │
│     ← {verified: true, needs: []}                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. PROFILE RETRIEVAL                                       │
│     → get_patient_profile_tool()                            │
│     ← {allergies: ["Penicillin"],                           │
│        medications: [{name: "Acetaminophen", ...}], ...}    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. SYMPTOM COLLECTION & TRIAGE                             │
│     Agent: "What brings you in today?"                      │
│     User: "I have a headache and feel tired"                │
│     → triage_symptoms_tool(symptoms_text="headache and      │
│        fatigue, no red flags")                              │
│     ← {risk: "self_care", advice: "Try rest...",            │
│        red_flags: []}                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. APPOINTMENT BOOKING (if needed)                         │
│     → list_providers_tool()                                 │
│     ← [{provider_id: "prov_smith_md", ...}]                 │
│                                                              │
│     → get_provider_slots_tool(provider_id="prov_smith_md")  │
│     ← ["2025-10-09T08:30:00", "2025-10-09T16:00:00"]        │
│                                                              │
│     Agent: "Tomorrow at 8:30am or 4pm. Which works?"        │
│     User: "8:30am"                                          │
│     → schedule_appointment_tool(slot_iso="2025-10-09T08:30")│
│     ← {appointment_id: "A-abc123", status: "booked"}        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  6. PHARMACY CONFIRMATION                                   │
│     → get_preferred_pharmacy_tool()                         │
│     ← {name: "CVS", address: "1010 El Camino Real..."}      │
│     Agent: "Keep pharmacy at 1010 El Camino Real?"          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  7. CALL LOGGING & CLOSING                                  │
│     → log_call_tool(notes="...", triage_json="...")         │
│     ← {logged: true, log_id: "L-xyz789"}                    │
│     Agent: "If symptoms worsen, seek urgent care. Take care"│
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Step 2 is the most critical**: The secret question requires a TWO-call pattern
- **Always retrieve profile (Step 3)** before giving medical advice
- **Triage (Step 4)** determines whether to proceed with booking or direct to ER
- **Logging (Step 7)** documents the entire encounter

## Example conversation

- Agent: Welcome back to our clinic. I’m your nurse assistant. May I have your full name?
- You: John Marshall.
- Agent: Thanks, John. Please confirm your date of birth and either your MRN last‑4 or answer to your secret question.
- You: January 1st, 1960. MRN last‑4 is 0001.
- Agent: Thank you. You’re verified. What’s going on today?
- You: I have a headache and feel really fatigued.
- Agent: I’m sorry you’re feeling that way. Any red flag symptoms like worst headache of your life, head injury, stiff neck, weakness, vision changes, seizure, or fever over 102°F?
- You: No, none of those.
- Agent: Thanks for checking. You’re on acetaminophen as needed and have a penicillin allergy. Since symptoms are mild with no red flags, try hydration, rest, and acetaminophen as directed. Would you like a telehealth appointment in the next day or two?
- You: Yes, please.
- Agent: I can book with Alex Chang, NP. Next openings are today at 8:00 pm, or tomorrow at 8:30 am or 4:00 pm. Which do you prefer?
- You: Tomorrow at 8:30 am.
- Agent: Booked. I’ll send details to your phone ending in 0101. Should we keep the pharmacy at 1010 El Camino Real, Santa Clara for any prescriptions?
- You: Yes, that’s fine.
- Agent: Great. I’ve logged your symptoms, advice provided, and appointment. If anything worsens—especially fever over 102°F, neck stiffness, confusion, weakness, vision loss, or severe headache—seek urgent care or call emergency services.

## Mock data

- Patients: `mock_data/patients.json`
- Providers: `mock_data/providers.json`
- Pharmacies: `mock_data/pharmacies.json`
- Triage rules: `mock_data/triage_rules.json`

## Notes

- The agent prioritizes empathy and brevity. It asks one question at a time and avoids medical jargon.
- All data are mock fixtures for demo purposes only and are not real medical records.
