# Budget guardrails

The agent decides autonomously whether to pay, bounded by two limits configured
in `.env`. This is what makes the agent safe to run unattended.

## Configuration

```ini
RESOURCE_PRICE=0.10     # price the server charges (human TUSD units)
BUDGET_PER_CALL=0.50    # reject any single payment above this
BUDGET_TOTAL=5.00       # reject once cumulative spend would exceed this
```

All values are in human TUSD units; the code converts to base units (6 decimals).

## The decision

Before signing anything, `agent_pay.py`:

1. Reads `maxAmountRequired` from the 402 quote.
2. Rejects if `price > BUDGET_PER_CALL`.
3. Loads cumulative spend from `.spent.json` (per token) and rejects if
   `already_spent + price > BUDGET_TOTAL`.
4. Only if both checks pass does it sign and pay.

A rejected call exits with code `2` and prints the reason — it never signs a
transfer. This guarantees the per-call and cumulative caps cannot be exceeded.

## Cumulative tracking

Spend is tracked locally in `.spent.json` (git-ignored), keyed by token address:

```json
{
  "0x<tusd_address>": 100000
}
```

The on-chain `PaymentLedger` also tracks `totalSpent[payer][token]`, so the cap
can be cross-checked against chain state (see `ledger.md`). To reset the local
counter for a fresh demo, delete `.spent.json`.

## Tuning for a demo

- Lower `BUDGET_TOTAL` to show the agent refusing a payment once the cap is hit.
- Raise `RESOURCE_PRICE` above `BUDGET_PER_CALL` to show a per-call rejection.
