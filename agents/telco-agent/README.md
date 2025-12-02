# Telco Agent

A mobile operator assistant that verifies callers via SMS OTP, reviews current plan and data usage, answers roaming questions, recommends packages, manages addons and plan changes, and can close contracts (mock).

## How to use

1. Provide your mobile number (MSISDN). The agent will send an SMS OTP.
2. Provide the 6-digit code to verify.
3. Ask for:
   - Current package and contract status
   - Current data balance/remaining
   - Roaming details for a country (pricing and passes)
   - Package recommendations (optionally give preferences: budget, need_5g, travel_country)
   - Close contract (the agent summarizes any early termination fee and asks for confirmation)
   - Addons list or purchase a roaming pass
   - Change package (now or next_cycle)
   - Billing summary and set data alerts

## Mock data

From `mock_data/`:

- Customers (`customers.json`):
  - `+15551234567` (Alex Lee): package `P-40` Standard 40GB 5G, billing cycle day 5, current_month used 12.5 GB.
  - `+447911123456` (Sam Taylor): package `P-10` Lite 10GB 4G.
- OTPs (`otps.json`):
  - default: `123456`
  - by number: `+15551234567` → `246810`, `+447911123456` → `135790`
- Packages (`packages.json`): 4G/5G plans including Unlimited options with features like EU roaming and data rollover.
- Roaming rates (`roaming_rates.json`): pay-as-you-go and pass options for `IT`, `FR`, `US`.

## Example conversation

- Agent: Hi! What’s your mobile number?
- You: +1 555 123 4567
- Agent: I’ve sent a 6-digit code to ***-***-**67. What’s the code?
- You: 246810
- Agent: Verified. Would you like your current package or data balance?
- You: What’s my data balance?
- Agent: You’ve used 12.5 GB this cycle on Standard 40GB 5G; 27.5 GB remaining. Anything else?
- You: I’m traveling to Italy. Roaming?
- Agent: Italy is included by your plan; passes also available (EU Day 1GB €5, Week 5GB €15). Purchase a pass?
- You: Recommend a cheaper plan under $50, 5G.
- Agent: Suggesting Travelers EU 20GB ($45): 5G, EU roaming included. Estimated monthly cost $45.

## Extended actions (tools)

- List addons: active roaming passes
- Purchase roaming pass: e.g., country `IT`, pass `EU-WEEK-5GB`
- Change package: `change_package(now|next_cycle)`
- Billing summary: monthly fee and last bill
- Set data alerts: by percent and/or GB

## Notes

- OTP is required before any account operations.
- Recommendations use recent usage history to estimate monthly costs.
