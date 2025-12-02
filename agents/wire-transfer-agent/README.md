# Wire Transfer Agent

This agent helps customers send domestic or international wire transfers using mock tools and data. It verifies the caller, collects transfer details, validates requirements, provides a quote (FX/fees/ETA), then confirms with OTP before executing.

## How to use

1. Start with your full name.
2. Verify identity (mandatory): provide DOB plus either SSN last-4 or your secret answer. If a secret question is returned, answer it.
3. Provide transfer info one by one when asked: type (DOMESTIC/INTERNATIONAL), source account (last-4), amount and source currency, destination country and currency, who pays fees (OUR/SHA/BEN).
4. Provide beneficiary details depending on country requirements.
5. Review the quote (FX rate, fees, net sent/received, ETA), then request OTP, provide the code, and confirm execution.

## Mock identities and accounts

From `mock_data/accounts.json`:

- Francesco Ciannella (`cust_test`)
  - DOB 1990-01-01, SSN last-4 6001, secret answer "blue"
  - Accounts: `WT-CHK-001` (wire-enabled, USD, balance 5200.50), `WT-SAV-001` (not wire-enabled)
- Alice Stone (`cust_alice`): last-4 1101, secret answer "green"

OTP: see `mock_data/otps.json` (default = 123456).

Country requirements (`mock_data/country_requirements.json`):
- US: routing_number, account_number, account_name
- CA: institution_number, transit_number, account_number, account_name
- EU: iban, account_name

## Example conversation

- Agent: Hi! What’s your full name?
- You: Francesco Ciannella
- Agent: Please provide DOB and either SSN last-4 or your secret answer.
- You: 1990-01-01 and 6001
- Agent: Verified. Is this a DOMESTIC or INTERNATIONAL wire?
- You: INTERNATIONAL
- Agent: From which account (last-4)?
- You: 6001
- Agent: How much and currency?
- You: 1000 USD to EUR
- Agent: Destination country?
- You: DE
- Agent: Who pays fees (OUR/SHA/BEN)?
- You: SHA
- Agent: Please provide beneficiary fields required for DE (EU): iban and account_name.
- You: iban DE89 37040044 0532013000, account_name Alice GmbH
- Agent: Here’s your quote: FX, fees, net sent/received, ETA. Shall I send an OTP to confirm?
- You: Yes
- Agent: Please provide the 6-digit OTP.
- You: 123456
- Agent: Transfer submitted. Confirmation WI-XXXXXX

## Notes

- Wire is only allowed from wire-enabled accounts and within daily limits and balances.
- For SHA/BEN, recipient fees reduce the amount received.
