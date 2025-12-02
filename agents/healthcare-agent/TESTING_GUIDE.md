# Healthcare Agent Testing Guide

This guide provides test scenarios to validate the improved tool calling behavior, especially the **secret question authentication flow**.

## Test Patients

Two test patients are available in `mock_data/patients.json`:

### Patient 1: John Marshall
- **Full Name**: John Marshall
- **DOB**: 1960-01-01 (January 1st, 1960)
- **MRN Last-4**: 0001
- **Secret Question**: "What is your favorite color?"
- **Secret Answer**: blue
- **Allergies**: Penicillin
- **Medications**: Acetaminophen 500mg PRN

### Patient 2: Francesco Ciannella
- **Full Name**: Francesco Ciannella
- **DOB**: 1990-01-01 (January 1st, 1990)
- **MRN Last-4**: 6001
- **Secret Question**: "What city were you born in?"
- **Secret Answer**: rome
- **Allergies**: NKA (No Known Allergies)
- **Medications**: Lisinopril 10mg daily

---

## Test Scenarios

### ✅ Test 1: Secret Question Flow (MOST IMPORTANT)

**Purpose**: Verify the agent correctly handles the two-step secret question authentication.

**Steps**:
1. Say: "My name is John Marshall"
2. Agent should call `find_patient()` and greet you
3. Say: "January 1st, 1960" (DOB)
4. Agent should call `verify_identity(dob=...)`
5. **EXPECTED**: Agent should ASK: "For security, what is your favorite color?"
6. Say: "Blue"
7. Agent should call `verify_identity(dob=..., secret_answer="Blue")`
8. **EXPECTED**: Agent confirms verification and asks about symptoms

**Success Criteria**:
- ✅ Agent explicitly asks the secret question
- ✅ Agent waits for your answer before proceeding
- ✅ Agent confirms "You're verified" after correct answer
- ✅ Agent does NOT ask for MRN last-4

**Common Failure Modes (Old Behavior)**:
- ❌ Agent skips asking the secret question
- ❌ Agent asks for MRN last-4 instead of secret question
- ❌ Agent claims verification before getting secret answer

---

### ✅ Test 2: Wrong Secret Answer

**Purpose**: Verify agent handles incorrect secret answers gracefully.

**Steps**:
1. Say: "My name is John Marshall"
2. Say: "January 1st, 1960" (DOB)
3. Agent asks: "What is your favorite color?"
4. Say: "Red" (WRONG - correct is "blue")

**Expected Behavior**:
- ✅ Agent says verification failed
- ✅ Agent asks for MRN last-4 as alternative: "Could you provide the last 4 digits of your MRN?"
- ✅ Agent does NOT proceed to medical questions

---

### ✅ Test 3: MRN Last-4 Path (Alternative Auth)

**Purpose**: Verify agent accepts MRN last-4 without asking secret question.

**Steps**:
1. Say: "My name is John Marshall"
2. Say: "January 1st, 1960, and MRN last-4 is 0001"

**Expected Behavior**:
- ✅ Agent calls `verify_identity(dob=..., mrn_last4="0001")`
- ✅ Agent confirms verification immediately
- ✅ Agent does NOT ask secret question (since MRN provided)

---

### ✅ Test 4: Allergy Awareness

**Purpose**: Verify agent considers allergies before recommending medications.

**Steps**:
1. Complete authentication as John Marshall
2. Say: "I have a headache and a sore throat"
3. Agent calls `get_patient_profile_tool()` and `triage_symptoms_tool()`

**Expected Behavior**:
- ✅ Agent mentions: "You have a penicillin allergy"
- ✅ Agent recommends Acetaminophen (which patient already has)
- ✅ Agent does NOT recommend penicillin-based antibiotics
- ✅ Agent references existing medication: "Since you're already taking acetaminophen as needed..."

---

### ✅ Test 5: Urgent Triage (Chest Pain)

**Purpose**: Verify agent correctly escalates urgent symptoms.

**Steps**:
1. Complete authentication as Francesco Ciannella
2. Say: "I'm having severe chest pain and shortness of breath"

**Expected Behavior**:
- ✅ Agent calls `triage_symptoms_tool(symptoms_text="severe chest pain and shortness of breath")`
- ✅ Returns: `{risk: "urgent", red_flags: ["chest pain"]}`
- ✅ Agent immediately says: "Chest pain can be serious. Please call 911 now or go to the nearest emergency room."
- ✅ Agent does NOT offer to book a regular appointment
- ✅ Agent emphasizes urgency

---

### ✅ Test 6: Self-Care with Appointment Booking

**Purpose**: Verify full flow for non-urgent symptoms with appointment.

**Steps**:
1. Complete authentication as John Marshall
2. Say: "I have a mild headache and feel tired, but no fever, no neck stiffness"
3. Agent triages and provides self-care advice
4. Say: "Yes, I'd like to schedule an appointment"

