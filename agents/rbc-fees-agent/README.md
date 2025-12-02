# RBC Fees Agent

This agent helps customers understand and resolve bank account fees using mock data. It verifies identity, reviews recent activity, explains fees, checks refund eligibility, and proactively recommends account upgrades.

## How to use

1. Start the conversation and provide your full name.
2. Verify identity when prompted:
   - Provide date of birth (any format; the agent normalizes it).
   - Provide either last-4 of an account number or the secret answer. If a secret question is returned, answer it.
3. Specify a date or date range to search for fees (e.g., "last 30 days", "2025-07-01 to 2025-09-01").
4. Ask to explain a specific fee or ask the agent to review fees in your timeframe. The agent will explain the fee and check dispute eligibility if asked.
5. The agent will also suggest upgrade options if they would have avoided/saved fees.

## Mock identities and accounts

Use these example customers from `mock_data/accounts.json`:

- Francesco Ciannella (customer_id `cust_test`)
  - DOB: 1990-01-01
  - Secret question: What is your favorite color? → Answer: "blue"
  - Accounts: `A-CHK-001` (number ends with 6001), `A-SAV-001` (7182)
- Alice Stone (`cust_alice`): DOB 1985-05-12, secret answer: "green"
- Bob Rivera (`cust_bob`): DOB 1978-11-30, secret answer: "red"

Tip: You can identify by name first, then provide DOB + last-4 (e.g., 6001) or the secret answer.

## Example conversation

- You: Hi, I saw a fee on my account.
- Agent: Hi! Can I have your full name to get started?
- You: Francesco Ciannella
- Agent: Thanks. Please share your date of birth and either the last-4 of an account or your secret answer.
- You: DOB is 1990-01-01, last-4 is 6001.
- Agent: Thanks, you are verified. What timeframe should I look at for fees?
- You: Last 90 days.
- Agent: I’ll review that period. I found a Monthly maintenance fee posted on 2025-09-01 for CAD 10.00... (explanation). Would you like me to check if it’s eligible for a refund?
- You: Yes.
- Agent: It’s not eligible due to policy, but here are tips... Also, switching to the Premium plan could avoid future fees.

## Relevant fixtures

- Transactions: `mock_data/transactions.json`
- Fee schedules: `mock_data/fee_schedules.json`
- Accounts: `mock_data/accounts.json`

## Notes

- The agent requires identity verification before accessing account data.
- Always specify a timeframe for fee review; the agent won’t assume one by default.