**Expected Behavior**:
- ✅ Agent calls `triage_symptoms_tool()` → returns `risk: "self_care"`
- ✅ Agent provides advice: "Try rest, hydration, and acetaminophen as directed"
- ✅ Agent offers appointment: "Would you like a telehealth appointment?"
- ✅ Agent calls `list_providers_tool()` → presents options
- ✅ Agent calls `get_provider_slots_tool()` → shows times in friendly format
- ✅ After you choose, agent calls `schedule_appointment_tool()`
- ✅ Agent confirms: "Booked. I'll send details to your phone ending in 0101."
- ✅ Agent calls `get_preferred_pharmacy_tool()` and confirms pharmacy
- ✅ At end, agent calls `log_call_tool()` silently

---

### ✅ Test 7: Francesco Ciannella Secret Question

**Purpose**: Test second patient with different secret question.

**Steps**:
1. Say: "My name is Francesco Ciannella"
2. Say: "January 1st, 1990"
3. **EXPECTED**: Agent asks "For security, what city were you born in?"
4. Say: "Rome"

**Expected Behavior**:
- ✅ Agent asks the correct secret question for Francesco
- ✅ Agent accepts "Rome" (case-insensitive)
- ✅ Agent confirms verification

---

### ✅ Test 8: Profile Not Found

**Purpose**: Verify agent handles unknown patients gracefully.

**Steps**:
1. Say: "My name is Jane Doe"

**Expected Behavior**:
- ✅ Agent calls `find_patient(full_name="Jane Doe")`
- ✅ Returns: `{}`
- ✅ Agent says: "I'm not finding you in our system. Could you verify the spelling of your name?"
- ✅ Agent does NOT proceed to verification without patient_id

---

## Debugging Tips

### Check Logs
Look for these log entries in `app.log`:

```
INFO - LLM tool_calls: ['find_patient']
INFO - tool find_patient result: {"patient_id": "pt_jmarshall", ...}
INFO - LLM tool_calls: ['verify_identity']
INFO - verify_identity: verified=False needs=['mrn_last4_or_secret']
INFO - LLM content: For security, what is your favorite color?
INFO - verify_identity: verified=True needs=[]
INFO - LLM tool_calls: ['get_patient_profile_tool']
```

### Common Issues

**Issue**: Agent doesn't ask secret question
- **Check**: Tool docstring has 7-step CRITICAL SECRET QUESTION FLOW section
- **Check**: System prompt has explicit secret question instructions in step 2

**Issue**: Agent asks for MRN instead of secret question
- **Fix**: Ensure prompt says "If 'question' field is present: READ THE EXACT QUESTION"

**Issue**: Agent proceeds without verification
- **Check**: Prompt has "NEVER claim verification until verified=true"
- **Check**: Tool auto-injects patient_id

---

## Expected Tool Call Sequences

### Minimal Flow (MRN path):
```
1. find_patient(full_name="John Marshall")
2. verify_identity(dob="...", mrn_last4="0001")
3. get_patient_profile_tool()
4. triage_symptoms_tool(symptoms_text="...")
5. log_call_tool(notes="...", triage_json="...")
```

### Secret Question Flow:
```
1. find_patient(full_name="John Marshall")
2. verify_identity(dob="...")                    ← First call
3. verify_identity(dob="...", secret_answer="...") ← Second call
4. get_patient_profile_tool()
5. triage_symptoms_tool(symptoms_text="...")
6. log_call_tool(...)
```

### Full Flow with Booking:
```
1. find_patient(full_name="John Marshall")
2. verify_identity(dob="...")
3. verify_identity(dob="...", secret_answer="...")
4. get_patient_profile_tool()
5. triage_symptoms_tool(symptoms_text="...")
6. list_providers_tool()
7. get_provider_slots_tool(provider_id="...")
8. schedule_appointment_tool(provider_id="...", slot_iso="...")
9. get_preferred_pharmacy_tool()
10. log_call_tool(notes="...", triage_json="...")
```

---

## Success Metrics

After improvements, you should see:
- ✅ **100% secret question ask rate** (when MRN not provided)
- ✅ **Zero skipped verifications**
- ✅ **Allergy mentions in every medication recommendation**
- ✅ **Proper urgent escalation** for chest pain, severe symptoms
- ✅ **Two-call pattern** for secret question auth

---

## Quick Test Script

```bash
# Test 1: John Marshall secret question
Agent: May I have your full name?
You: John Marshall
Agent: Please confirm your date of birth.
You: January 1st, 1960
Agent: For security, what is your favorite color?  ← MUST ASK THIS
You: Blue
Agent: Thank you, you're verified. What brings you in today?  ← MUST CONFIRM

# Test 2: Francesco with symptoms
You: Francesco Ciannella
Agent: Date of birth?
You: January 1st, 1990
Agent: For security, what city were you born in?  ← MUST ASK THIS
You: Rome
Agent: What's going on today?
You: I have a mild headache
Agent: [provides advice considering Lisinopril medication]  ← MUST MENTION MEDS
```

---

## Reporting Issues

If tests fail, provide:
1. **Patient name** used
2. **Exact conversation** (user input + agent responses)
3. **Expected behavior** vs **actual behavior**
4. **Log excerpt** from `app.log` showing tool calls
5. **Which test scenario** from this guide

